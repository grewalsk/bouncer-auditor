#ifndef PREFETCHER_BOUNCER_PREF_H
#define PREFETCHER_BOUNCER_PREF_H

#include <cstdint>
#include <unordered_map>
#include <fstream>
#include <string>

#include "address.h"
#include "champsim.h"
#include "modules.h"
#include "auditor.h"

// Bouncer auditor as a ChampSim L2C prefetcher module.
//   * "learned" controller   = per-IP stride prefetcher
//   * safe fallback pi0       = next-line
//   * reward                  = prefetch usefulness (useful_prefetch flag)
//   * secret set-dueling Δ̂ + lower-CUSUM + gate FSM (reused, validated)
// Env-configured so all study configs come from one binary:
//   BOUNCER_GATE=1|0           : auditor gates (1) or always-learned (0)
//   BOUNCER_ATTACK_WINDOW=N    : window index at which the learned policy is
//                                corrupted into useless prefetches (-1 = never)
//   BOUNCER_LOG=path           : per-window Δ̂ / gate-state CSV
struct bouncer_pref : public champsim::modules::prefetcher {
  static constexpr uint32_t N_SETS = 2048, N_L = 32, N_F = 32;
  static constexpr uint64_t WINDOW_ACCESSES = 40000;  // ~ m≈12 per set/window
  static constexpr int64_t BAD_STRIDE = 991;          // corrupt prefetch offset

  bouncer::Bouncer auditor{bouncer::BouncerConfig{N_SETS, N_L, N_F}};

  struct strider { uint64_t last_block = 0; int64_t last_stride = 0; bool valid = false; };
  std::unordered_map<uint64_t, strider> stride_table;

  uint64_t access_count = 0, window_idx = 0;
  bool gate_enabled = true;
  long attack_window = -1;
  std::string log_path;
  std::ofstream log;

  using champsim::modules::prefetcher::prefetcher;

  void prefetcher_initialize();
  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type,
                                    uint32_t metadata_in);
  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way, uint8_t prefetch, champsim::address evicted_addr, uint32_t metadata_in);
  void prefetcher_final_stats();
};

#endif
