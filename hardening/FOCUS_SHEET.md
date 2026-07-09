# FOCUS SHEET — Bouncer

*Emitted by the FOCUS loop (methods-and-paper convergence). Structuring, sectioning,
venue choice, and prose polish are the human's next step ("structure after"). This
sheet + `state.json` are the machine-readable convergence state; `DELTA_REPORT.md` is
the honest delta.*

---

## THESIS (the one committed sentence)

**Set-locality — a learned microarchitectural controller's reward being attributable
to the same dueling set as its decision — is the condition under which secret reseeded
set-dueling gives a counterfactual-free, label-free realized-competence audit that caps
the controller to its vetted fallback under benign drift and adaptive mimicry; we prove
this, prove and validate in a *stateless synthetic* runtime-assurance harness that the
resulting bounded-regret floor and secrecy-purchased mimicry resistance hold (floor
within 0.63 %, clean tax 0.35 %, mimicry TPR 1.0 vs input-OOD 0.0), and show on real
ChampSim/SPEC that set-locality is *necessary but not sufficient* because the two
canonical controllers each break one condition — prefetching is not set-local (its
de-localized benefit over-gates a helpful prefetcher, and the controller's own reward
does not fix it) and cache replacement is set-local but *stateful* (the secret per-epoch
reseed that buys mimicry resistance confounds its per-window estimate) — so a faithful
audit additionally requires a near-stateless reward.**

Thesis id: **T-char** (the honest floor; needs no new experiment).
Fingerprint: `8c36d05576833603`.
Adjudicated by an independent thesis critic: `exceeds_evidence=false`, `underclaims_evidence=false`.
(T-monitor rejected — it states the fallback cap under adaptive mimicry as an unscoped
headline, implying a real guarantee `KEYSTONE_REAL=false` denies. T-hybrid subsumed by
T-char with explicit scoping.)

---

## REFERENCE CLASS (bar clearable = TRUE)

**Runtime assurance (A) + label-free deterioration monitoring (B).** Both families'
evaluation norm is *simulation + guarantees*, not a real-silicon performance win, so the
reproduced evidence clears the bar. Deltas vs the closest neighbors:

- **Simplex / Black-Box Simplex** (A, cited): Bouncer keeps the "simplicity controls
  complexity + bootstrap-to-baseline" posture but needs **no verified plant model / no
  reachability proof** — safety is a *measured relative-competence floor*, not a
  state-space invariant — and adds **secrecy-based mimicry resistance** an observable
  decision module lacks.
- **Shielding / safe-policy-improvement / conformal recovery-deadline** (A, cited):
  Bouncer certifies a *competence floor* (not a temporal-logic shield, a known cost
  function, or a recovery *time*), triggered by a counterfactual-free realized-reward
  estimate.
- **Suitability Filter (Pouget/Papernot)** (B, **now cited**): both are label-free
  margin tests (Δ<τ); Bouncer adds a **secret reseeded** sampler (mimicry resistance a
  margin proxy lacks), a ~336-byte hardware embodiment with a bounded-regret gate (vs a
  one-shot deploy/no-deploy decision), and the **set-locality** attributability condition.
- **Sequential Harmful Shift Detection Without Labels (Amoukou et al.)** (B, **now
  cited**): a proxy-error estimator + sequential FPR control = structurally *S_res* +
  one-sided CUSUM; Bouncer adds the per-set dueling proxy, secrecy, the hardware floor.
- **D3M** (B, **now cited**): sample-complexity for label-free TPR/FPR = the theory
  behind Bouncer's σ_Δ→H→D sizing.

Positioning fix applied: input-distribution OOD monitors demoted from "the alternative"
to "the weakest alternative"; the three family-B neighbors named with deltas in
`related_work.tex`. **Bib metadata for the 3 new family-B entries needs human
verification before submission** (out-of-scope "structure after").

---

## VENUE CLASS (consequence, not decided here)

**TMLR** — the venue whose bar the FOCUS pass actually clears. TMLR is claim/evidence-graded
with **no significance / no "is the win big enough" bar**, so removing overclaims is
load-bearing there. **MLSys does *not* group with TMLR here**: it is a *systems* venue and
carries the **same missing-real-win objection as HPCA/ISCA**, which the FOCUS pass did not
touch (no RUN forced, `KEYSTONE_REAL=false`, still no positive real result). Recorded as a
*consequence* of the committed thesis + reference class, not a driver.

- **TMLR** — the FOCUS fixes matter here (bar = correctness/clarity, which is now met).
- **MLSys** — down with the systems venues; the fixes help the claim/evidence story but the
  systems-thinness / missing-win objection persists.
- **HPCA/ISCA** — needs a real-silicon upside win `KEYSTONE_REAL=false` denies.

---

## CLAIM LEDGER (final) — `id : defended : reproduced : thesis_required`

