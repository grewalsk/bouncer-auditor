# Bouncer — E-loop hardening delta report

Branch `hardening/e-loop-keystone` off `main@114bc07`. This loop ran the
prescribed E1/E2/E3 → V1 → F1 → W1 DAG on top of the prior run's set-locality
reframe. Self-review honesty clause honored: every judgment gate was adjudicated by
a separate hostile-reviewer subagent (E3 critic, W1 critic), not by the producer.

## Keystone (E1): FELL BACK — KEYSTONE_REAL = false (honest negative + 3 real refinements)

The real-ChampSim **replacement** clean-case upside-capture trajectory did **not**
land. We did not fake it. But the investigation produced three *measured* findings
that strengthen the paper rather than just recording a null:

1. **The prior "dhat ≈ 0 on real HW" was a software artifact, not a sampling/horizon
   limit.** The `bouncer_repl` module lacked a `replacement_cache_fill` hook, so
   (per `inc/cache.h:475`, `has_cache_fill`) `update_replacement_state` fired on
   **hits only** → the demand-hit reward collapsed to 1 → `dhat` ≡ 0 identically.
   Adding the fill hook makes `dhat` a real nonzero signal.
2. **The whole-cache competence gap is real and large**: forcing every LLC set to
   the learned policy gives 33.6% hit rate vs 4.8% for the fallback (623.xalancbmk,
   FORCE mode).
3. **The secret per-epoch reseed — the mechanism that buys mimicry resistance —
   *confounds* the per-window estimate for a *stateful* reward.** Reseeded clean
   mean `dhat` = 0.005 (≈ noise) despite that 29-point gap; with **fixed leaders**
   (reseed off, DRRIP's own configuration) the *same* estimator resolves it
   (mean `dhat` = 0.23). A cache's reward is path-dependent: a set must run one
   policy consistently to accumulate the policy-specific state DRRIP's PSEL
   integrates, and reseeding erases it.

**New characterization result:** set-locality is **necessary but not sufficient** —
a secret, reseeded competence audit additionally requires a **(near-)stateless
reward** (paper `Remark 1`/`rem:stateless`). The synthetic harness's i.i.d.
per-decision reward satisfies this; a real cache does not at per-window grain. The
clean-case upside dynamics therefore remain scoped to the synthetic harness
everywhere in the manuscript.

Evidence (all regenerable): `results/champsim_e1/{dueling_reseeded,dueling_fixed_leader}.csv`,
`baselines.json`, `results/e1_keystone.json`, `figures/e1_replacement.pdf`,
`champsim_plugin/run_e1_replacement.sh`, fixed module `champsim_plugin/bouncer_repl/`.
Single-trace (xalancbmk) basis is disclosed in the text. Engineering bugs found and
fixed en route: the SRRIP/LIP policy choice, the corruption semantics
(evict-hottest), and an **ODR violation** (an out-of-sync `auditor.h` between the
two modules linked into one binary corrupted the RNG → SIGSEGV in `reseed`).
ChampSim compute spent ≈ 2.5 h of the 12 h cap.

## E2 (realizability): OPTION B (honest minimum)

Real-silicon adversarial **steering** is **not** demonstrated. Option A (a
co-located ChampSim polluter that steers the *real* controller to sub-resolution
harm) is a separate research contribution, infeasible in budget on single-core SPEC
traces. The paper now states plainly (threat model) that the real study uses an
*injected, controlled, labelled* degradation; the harness realizes steering via the
stress knob; real-HW steering realizability is future work. The guarantee is
degradation-source-agnostic — the open question is the attacker's realizability, not
the defense. Invariant enforced: nothing implies demonstrated real-HW steering.

## E3 (transfer-function sensitivity): PASS (scoped)

`experiments/exp_e3_sensitivity.py` re-runs the floor (P1) and both P4 headlines
across a family: collapse curve as clip and logistic (two slopes), IPC map steeper
and concave, a shifted fallback floor `q0 ∈ [0.4,0.6]`, and a **joint** `mu_C×IPC`
change. Result (`results/e3_sensitivity.json`, `PASS_shape_and_ipc=True`): the
qualitative guarantees are invariant (floor ≤ 0.9%, mimicry TPR 1.0 vs input-OOD 0,
secrecy TPR-vs-f shape preserved); only exact percentages move. The hostile E3
critic's objection (the original sweep held `q0` fixed and the attack far past the
crossing) was addressed by adding the `q0` sweep, the joint cell, and a
**detectability-vs-|Δ| curve** showing power tracks `|Δ|` (earned, not baked in).
**Documented scope:** robust to collapse *shape* + IPC map + floor; Tier-A
feature/confidence maps **not** swept (the competence-beats-input result is a Tier-B
property). Paper `Sec. eval-e3`, `figures/e3_sensitivity.pdf`.

