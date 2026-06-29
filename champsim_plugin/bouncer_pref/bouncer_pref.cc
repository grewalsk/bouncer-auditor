#include "bouncer_pref.h"
#include "cache.h"
#include <cstdlib>

void bouncer_pref::prefetcher_initialize()
{
  if (const char* g = std::getenv("BOUNCER_GATE")) gate_enabled = (std::string(g) == "1");
  if (const char* a = std::getenv("BOUNCER_ATTACK_WINDOW")) attack_window = std::atol(a);
  // env-tunable trust threshold / CUSUM (reward here = prefetch-usefulness rate)
  double tau = 0.04, gamma = 0.04, H = 0.20;
  if (const char* t = std::getenv("BOUNCER_TAU")) tau = std::atof(t);
  if (const char* gm = std::getenv("BOUNCER_GAMMA")) gamma = std::atof(gm);
  if (const char* h = std::getenv("BOUNCER_H")) H = std::atof(h);
  auditor = bouncer::Bouncer(bouncer::BouncerConfig{N_SETS, N_L, N_F, 64, tau, gamma, H});
  if (const char* l = std::getenv("BOUNCER_LOG")) { log_path = l; log.open(log_path); if (log) log << "window,delta_hat,state,gate\n"; }
}

uint32_t bouncer_pref::prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool /*useful_prefetch*/,
                                                access_type /*type*/, uint32_t metadata_in)
{
  const uint64_t blk = champsim::block_number{addr}.to<uint64_t>();
  const uint32_t set = static_cast<uint32_t>(blk % N_SETS);

  // reward = cache-hit (the metric prefetching moves). Δ̂ = hit-rate(learned
  // sets) - hit-rate(off sets) isolates the prefetcher's contribution because the
  // secret L/F partition is random. A corrupted (polluting) prefetcher drives the
  // learned-set hit rate BELOW the off floor -> Δ̂ < 0 -> gate.
  auditor.observe(set, cache_hit ? 1.0 : 0.0);

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
    if (st.valid && stride != 0 && stride == st.last_stride && !attacking) {  // degree 2 on confident stride
      prefetch_line(champsim::address{champsim::block_number{addr} + 2 * pf_stride}, light, 0);
    }
  }

  // update stride tracker
  st.last_stride = stride; st.last_block = blk; st.valid = true;

  // --- window boundary: run the Tier-B confirmer + gate ---
  if (++access_count % WINDOW_ACCESSES == 0) {
    // Tier-A is not wired in this minimal module; the background Tier-B CUSUM
    // gates directly (the validated mimicry-safe path).
    bouncer::Gate g = auditor.end_window(/*tierA_escalate=*/false, /*tierA_clear=*/true);
    if (log) {
      const char* sn[] = {"TRUSTED", "SUSPECT", "GATED", "PROBING"};
      log << window_idx << "," << auditor.last_delta_hat() << ","
          << sn[(int)g] << "," << (gate_enabled ? 1 : 0) << "\n";
    }
    ++window_idx;
  }
  return metadata_in;
}

uint32_t bouncer_pref::prefetcher_cache_fill(champsim::address, long, long, uint8_t, champsim::address, uint32_t metadata_in)
{
  return metadata_in;
}

void bouncer_pref::prefetcher_final_stats()
{
  if (log) log.close();
}
