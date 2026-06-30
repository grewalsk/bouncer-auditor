#ifndef REPLACEMENT_BOUNCER_REPL_H
#define REPLACEMENT_BOUNCER_REPL_H

#include <cstdint>
#include <vector>
#include <fstream>
#include <string>

#include "cache.h"
#include "modules.h"
#include "auditor.h"

// Bouncer auditor as a ChampSim LLC *replacement* module -- set-dueling's home
// turf. The dueling "sets" are the REAL physical cache sets. The substrate is
// DRRIP: both the learned controller and the safe fallback are RRIP insertion
// policies; they differ only in their insertion RRPV, and set-dueling estimates
// which is winning. Bouncer repurposes that substrate from policy SELECTION to
// policy TRUST. Reward = demand cache hit (set-local by construction), so
// Delta-hat directly reflects competence. A corruption attack flips the learned
// arm to an MRU-insert thrash policy on a known window range.
//
// IMPORTANT (ChampSim API): update_replacement_state fires on EVERY access only
// if the module ALSO provides replacement_cache_fill (inc/cache.h:475,
// has_cache_fill). Without the fill hook the module sees hits only, the demand-hit
// reward collapses to 1, and Delta-hat is identically 0 -- the 'dhat~0 on real
// HW' artifact. We implement BOTH hooks.
//
// Env levers (a single build sweeps the whole operating point):
//   BOUNCER_GATE=1|0        gate on / off (off == ungated learned baseline)
//   BOUNCER_ATTACK_WINDOW=N degradation onset window (-1 = none)
//   BOUNCER_ATTACK_END=N    degradation end window (-1 = never; set for a
//                           transient phase so the gate can re-trust via PROBING)
//   BOUNCER_NL / BOUNCER_NF leader pool sizes (more leaders == more samples/win)
//   BOUNCER_WINDOW          demand accesses per audit window
//   BOUNCER_LEARN           learned insertion RRPV (MAXRRPV=LIP, MAXRRPV-1=SRRIP-HP)
//   BOUNCER_FALLBACK        fallback insertion RRPV (default MAXRRPV-1 = SRRIP-HP)
//   BOUNCER_TAU/GAMMA/H/HYS  gate threshold / CUSUM slack / CUSUM height / re-trust band
//   BOUNCER_FORCE=learned|fallback   pure-policy IPC baselines (no dueling/gate)
//   BOUNCER_LOG=path        per-window CSV
class bouncer_repl : public champsim::modules::replacement {
  long NUM_SET = 0, NUM_WAY = 0;
  uint32_t N_L = 64, N_F = 64;        // BOUNCER_NL / BOUNCER_NF
  uint64_t WINDOW_ACCESSES = 800;     // BOUNCER_WINDOW
  static constexpr int MAXRRPV = 3;
  int learn_insert = MAXRRPV;         // BOUNCER_LEARN: MAXRRPV=LIP (aggressive protect)
  int fallback_insert = MAXRRPV - 1;  // BOUNCER_FALLBACK: SRRIP-HP (safe heuristic)
  bouncer::Bouncer* auditor = nullptr;

  std::vector<uint8_t> rrpv;          // SRRIP/RRPV state per (set,way)
  uint64_t access_count = 0, window_idx = 0;
  bool gate_enabled = true;
  long attack_window = -1, attack_end = -1;
  enum class Force { NONE, FALLBACK, LEARNED } force = Force::NONE;
  std::ofstream log;

  inline std::size_t idx(long set, long way) const { return (std::size_t)set * NUM_WAY + way; }
  // arm for this set: leader-C=learned, leader-F=fallback, follower=gate-selected.
  inline bool use_learned(long set) const {
    if (force == Force::FALLBACK) return false;
    if (force == Force::LEARNED) return true;
    uint8_t tg = auditor->pool_tag((uint32_t)set);
    if (tg == 1) return true;
    if (tg == 2) return false;
    return gate_enabled ? auditor->use_learned((uint32_t)set) : true;
  }
  inline bool degrading() const {
    if (attack_window < 0) return false;
    if ((long)window_idx < attack_window) return false;
    if (attack_end >= 0 && (long)window_idx >= attack_end) return false;
    return true;
  }

public:
  explicit bouncer_repl(CACHE* cache);
  bouncer_repl(CACHE* cache, long sets, long ways);
  void initialize_replacement();
  long find_victim(uint32_t cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set,
                   champsim::address ip, champsim::address full_addr, access_type type);
  void update_replacement_state(uint32_t cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                champsim::address victim_addr, access_type type, uint8_t hit);
  void replacement_cache_fill(uint32_t cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                              champsim::address victim_addr, access_type type);
  void replacement_final_stats();
};

#endif
