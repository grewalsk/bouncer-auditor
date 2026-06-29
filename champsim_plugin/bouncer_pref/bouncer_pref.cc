#include "bouncer_pref.h"
#include "cache.h"
#include <cstdlib>

void bouncer_pref::prefetcher_initialize()
{
  if (const char* g = std::getenv("BOUNCER_GATE")) gate_enabled = (std::string(g) == "1");
  if (const char* a = std::getenv("BOUNCER_ATTACK_WINDOW")) attack_window = std::atol(a);
  if (const char* w = std::getenv("BOUNCER_WINDOW")) window_accesses = std::strtoull(w, nullptr, 10);
  // env-tunable trust threshold / CUSUM (reward here = prefetch-usefulness rate)
  double tau = 0.04, gamma = 0.04, H = 0.20;
  if (const char* t = std::getenv("BOUNCER_TAU")) tau = std::atof(t);
  if (const char* gm = std::getenv("BOUNCER_GAMMA")) gamma = std::atof(gm);
  if (const char* h = std::getenv("BOUNCER_H")) H = std::atof(h);
  // N1: select the reward signal WITHOUT touching (tau,gamma,H,window,partition).
  if (const char* rw = std::getenv("BOUNCER_REWARD")) {
    std::string s(rw);
    if (s == "ownpf") reward_mode = 1;
    else if (s == "ownpf_peraccess") reward_mode = 2;
    else if (s == "ownacc") reward_mode = 3;
    else reward_mode = 0;  // "cachehit" or unset
  }
  auditor = bouncer::Bouncer(bouncer::BouncerConfig{N_SETS, N_L, N_F, 64, tau, gamma, H});
  if (const char* l = std::getenv("BOUNCER_LOG")) { log_path = l; log.open(log_path); if (log) log << "window,delta_hat,state,gate\n"; }
}

