# MLForSys 2026 adversarial-review response

This document records how the workshop branch responds to the supplied
adversarial review. The revision follows one rule: where the present artifact
can measure a claim, it does; where it cannot, the paper narrows or removes the
claim instead of substituting aspiration for evidence.

## 1. Constructed maximal shift and circular headline

The original maximal reversal remains as a transparent mechanism check, but it
is no longer the sole or headline operating point. A new fixed-parameter study
adds nine nested shift severities, a 16-window ramp, four cache/reuse-family
perturbations, and a Zipf/correlated-shift negative control. It reports misses
at 37.5% and 50% severity and an in-control gate at 12.5%, so the detector is no
longer presented as infallible. The paper now says explicitly that the 12 seeds
are repeats within one synthetic workload family.

The former 87.5% retention and recovery headlines are identified as the
expected 7/8 leader-allocation ceiling. Observed values remain checked only to
show that the implementation matches that design arithmetic.

Evidence:

- `experiments/exp_trained_characterization.py`
- `results/trained_characterization.json`
- `figures/trained_characterization.pdf`
- manuscript Section 3 and Appendix B

## 2. Detector theory and estimator bias

Equation 3 is now titled "expected-cost accounting," not a predictive safety
theorem. `N_ep` and `T_harm` are defined. The text states that `D` and `alpha`
are assumed or separately calibrated inputs and that the score CUSUM does not
inherit an exact Page/Lorden false-alarm guarantee under dependent leader
rewards. It also names the additional martingale or exchangeability conditions
an anytime-valid replacement would need.

The estimator decomposition now defines sampling, reward-locality, and
assignment-state bias separately. Simulator-only shadow replay recomputes both
policies on follower accesses without changing routing; against that target the
homogeneous estimator has mean bias -0.0003 and RMSE 0.0104. The Zipf negative control
then reverses the estimand sign (decision-weighted follower gap -0.193 versus
unweighted leader estimate +0.055) and alarms in only 4/12 runs. This shows,
rather than assumes, what happens when representative sampling fails.

The revision now repairs, rather than merely scopes, that controlled failure.
Pre-shift activity strata reserve one leader per arm in the hot eighth and seven
in the cold stratum, then weight within-stratum contrasts by follower request
mass. Mean bias falls from +0.247 to -0.0006 and detection rises from 4/12 to
12/12. This remains conditional on the measured strata capturing heterogeneity.

## 3. Missing baselines

The characterization adds all three requested diagnostics:

- a confidence-distribution monitor, whose total-variation signal is exactly
  zero because the model score is a deterministic function of the invariant PC;
- signed 8-bit and 10-bit PSEL references under abrupt and gradual shift;
- an adjacent-window A/B reference that makes its 50% learned exposure and
  temporal-stability assumption explicit.

PSEL is described as an architectural reference, not a statistically calibrated
safety baseline. The paper reports counter-width-dependent inertia without
claiming universal detector superiority. At `p=0.25`, Bouncer gates 7/12 while
PSEL-8 and PSEL-10 each gate 3/12, with conditional delays 4.33 and 15.33
windows. All rule delays use the same underlying gap crossing; PSEL has no `K`.

## 4. Reward locality and systems scope

The title now scopes the mechanism to partition-local learned controllers. The
paper distinguishes cache insertion/replacement, where decisions and hit rewards
share a set, from prefetching, where reward can cross partitions. The ChampSim
boundary paragraph now reports the formerly vague quantities: on one xalancbmk
trace, the candidate LIP insertion-3 and fallback SRRIP-HP insertion-2 policies
have whole-cache hit rates 0.336/0.048, while reseeding
attenuates mean leader difference to 0.005 and fixed leaders recover 0.23. These
are hand-designed LLC policies and are labeled one-trace, one-seed boundary
measurements, not validation of the fitted controller.

## 5. Secrecy and state preservation

Secrecy was removed from the abstract and mechanism headline. Fixed leaders in
the benign-shift experiment preserve state but make no security claim. A new
counter-like warm-up study quantifies the state problem: reset rotation measures
0.015 for a true 0.300 gap, fixed leaders measure 0.299, and shadow-updated state
measures 0.298. The model uses two 8-bit counters per set (128 B for 64 sets),
not duplicated cache contents or RTL.

The stateless trace replay also adds evidence-adaptive allocation: two leaders
per arm rotate through an eight-candidate cohort, expand under suspicious
evidence, and shrink after four stable windows. It averages 2.03 leaders per arm
with no clean alarms and matches or improves fixed-eight detection in the tested
shifted cells. This rotation result is not transferred to stateful cache contents.

## 6. Writing, positioning, and submission mechanics

The abstract now leads with the operational question and validity conditions.
Figure 1 identifies the DIP/set-dueling topology at the point where reviewers
first see it and states what Bouncer adds. The paper distinguishes follower
advantage, leader estimate, and bias terms; defines all variables in the cost
accounting; annotates the designed post-gate exposure; and adds related work on
controlled online experiments, interleaved evaluation, and time-uniform
confidence sequences.

The footer now names the NeurIPS 2026 Workshop on Machine Learning for Systems.
The build checks that main text ends on page 4, references start on page 5, the
footer is present, and no undefined citations remain.

## Reproduction status

From the repository root:

```bash
./run_ml4sys.sh
```

The final deterministic run passed 61/61 numerical claim checks and produced a
nine-page PDF: four main-text pages, two reference pages, and three appendix
pages. The workshop-only path was reproduced with Python 3.11.4, NumPy 1.26.4,
Matplotlib 3.8.4, and TeX Live 2026. The full repository requirements were not
needed for this path.

## Claims deliberately not added

This revision does not claim application-level generalization, IPC improvement,
calibrated sequential error control, hardware area/timing/energy, production
security, or full cache-content shadowing. A natural real-trace phase change,
additional learned policies, an explicitly stateful trained controller, and a
validated anytime-valid gate remain next experiments rather than hidden claims.
