// pythia_bouncer_shim.cc — example wiring of the Bouncer auditor into ChampSim's
// prefetcher module API, wrapping the Pythia RL prefetcher.
//
// This is illustrative against ChampSim's modern module interface (champsim
// commit-era `champsim::modules::prefetcher`). It does not compile outside a
// ChampSim tree; it shows exactly which hooks Bouncer needs. All auditor work is
// OFF the datapath: the hot path only reads a 2-bit pool tag and accumulates a
// reward that Pythia already computes.
//
//   #include "ooo_cpu.h"
//   #include "cache.h"
#include "bouncer.h"

namespace {
bouncer::Bouncer g_auditor(bouncer::BouncerConfig{});  // §12 operating point
uint64_t g_window_decisions = 0;
constexpr uint64_t WINDOW = 1u << 17;   // ~131072 decisions/window (m*n_sets)

// Map a memory access to a dueling "set". For Pythia this is the PC-hash bucket;
// for a replacement policy it is the cache set index.
inline uint32_t to_set(uint64_t pc, uint64_t addr) {
  return uint32_t((pc ^ (addr >> 6)) & (2048 - 1));
}
}  // namespace

// Called on every L2/LLC access. Bouncer decides whether Pythia or the safe
// fallback (next-line/off) drives this prefetch, and freezes Pythia's learning
// while GATED.
extern "C" uint32_t bouncer_pythia_operate(uint64_t addr, uint64_t pc,
                                           uint8_t cache_hit, uint8_t type,
                                           /*Pythia state*/ void* pythia) {
  uint32_t set = to_set(pc, addr);
  bool learned = g_auditor.use_learned(set);

  uint32_t pf_addr;
  if (learned) {
    pf_addr = pythia_predict(pythia, addr, pc);      // existing Pythia path
  } else {
    pf_addr = addr + 64;                             // safe fallback: next-line
    pythia_freeze_update(pythia);                    // online learning FROZEN
  }
  return pf_addr;
}

// Called when a prefetch's outcome is known (fill / late / useless). Pythia
// already computes this reward to drive its Q-update; Bouncer snoops it.
extern "C" void bouncer_pythia_reward(uint64_t addr, uint64_t pc, double reward) {
  uint32_t set = to_set(pc, addr);
  g_auditor.observe(set, reward);                    // bounded reward in [0, r_max]

  if (++g_window_decisions >= WINDOW) {
    g_window_decisions = 0;
    // Tier-A escalation comes from the always-on sketches (S_in/S_dec/S_res);
    // wired here from the management core. Stubbed True/False for the skeleton.
    bool escalate = tierA_escalated();
    bouncer::Gate g = g_auditor.end_window(escalate, !escalate);
    if (g == bouncer::Gate::GATED) qos_attribute_and_throttle();   // optional §7
  }
}

// --- stubs that the real integration provides --------------------------------
extern uint32_t pythia_predict(void*, uint64_t, uint64_t);
extern void     pythia_freeze_update(void*);
extern bool     tierA_escalated();
extern void     qos_attribute_and_throttle();