## V1 (venue): MLSys

Trigger: `KEYSTONE_REAL == false` → `target_venue = MLSys` (not HPCA). MLSys
tolerates rigorous-but-synthetic evaluation; the runtime-assurance-for-learned-
controllers framing plus the set-locality + stateless-reward characterization is its
hook. Header retargeted; clean-case upside scoped to the synthetic harness in every
claim-bearing sentence.

## F1 (framing): set-locality + stateless-reward lead

Set-locality lead retained and sharpened with the stateless-reward condition
(abstract, intro contribution 1, `def:setlocal` + `rem:stateless`, eval, conclusion).
Positions explicitly against "monitoring wrapper, not a mechanism": the contribution
is the set-locality+stateless **characterization** (a mechanism boundary with a
proof and a measured failure mode), secret-dueling repurposed from selection to
trust, and the bounded-regret floor.

## W1 (writeup): final claim set + discharge table

Hostile W1 critic verdict: **5/6 CLEAN, 1 UNRESOLVED**. No overclaims found — every
disclaimer matches the on-disk evidence (no real clean-case validation implied; no
real-HW steering implied; abstract synthetic-vs-real split exact; headline % carry
the E3 scope without "map-independent"). The UNRESOLVED item (no hypothesis-discharge
table) is now **resolved**: `Table (tab:discharge)` maps every A1–A5 and Prop-1
premise to where it is established/measured/assumed, and explicitly records the one
premise that **fails, measured, on a real cache** — A1's *stateless* sub-condition.
Manuscript compiles clean, 14 pp, 0 undefined references.

### Final claim ledger (defended levels; Gap = Σ(asserted−defended) = 0)

| Claim | Defended | Notes |
|---|---|---|
| Set-locality characterization (+ stateless-reward refinement) | 3 | analytical + real prefetcher boundary + measured stateful-reward failure |
| Bounded-regret safety floor (union of audited domains, own reward) | 2 | Lemma 1 + synthetic P1 |
| Real downside cap (corrupted prefetcher → prefetch-off floor) | 2 | real, lbm |
| **Real clean-case upside trajectory (replacement)** | **1** | **scoped to synthetic; NOT claimed real** |
| Real replacement boundary finding (bug fix + gap + reseed-confounding) | 2 | measured, 1 trace, disclosed |
| Per-domain mimicry resistance (secret intact) | 2 | Prop 1 + synthetic P4 |
| Coverage hole (slow-bleed named, demonstrated) | 2 | fig:hole |
| General any-region security | 0 | refuted; not claimed |
| Headline map-robustness (E3) | 2 | shape+IPC+q0+joint; Tier-A not swept |
| Real-HW adversarial steering realizability | 0 | option B: not established, future work |

## UNRESOLVED for human review

- **A1 (stateless reward) is asserted-by-construction for the harness, not
  empirically discharged there.** The discharge table is honest (synthetic = holds
  by construction; real = fails, measured), but a reviewer may still want the
  harness's i.i.d. property itself stress-tested. Low risk; flagged.
- **E1 is single-trace (xalancbmk).** The reseed-confounding A/B is one trace + one
  reseeded-vs-fixed comparison. The mechanistic argument generalizes, but a
  multi-trace replication would harden it. Disclosed in text.
- **E3 does not sweep Tier-A feature/confidence maps.** Stated as a limitation, not
  closed.

## Revised odds (a guess, not a guarantee)

**MLSys ≈ 50–60%** (up from the diagnosis's "MLSys higher than HPCA's ~25%"). The
honesty is now airtight and the set-locality+stateless-reward characterization is a
genuine, non-obvious mechanism contribution with a proof *and* a measured failure
mode — which reads as depth, not weakness, to an MLSys committee. The ceiling is set
by the still-synthetic upside evidence and the single-trace real study. **HPCA
remains below the line (~25–30%)** without a real upside-capture result, exactly as
the diagnosis predicted. This is a guess.
