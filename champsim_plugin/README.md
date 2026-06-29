# Bouncer ChampSim plugin (bridge to the systems evaluation)

This directory bridges the simulation-validated Bouncer auditor (`../bouncer/`) to
a real ChampSim deployment. The Python harness validates the **mechanism and its
guarantees** (estimator fidelity, safety floor, mimicry resistance, ARL constants);
this plugin is the **path to the IPC-on-SPEC numbers** an architecture reviewer
will want next. The C++ here mirrors the Python classes line-for-line in semantics
so the bridge is faithful, not a re-derivation.

## Why the Python results transfer

Bouncer's guarantees depend only on two environment-agnostic facts:

1. **Bounded per-decision reward** `r_t ∈ [0, r_max]`. Every target controller has
   such a reward already computed in silicon: prefetch *accuracy×timeliness*
   (Pythia computes this for its own RL update), cache *hit/miss*, *−latency*,
   *branch correct*.
2. **A randomly partitionable shared resource** for set-dueling. ChampSim caches
   are already sliced into sets; Pythia hashes PC into buckets; the memory
   controller has banks/channels.

Nothing in Lemma 6.1 or Prop 6.2 refers to a *specific* workload or controller —
only to `r_max`, the pool sizes `n_L,n_F`, decisions-per-window `m`, and the CUSUM
`(K,H)`. Those are exactly the knobs the Python sweep pins (`../experiments`), so
the operating point transfers; ChampSim supplies the absolute IPC scale.

## Mapping: Python class → ChampSim hook

| Python (`bouncer/`)            | ChampSim integration                                            |
|--------------------------------|-----------------------------------------------------------------|
| `SetDueling`                   | secret per-set/per-bucket pool tag, reseeded from an on-die RNG (reuse the sampler/ATD that DIP/DRRIP already carry) |
| reward `r_t`                   | tap the controller's existing reward signal (Pythia `pref_t` reward; replacement hit bit; scheduler latency) — **read-only, off critical path** |
| `Bouncer.step` (per window)    | a management-core / firmware routine fired every `~10^5–10^6` cycles (epoch grain); never on the datapath |
| `TierA` sketches               | small adjacent SRAM updated on a sampled `1/k` of accesses      |
| `GateFSM`                      | a 2-bit state register + comparators; on `GATED`, the controller's output is muxed to the fallback heuristic and online learning is frozen |

## Where to tap each controller

* **Pythia (prefetcher, lead controller).** Pythia already maintains a reward for
  each prefetch action to drive its Q-update (`bera2021pythia`). The Bouncer shim
  (`pythia_bouncer_shim.cc`) snoops that reward and the PC-hash bucket id, routes
  Leader-C buckets through Pythia and Leader-F buckets through next-line/off, and
  accumulates `r̄_L, r̄_F`. On `GATED`, `prefetcher_operate` returns the next-line
  (or no) prefetch and Pythia's table updates are suppressed.
* **Hawkeye/Glider (replacement).** Native set-dueling: dedicate sampled sets to
  the learned insertion policy vs RRIP; route the follower sets by the gate.
* **RL memory scheduler.** No clean counterfactual sampling on a shared command
  bus ⇒ `model_based=true` (`bouncer.h`): `r̄_F` is a model estimate of FR-FCFS,
  which weakens Prop 6.2 (documented as the "how far does it stretch" case).

## Files

* `bouncer.h` / `bouncer.cc` — the auditor: `SetDueling`, `LowerCusum`,
  `TwoSidedCusum`, `TierA`, `GateFSM`, `Bouncer`. Semantics identical to Python.
* `pythia_bouncer_shim.cc` — example wiring into ChampSim's prefetcher module API.
* `champsim_knobs.md` — the §12 hyperparameters as ChampSim build knobs.
* **`bouncer_pref/`** — the **real, working** ChampSim L1D prefetcher module
  (`bouncer_pref.{h,cc}` + `auditor.h`): set-dueling Δ̂ from per-set cache-hit
  rate, lower-CUSUM, gate FSM; learned = per-IP stride, fallback = prefetch-off,
  attack = cache-polluting corruption. Env-configured (`BOUNCER_GATE`,
  `BOUNCER_ATTACK_WINDOW`, `BOUNCER_TAU/GAMMA/H`, `BOUNCER_LOG`).
* **`setup_champsim.sh`** — one command: clone+build ChampSim, install the module,
  fetch a public SPEC trace, run the 4-config safety-floor study.

## Build / run — verified end to end

```
./setup_champsim.sh            # clones ChampSim, builds, fetches 619.lbm, runs the study
```

Verified result (SPEC CPU2017, L1D, Apple clang 17), `../results/champsim.json`.
The honest finding: **the auditor is only as good as its competence reward.** With
a per-set L1D cache-hit *proxy* (a poor stand-in for a prefetcher's real
latency/MLP benefit):
- `619.lbm`: the reward judges the stride prefetcher net-unhelpful and gates it
  off; a corrupting attack then costs the unguarded config **7.9% IPC** while
  Bouncer (already at the off floor) is unharmed — the **safety-floor cap** (not
  attack-specific detection; the gate engaged before the attack onset).
- `654.roms`: the same proxy under-credits a genuinely-helpful prefetcher (IPC
  1.14 vs off floor 1.01) and **over-gates** it (**11% clean tax**).

Both motivate feeding the auditor the controller's *own* in-silicon reward
(Pythia's accuracy×timeliness). The gate's TRUSTED→GATED transition dynamics are
shown where competence is controllable (the synthetic harness); these real runs
show end-to-end behavior under a realized-competence proxy.

## Status

**Working integration**, not just a skeleton: `bouncer_pref/` compiles into
ChampSim and runs on real SPEC traces (see above); `bouncer.{h,cc}` additionally
build standalone (`c++ -std=c++17 bouncer.cc -o bouncer_selftest`). The Python
harness still carries the *controlled* quantitative claims (multi-seed CIs,
sensitivity, adaptive adversaries); this plugin provides the real-simulator proof
of deployment. A full SPEC/GAP sweep with a timeliness-aware reward (matching the
controller's in-silicon reward) and the production controllers of Table I is the
remaining systems-evaluation step (P5).