uint32_t bouncer_pref::prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch,
                                                access_type type, uint32_t metadata_in)
{
  const uint64_t blk = champsim::block_number{addr}.to<uint64_t>();
  const uint32_t set = static_cast<uint32_t>(blk % N_SETS);

  // ownacc (mode 3): a DEMAND that lands on a block this arm prefetched (and not
  // yet consumed) is a timely-useful prefetch -> reward 1, attributed to the set
  // that issued it (tag unchanged within the window). pf_pending was cleared at the
  // last reseed, so this credit can never leak across the L/F partition.
  if (reward_mode == 3 && type == access_type::LOAD) {
    auto it = pf_pending.find(blk);
    if (it != pf_pending.end()) { auditor.observe(set, 1.0); pf_pending.erase(it); }
  }

  // --- reward signal (N1 isolation): everything else (tau,H,window,partition,FSM)
  //     is held FIXED; ONLY this observation changes. ----------------------------
  if (reward_mode == 0) {
    // BASELINE: per-access cache-hit (the borrowed proxy). Δ̂ = hit-rate(learned)
    // - hit-rate(off). On a 99%-hit L1D the prefetch's contribution is a tiny
    // differential swamped by hits that occur regardless -> poor SNR -> over-gate.
    auditor.observe(set, cache_hit ? 1.0 : 0.0);
  } else if (reward_mode == 2) {
    // ABLATION: per-access useful_prefetch (timely hit on a prefetched line),
    // averaged over ALL accesses. Faithful-but-DILUTED: useful-pf rate ~0.15% on
    // roms, below K=tau+gamma/2 -> still over-gates. Shows scaling, not sign, is
    // the issue for a naive own-reward.
    auditor.observe(set, useful_prefetch ? 1.0 : 0.0);
  } else if (reward_mode == 1) {
    // EVENT-SCOPED own-reward via the cache's useful_prefetch bit (a NEGATIVE
    // RESULT we keep as an ablation): useful->1, uncovered demand miss->0. Because
    // the secret partition reseeds every window but the cache's prefetch bit
    // persists, prefetch credit leaks onto the retagged off arm -> Δ̂ goes negative
    // -> over-gates WORSE. Motivates the leak-free in-module tracking (mode 3).
    if (useful_prefetch) auditor.observe(set, 1.0);
    else if (!cache_hit) auditor.observe(set, 0.0);
  }
  // reward_mode == 3 (ownacc): observations happen on the demand-use path above and
  // the eviction path in prefetcher_cache_fill; nothing scored here.

  // gate decision: leaders fixed; followers follow the gate (or always-learned
  // when gating disabled, to isolate the auditor's effect)
  const bool learned = gate_enabled ? auditor.use_learned(set)
                                    : (auditor.pool_tag(set) != 2);  // leader-F still fallback
  const bool attacking = (attack_window >= 0) && (static_cast<long>(window_idx) >= attack_window);

  // --- learned controller: per-IP stride ---
  const uint64_t ipv = ip.to<uint64_t>();
  auto& st = stride_table[ipv];
  int64_t stride = st.valid ? (int64_t)blk - (int64_t)st.last_block : 0;

  // fallback pi0 = prefetch OFF (the paper's next-line/off fallback, "off" arm).
  // learned = aggressive stride: confident stride if seen twice, else next-line.
  int64_t pf_stride = 0;
  bool issue = false;
  if (learned) {
    issue = true;
    if (attacking) {
      pf_stride = BAD_STRIDE;               // corrupted -> useless far line (pollution)
    } else if (st.valid && stride != 0 && stride == st.last_stride) {
      pf_stride = stride;                   // confident stride prediction
    } else {
      pf_stride = 1;                        // default aggressive next-line
    }
  }
  // (fallback: issue stays false -> no prefetch)

  if (issue) {
    const bool light = intern_->get_mshr_occupancy_ratio() < 0.5;
    prefetch_line(champsim::address{champsim::block_number{addr} + pf_stride}, light, 0);
    if (reward_mode == 3) pf_pending.insert(blk + static_cast<uint64_t>(pf_stride));   // ownacc: track the issued prefetch
    if (st.valid && stride != 0 && stride == st.last_stride && !attacking) {  // degree 2 on confident stride
      prefetch_line(champsim::address{champsim::block_number{addr} + 2 * pf_stride}, light, 0);
      if (reward_mode == 3) pf_pending.insert(blk + static_cast<uint64_t>(2 * pf_stride));
    }
  }

  // update stride tracker
  st.last_stride = stride; st.last_block = blk; st.valid = true;

  // --- window boundary: run the Tier-B confirmer + gate ---
  if (++access_count % window_accesses == 0) {
    // Tier-A is not wired in this minimal module; the background Tier-B CUSUM
    // gates directly (the validated mimicry-safe path).
    bouncer::Gate g = auditor.end_window(/*tierA_escalate=*/false, /*tierA_clear=*/true);
    if (reward_mode == 3) pf_pending.clear();  // ownacc: reseed happened -> drop stale issue-time attributions (leak-free)
    if (log) {
      const char* sn[] = {"TRUSTED", "SUSPECT", "GATED", "PROBING"};
      log << window_idx << "," << auditor.last_delta_hat() << ","
          << sn[(int)g] << "," << (gate_enabled ? 1 : 0) << "\n";
    }
    ++window_idx;
  }
  return metadata_in;
}

uint32_t bouncer_pref::prefetcher_cache_fill(champsim::address /*addr*/, long, long, uint8_t /*prefetch*/, champsim::address evicted_addr,
                                             uint32_t metadata_in)
{
  // ownacc: a prefetched-but-never-demanded block that gets evicted is a wasted
  // (inaccurate/untimely) prefetch -> reward 0, attributed to its issuing set.
  if (reward_mode == 3 && !pf_pending.empty()) {
    const uint64_t eblk = champsim::block_number{evicted_addr}.to<uint64_t>();
    auto it = pf_pending.find(eblk);
    if (it != pf_pending.end()) { auditor.observe(static_cast<uint32_t>(eblk % N_SETS), 0.0); pf_pending.erase(it); }
  }
  return metadata_in;
}

void bouncer_pref::prefetcher_final_stats()
{
  if (log) log.close();
}
