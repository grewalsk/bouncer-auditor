#ifndef PREFETCHER_BOUNCER_PREF_H
#define PREFETCHER_BOUNCER_PREF_H

#include <cstdint>
#include <unordered_map>
#include <unordered_set>
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
  uint64_t window_accesses = WINDOW_ACCESSES;  // BOUNCER_WINDOW override (supplementary SNR probe)
  bool gate_enabled = true;
  long attack_window = -1;
  // N1 reward-fidelity isolation (BOUNCER_REWARD): which competence signal feeds Δ̂.
  //   0 = cachehit        : per-access cache-hit (the borrowed proxy; baseline)
  //   1 = ownpf           : controller's OWN reward, event-scoped coverage-accuracy
  //                         useful/(useful + uncovered-miss) ~ accuracy x timeliness
  //   2 = ownpf_peraccess : per-access useful_prefetch (sparse/diluted ablation)
  //   3 = ownacc          : faithful own prefetch ACCURACY, in-module tracked with
  //                         issue-time set attribution, demand-use=+1 / evict-unused
  //                         =0, pf_pending cleared at each reseed -> no cross-
  //                         partition credit leak; off arm earns 0 by construction.
  int reward_mode = 0;
  std::unordered_set<uint64_t> pf_pending;  // ownacc: prefetched-but-unused blocks (this window)
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