| id | defended | reproduced | thesis_req | note |
|---|---|---|---|---|
| C_setlocal | 3 | ✓ | 3 | proven + real ChampSim both sides |
| C_stateless | 3 | ✓ | 3 | rem:stateless + e1_keystone (reseed 0.005 vs fixed 0.233) |
| C_floor | 2 | ✓ | 2 | Lemma 1 + P1 + theory (loose15.1/tight7.8/meas5.9) |
| C_mimicry | 2 | ✓ | 2 | Prop 1 + P4 secrecy ablation; per-domain, coverage hole named |
| C_estimator | 2 | ✓ | 1 | R²=0.997 controlled harness (scoped) |
| C_mimicry_vs_input | 2 | ✓ | 2 | TPR 1 vs 0; 0/50 definitional, earned = secrecy ablation |
| C_maprobust | 2 | ✓ | 1 | E3: floor/mimicry/secrecy invariant over mu_C/IPC/q0 |
| C_realdeploy_prefetch | 2 | ✓ | 2 | real prefetcher downside cap + over-gate (11% tax) |
| C_coverage_hole | 2 | ✓ | 0 | named open vuln; 1/√B; math-forbidden to close |
| C_detectpower_rolloff | 0 | ✗ | 0 | **RETREATED** — flat TPR, roll-off not exercised |
| C_overhead | 3(analytical) | ✓ | 0 | ~336 B; no-latency *by construction*, RTL future work |
| C_cusum_optimal | 1 | ✓ | 0 | **REDUCED** delay-optimal → near-optimal/well-motivated |
| C_triage | 2 | ✓ | 0 | attack-vs-drift 100% 5-fold CV (synthetic) |
| C_adaptive | 2 | ✓ | 0 | boiling-frog + PROBING-exploit bounded (synthetic) |

**Gap = Σ(asserted − defended) = 0.** Every `overclaim = false`. INV-5:
`defended ≥ thesis_required` for every claim.

---

## SURVIVING FIGURES (the ones the thesis actually needs)

1. **fig:e1repl** — real ChampSim *replacement*: secret reseed confounds the stateful
   reward (reseeded dhat≈noise vs fixed-leader resolves). *The strength-3 real boundary:
   set-local but stateful.*
2. **fig:champsim** — real ChampSim *prefetcher*: reliable floor downside cap + over-gate
   of a helpful prefetcher; own-reward does not fix. *The strength-3 real boundary: not
   set-local.*
3. **fig:floor** (P1) — the synthetic bounded-regret floor payload (detect→floor→re-trust).
4. **fig:p4** — synthetic mimicry survival + secrecy ablation (the secrecy-purchased
   mimicry resistance payload; TPR 1 vs 0; TPR-vs-leak-f).
5. **fig:hole** — the named coverage-hole open vulnerability (honesty boundary).

(P0/P2/P3/theory/adaptive/robust/E3 figures support but are not thesis-load-bearing.)

---

## QUEUED RUNS

- **R-latency** — `QUEUED_OPTIONAL`. Measure detection *latency* (not binary TPR) as
  |Δ|→σ_Δ, to exhibit the σ_Δ roll-off the flat-TPR E3 sweep could not.
  - Success: latency rises as the gap shrinks toward σ_Δ.
  - Abort: latency stays flat within tested range.
  - **Not required by the committed thesis** (T-char does not need a roll-off claim); the
    E3 overclaim was resolved by REDUCE, not RUN. Cheap synthetic if a human wants the
    positive version.

(R-reseed and R-multitrace from the seed backlog are **not** queued: the committed thesis
is T-char, which the current single-trace `e1_keystone` boundary result already supports
at strength 3; those runs would be needed only to escalate toward T-mech, which is out of
scope here since `KEYSTONE_REAL=false`.)

---

## OPEN HONEST BOUNDARIES

- **Coverage hole** — sub-resolution slow-bleed, δ_R^min ∝ 1/√B; *math-forbidden to fully
  close*; named, demonstrated (`fig:hole`).
- **Real-replacement single-trace** — `e1_keystone` is `623.xalancbmk` only; the
  reseed-confound / stateless-reward finding is not yet replicated on ≥3 cache-sensitive
  traces (R-multitrace unrun).
- **Real-hardware steering realizability NOT established** — the ChampSim study drives the
  auditor with an *injected, controlled, labelled* degradation; whether a co-located tenant
  can steer a specific deployed controller to sub-resolution harm on real silicon is future
  work.
- **Tier-A feature/confidence maps unswept** — E3 varies only the Tier-B collapse/IPC/q0
  maps; the "competence beats input" headline is a Tier-B property.
- **Overhead analytical** — ~336 B / no-added-latency is by construction; no RTL timing.
- **E3 detection-power roll-off predicted, not exercised** — the σ_Δ bound predicts a
  roll-off as |Δ|→σ_Δ, but the reduced-episode sweep stays >7σ from K (flat TPR 1.0);
  R-latency would exercise it.

---

## HALT

FOCUSED reached when: thesis fingerprint stable across a sweep · Gate R green · INV-1..5
green · this sheet on disk. See `state.json.focused` and `DELTA_REPORT.md`.
