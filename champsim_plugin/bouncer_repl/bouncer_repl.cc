#include "bouncer_repl.h"
#include <cstdlib>
#include <cstring>

bouncer_repl::bouncer_repl(CACHE* cache) : bouncer_repl(cache, cache->NUM_SET, cache->NUM_WAY) {}

bouncer_repl::bouncer_repl(CACHE* cache, long sets, long ways)
    : replacement(cache), NUM_SET(sets), NUM_WAY(ways),
      rrpv((std::size_t)sets * ways, MAXRRPV) {}

void bouncer_repl::initialize_replacement()
{
  if (const char* g = std::getenv("BOUNCER_GATE")) gate_enabled = (std::string(g) == "1");
  if (const char* a = std::getenv("BOUNCER_ATTACK_WINDOW")) attack_window = std::atol(a);
  if (const char* e = std::getenv("BOUNCER_ATTACK_END")) attack_end = std::atol(e);
  if (const char* nl = std::getenv("BOUNCER_NL")) N_L = (uint32_t)std::atol(nl);
  if (const char* nf = std::getenv("BOUNCER_NF")) N_F = (uint32_t)std::atol(nf);
  if (const char* w = std::getenv("BOUNCER_WINDOW")) WINDOW_ACCESSES = (uint64_t)std::atoll(w);
  if (const char* li = std::getenv("BOUNCER_LEARN")) learn_insert = std::atoi(li);
  if (const char* fi = std::getenv("BOUNCER_FALLBACK")) fallback_insert = std::atoi(fi);
  if (const char* f = std::getenv("BOUNCER_FORCE")) {
    if (std::strcmp(f, "fallback") == 0) force = Force::FALLBACK;
    else if (std::strcmp(f, "learned") == 0) force = Force::LEARNED;
  }
  double tau = 0.0, gamma = 0.04, H = 0.4, hys = 0.05;
  if (const char* t = std::getenv("BOUNCER_TAU")) tau = std::atof(t);
  if (const char* gm = std::getenv("BOUNCER_GAMMA")) gamma = std::atof(gm);
  if (const char* h = std::getenv("BOUNCER_H")) H = std::atof(h);
  if (const char* hy = std::getenv("BOUNCER_HYS")) hys = std::atof(hy);
  bouncer::BouncerConfig bc{(uint32_t)NUM_SET, N_L, N_F, 64, tau, gamma, H};
  bc.delta_hys = hys;
  if (std::getenv("BOUNCER_NORESEED")) bc.reseed_enabled = false;  // fixed leaders (DRRIP-style)
  auditor = new bouncer::Bouncer(bc);
  if (const char* l = std::getenv("BOUNCER_LOG")) {
    log.open(l);
    if (log) log << "window,delta_hat,sigma_dhat,rL,rF,cntL,cntF,degrading,state\n";
  }
}

// SRRIP victim: shift all up so the max RRPV becomes MAXRRPV, evict it. Both the
// learned arm and the fallback arm use SRRIP victim; they differ only in the
// INSERTION RRPV (set in replacement_cache_fill) -- this is the DRRIP set-dueling
// substrate, repurposed from policy selection to policy TRUST.
long bouncer_repl::find_victim(uint32_t, uint64_t, long set, const champsim::cache_block*,
                               champsim::address, champsim::address, access_type)
{
  // INJECTED DEGRADATION (labelled): on a learned set in its corruption phase the
  // learned controller is flipped to an anti-policy that evicts the HOTTEST (min
  // RRPV) block, killing the working set. This is a deliberately-bad policy on a
  // known phase -- guaranteed worse than the fallback on any trace, so Delta-hat
  // resolves the drop. (Only the learned arm degrades; the fallback pi0 is intact.)
  if (degrading() && use_learned(set)) {
    long victim = 0; uint8_t mn = rrpv[idx(set, 0)];
    for (long w = 1; w < NUM_WAY; ++w)
      if (rrpv[idx(set, w)] < mn) { mn = rrpv[idx(set, w)]; victim = w; }
    return victim;
  }
  // SRRIP victim: shift all up so the max RRPV becomes MAXRRPV, evict it.
  long victim = 0; uint8_t mx = rrpv[idx(set, 0)];
  for (long w = 1; w < NUM_WAY; ++w)
    if (rrpv[idx(set, w)] > mx) { mx = rrpv[idx(set, w)]; victim = w; }
  if (uint8_t bump = (uint8_t)(MAXRRPV - mx); bump)
    for (long w = 0; w < NUM_WAY; ++w) rrpv[idx(set, w)] = (uint8_t)(rrpv[idx(set, w)] + bump);
  return victim;
}

// Fires on EVERY demand access (hit OR miss) because we also provide
// replacement_cache_fill -> has_cache_fill==true (inc/cache.h:475). Without the
// fill hook the module sees hits only, reward collapses to 1, and Delta-hat is
// identically 0 (the prior 'dhat~0 on real HW' artifact). On a miss `way` is
// invalid (== NUM_WAY), so we index by way only on a hit.
void bouncer_repl::update_replacement_state(uint32_t, long set, long way, champsim::address, champsim::address,
                                            champsim::address, access_type type, uint8_t hit)
{
  if (type == access_type::WRITE) return;            // writebacks are not demand competence
  // reward = demand cache hit (replacement's objective). Real hit/miss stream, so
  // Delta-hat = r_bar_L - r_bar_F is a genuine competence signal.
  auditor->observe((uint32_t)set, hit ? 1.0 : 0.0);
  if (hit) rrpv[idx(set, way)] = 0;                  // promote on hit (way valid)

  if (++access_count % WINDOW_ACCESSES == 0) {
    const bool attacking = degrading();              // label for the window closing now
    bouncer::Gate g = auditor->end_window(false, true);
    if (log) {
      const char* sn[] = {"TRUSTED", "SUSPECT", "GATED", "PROBING"};
      log << window_idx << "," << auditor->last_delta_hat() << "," << auditor->sigma_dhat()
          << "," << auditor->last_rL() << "," << auditor->last_rF()
          << "," << auditor->last_cntL() << "," << auditor->last_cntF()
          << "," << (attacking ? 1 : 0) << "," << sn[(int)g] << "\n";
    }
    ++window_idx;
  }
}

// Insertion on a fill. `way` is the valid victim way. The arm is chosen by the
// gate/leader assignment; learned and fallback differ only in insertion RRPV.
void bouncer_repl::replacement_cache_fill(uint32_t, long set, long way, champsim::address, champsim::address,
                                          champsim::address, access_type type)
{
  if (type == access_type::WRITE) { rrpv[idx(set, way)] = MAXRRPV - 1; return; }  // writeback: distant
  // insertion arm (the corruption lives in find_victim, not here):
  rrpv[idx(set, way)] = (uint8_t)(use_learned(set) ? learn_insert : fallback_insert);
}

void bouncer_repl::replacement_final_stats() { if (log) log.close(); }
