#include "bouncer_repl.h"
#include <cstdlib>

bouncer_repl::bouncer_repl(CACHE* cache) : bouncer_repl(cache, cache->NUM_SET, cache->NUM_WAY) {}

bouncer_repl::bouncer_repl(CACHE* cache, long sets, long ways)
    : replacement(cache), NUM_SET(sets), NUM_WAY(ways),
      rrpv((std::size_t)sets * ways, MAXRRPV), lru_stamp((std::size_t)sets * ways, 0) {}

void bouncer_repl::initialize_replacement()
{
  if (const char* g = std::getenv("BOUNCER_GATE")) gate_enabled = (std::string(g) == "1");
  if (const char* a = std::getenv("BOUNCER_ATTACK_WINDOW")) attack_window = std::atol(a);
  double tau = 0.0, gamma = 0.04, H = 0.4;
  if (const char* t = std::getenv("BOUNCER_TAU")) tau = std::atof(t);
  if (const char* gm = std::getenv("BOUNCER_GAMMA")) gamma = std::atof(gm);
  if (const char* h = std::getenv("BOUNCER_H")) H = std::atof(h);
  auditor = new bouncer::Bouncer(bouncer::BouncerConfig{(uint32_t)NUM_SET, N_L, N_F, 64, tau, gamma, H});
  if (const char* l = std::getenv("BOUNCER_LOG")) { log.open(l); if (log) log << "window,delta_hat,state\n"; }
}

long bouncer_repl::find_victim(uint32_t, uint64_t, long set, const champsim::cache_block*,
                               champsim::address, champsim::address, access_type)
{
  if (use_learned(set)) {
    // SRRIP: evict a way at MAXRRPV; if none, age all and retry
    for (int iter = 0; iter < MAXRRPV + 1; ++iter) {
      for (long w = 0; w < NUM_WAY; ++w)
        if (rrpv[idx(set, w)] >= MAXRRPV) return w;
      for (long w = 0; w < NUM_WAY; ++w) rrpv[idx(set, w)]++;
    }
    return 0;
  } else {
    // LRU: evict the oldest stamp
    long victim = 0; uint64_t oldest = lru_stamp[idx(set, 0)];
    for (long w = 1; w < NUM_WAY; ++w)
      if (lru_stamp[idx(set, w)] < oldest) { oldest = lru_stamp[idx(set, w)]; victim = w; }
    return victim;
  }
}

void bouncer_repl::update_replacement_state(uint32_t, long set, long way, champsim::address, champsim::address,
                                            champsim::address, access_type type, uint8_t hit)
{
  if (type == access_type::WRITE && !hit) return;  // writeback fills don't train
  ++cycle;
  const bool learned = use_learned(set);
  const bool attacking = (attack_window >= 0) && ((long)window_idx >= attack_window);

  // reward = demand cache hit (replacement's objective)
  auditor->observe((uint32_t)set, hit ? 1.0 : 0.0);

  // LRU bookkeeping (always maintained so followers can switch policy safely)
  lru_stamp[idx(set, way)] = cycle;
  // SRRIP bookkeeping
  if (hit) {
    rrpv[idx(set, way)] = 0;                       // promote on hit
  } else {                                         // insertion on fill
    if (learned && attacking)
      rrpv[idx(set, way)] = MAXRRPV;               // CORRUPTED: insert at evict (thrash)
    else if (learned)
      rrpv[idx(set, way)] = MAXRRPV - 1;           // SRRIP long re-reference insert
    else
      rrpv[idx(set, way)] = MAXRRPV - 1;           // LRU arm also fills (stamp drives its victim)
  }

  if (++access_count % WINDOW_ACCESSES == 0) {
    bouncer::Gate g = auditor->end_window(false, true);
    if (log) {
      const char* sn[] = {"TRUSTED", "SUSPECT", "GATED", "PROBING"};
      log << window_idx << "," << auditor->last_delta_hat() << "," << sn[(int)g] << "\n";
    }
    ++window_idx;
  }
}

void bouncer_repl::replacement_final_stats() { if (log) log.close(); }
