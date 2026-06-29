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
// turf. The dueling "sets" are the REAL physical cache sets (not virtual
// buckets). Learned policy = SRRIP-style insertion; fallback pi0 = LRU; reward =
// cache hit (replacement's actual objective, so Delta-hat directly reflects
// competence). A corruption attack thrashes the learned arm (insert-at-evict).
//   BOUNCER_GATE=1|0  BOUNCER_ATTACK_WINDOW=N(-1)  BOUNCER_TAU/GAMMA/H  BOUNCER_LOG
class bouncer_repl : public champsim::modules::replacement {
  long NUM_SET = 0, NUM_WAY = 0;
  static constexpr uint32_t N_L = 64, N_F = 64;
  static constexpr int MAXRRPV = 3;
  static constexpr uint64_t WINDOW_ACCESSES = 800;
  bouncer::Bouncer* auditor = nullptr;

  std::vector<uint8_t> rrpv;          // SRRIP state per (set,way)
  std::vector<uint64_t> lru_stamp;    // LRU state per (set,way)
  uint64_t cycle = 0, access_count = 0, window_idx = 0;
  bool gate_enabled = true; long attack_window = -1;
  std::ofstream log;

  inline std::size_t idx(long set, long way) const { return (std::size_t)set * NUM_WAY + way; }
  // policy for this set: leader-C=SRRIP, leader-F=LRU, follower=gate-selected
  inline bool use_learned(long set) const {
    uint8_t tg = auditor->pool_tag((uint32_t)set);
    if (tg == 1) return true;
    if (tg == 2) return false;
    return gate_enabled ? auditor->use_learned((uint32_t)set) : true;
  }

public:
  explicit bouncer_repl(CACHE* cache);
  bouncer_repl(CACHE* cache, long sets, long ways);
  void initialize_replacement();
  long find_victim(uint32_t cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set,
                   champsim::address ip, champsim::address full_addr, access_type type);
  void update_replacement_state(uint32_t cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                champsim::address victim_addr, access_type type, uint8_t hit);
  void replacement_final_stats();
};

#endif
