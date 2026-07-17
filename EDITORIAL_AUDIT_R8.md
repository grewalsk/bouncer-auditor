# Bouncer R8 editorial and technical audit

Status: revised source on branch `editorial/tmlr-r8`. The authoritative paper is
`paper/bouncer.tex` and the compiled artifact is `paper/bouncer.pdf`.

## 1. Reproduction record

The pinned pre-edit commit `973fa10` was reproduced independently in an isolated
clone. `./run_all.sh` exited successfully, its audit passed 36/36, all regenerated
JSON files were byte-identical to the commit, and the rendered PDF text matched
the committed PDF. The original PDF had 34 pages. This established reproducibility
of the submitted artifact; it did not establish that the implementation matched
the causal claims.

The revised implementation repairs two independently discovered defects:

- End-of-window evidence previously changed the routing of that same window.
  `bouncer/bouncer.py:93-157` now returns pre-update routing as `state` and the
  post-audit routing as `state_next`. `bouncer/simulate.py:80-117` deploys the
  pre-update state. The invariant at `experiments/test_invariants.py:55-66`
  exercises this boundary.
- The warm-up experiment retained stale policy history for nonsampled slices.
  `experiments/exp_warmup_predictor.py:40-64` now resets nonsampled slices to
  cold state and increments only immediately consecutive assignments.

The revised numeral audit passes 40/40. It now pins the causal P1/E3 values, the
warm-up values, the sensitivity and adaptive-timing values, and the proposed
storage budget (`scripts/check_paper_numbers.py:131-264`). Final end-to-end and
layout verification is recorded at the end of this file after the release build.

Independent recomputations:

- Proposition 1 exact DP: `125/32768 = 0.003814697265625` no-alarm probability.
- High-average probability for the same support: `2517/65536 = 0.0384063720703125`.
- Corrected Hoeffding envelope: `0.7261490370736908`.
- Floor mean: `(32/2048)(0.5-0.156)(1.4)/1.3 = 0.578846%`.
- CUSUM zero-drift limit: `b^2`, now implemented at `bouncer/cusum.py:108-110`.

## 2. Section-by-section before/after record

Counts below are TeXcount prose + headings + captions; math-token accounting is
reported separately in the whole-paper total. “Removed” means redundant prose or
an inaccurate claim recorded in Section 9, not silent scientific deletion.

| Section | Before | After | Net | Revision and meaning-preservation result |
|---|---:|---:|---:|---|
| Abstract/front matter | 715 | 367 | -348 | Rebuilt as a five-paragraph claim map: formal result, controller-side conditions, synthetic evidence, ChampSim boundaries, and implementation scope. All load-bearing results remain; 1-window and 336-byte claims were corrected. |
| Introduction | 1,136 | 1,110 | -26 | Reduced repeated motivation and kept the exact contribution/scope boundary. |
| Formal setting | 620 | 647 | +27 | Added audit-window reward units, representative sampling, and an explicit reseed-identifiability definition. |
| Threat model | 414 | 317 | -97 | Separated measurement, secrecy, denial-of-service, and poisoning assumptions; removed duplicate prose. |
| Architecture | 305 | 292 | -13 | Simplified the state-machine narrative and distinguished off-path epoch work from remaining per-access routing. |
| Tier-B | 279 | 313 | +34 | Added the missing effective-independence premise and standardized the audit-window index `w`. |
| Tier-A | 201 | 224 | +23 | Replaced the nonexistent quantile/energy-distance and 16-weight descriptions with the released dense-projection and 18-coefficient implementation. |
| Guarantees | 1,888 | 1,520 | -368 | Split assumptions, proof steps, and scope. Defined false-alarm episode cost. Preserved the three-term Lemma, exposure-only Azuma refinement, and two-part Proposition. Removed unsupported leak/tight-bound generalizations. |
| Triage | 135 | 135 | 0 | No substantive edit required. |
| Controller instantiation | 170 | 141 | -29 | Scoped each abstraction and removed repeated acronym explanations. |
| Methodology | 503 | 281 | -222 | Reorganized around formal premises, controlled evidence, operating point, and real-simulator boundary. Defined `q0` and the IPC mapping before numeric use. |
| Evaluation | 4,678 | 4,184 | -494 | Added a roadmap; split P1; scoped P3/P4; corrected all causal values; compressed revision-history narration; separated proved loose bound from descriptive tracker. |
| Overhead | 155 | 122 | -33 | Recomputed released dimensions as 404 B and explicitly labeled quantization/RTL timing/energy unmeasured. |
| Related work | 1,066 | 866 | -200 | Shortened comparison prose, corrected practical-versus-idealized D3M scope, and removed unsupported hardware finality. |
| Discussion | 294 | 302 | +8 | Made representative sampling, set-locality, and reseed-identifiability jointly visible. |
| Conclusion | 252 | 280 | +28 | Matched body scope; added representative sampling and unmeasured implementation qualifications. |
| Broader impact | 150 | 150 | 0 | No substantive edit required. |
| Reproducibility | 161 | 189 | +28 | Distinguished synthetic regeneration from committed ChampSim-log plotting. |
| Artifact appendix | 150 | 149 | -1 | Scoped the setup scripts to the actual `lbm` and single-trace replacement cases. |

## 3. Definition ledger

| Term | Definition / first use | Aliases removed | Status |
|---|---|---|---|
| Learned controller `C` | Controller under audit; `paper/bouncer.tex:199-214` | “learned policy” retained only descriptively | Defined |
| Fallback `pi0` | Vetted comparison policy; `paper/bouncer.tex:199-214` | baseline/floor distinguished from reward | Defined |
| Audit window | Set of decisions normalized to one reward unit; `paper/bouncer.tex:205-214` | epoch is reserved for an assignment lifetime | Defined |
| Competence gap `Delta_w` | Window reward of `C` minus fallback; `paper/bouncer.tex:211-219` | uppercase `W` index removed from Tier-B equation | Defined |
| Set-locality | Decision and credited outcome share a dueling set; `paper/bouncer.tex:230-251` | localizability used only as ordinary description | Defined |
| Representative sampling | Pool estimator targets decision-weighted deployed traffic; `paper/bouncer.tex:253-260` | none | Defined |
| Reseed-identifiability | Sign of the measured contrast survives secret reassignment; `paper/bouncer.tex:262-287` | “statelessness requirement” removed | Defined |
| Leader-L / Leader-F / follower | Secret policy pools; `paper/bouncer.tex:375-388` | Leader-C normalized to Leader-L in prose | Defined |
| CUSUM | One-sided cumulative-sum detector; `paper/bouncer.tex:407-420` | repeated long expansions removed | Defined |
| Tier-A / Tier-B | Tripwire and competence-confirmation tiers; `paper/bouncer.tex:323-362` | hot/warm labels removed | Defined |
| Drop episode | Maximal run with `Delta_w < tau`; `paper/bouncer.tex:454-457` | attack episode kept only where labels are empirical | Defined |
| Fully-open window | Controller runs on all followers in TRUSTED/SUSPECT; `paper/bouncer.tex:454-457` | detection delay alone no longer substituted for it | Defined |
| Audit exposure | Resource share still running `C` during a drop; `paper/bouncer.tex:482-490` | “floor leakage” avoided | Defined |
| Coverage hole | Harm below finite per-domain resolution; `paper/bouncer.tex:652-674` | leakage kept as a distinct failure axis | Defined |
| Descriptive tracker | Realized gap/occupancy plus approximate mean delay; `paper/bouncer.tex:1095-1111` | “tight bound/envelope” removed | Defined |

## 4. Notation ledger

| Symbol | Meaning | Domain / units | First use | Status |
|---|---|---|---|---|
| `r_t^pi` | Per-decision bounded reward | `[0,r_max]` | `paper/bouncer.tex:199-214` | Consistent |
| `bar r_w^pi` | Window-normalized mean reward | reward/window | `paper/bouncer.tex:205-214` | Consistent |
| `Delta_w` | Competence advantage | reward/window | `paper/bouncer.tex:211-219` | Consistent |
| `dhat_w` | Dueling estimate of `Delta_w` | reward/window | `paper/bouncer.tex:383-399` | Consistent |
| `m_eff` | Effective independent samples per set/window | positive real count | `paper/bouncer.tex:390-399` | Added premise |
| `n_L,n_F` | Leader pool sizes | positive integers | `paper/bouncer.tex:375-389` | Consistent |
| `sigma_Delta` | Standard-deviation upper bound | reward/window | `paper/bouncer.tex:390-405` | Conditional on `m_eff` |
| `tau` | Trust threshold | reward/window | `paper/bouncer.tex:211-219` | Consistent |
| `gamma` | Detector design margin | positive reward margin | `paper/bouncer.tex:407-413` | Defined before use |
| `K` | CUSUM reference, `tau+gamma/2` | reward/window | `paper/bouncer.tex:407-413` | Consistent |
| `H` | CUSUM alarm threshold | cumulative reward units | `paper/bouncer.tex:407-413` | Consistent |
| `D` | Expected fully-open windows per drop episode | windows/episode | `paper/bouncer.tex:454-457` | Not conflated with mean-delay approximation |
| `alpha` | Marginal false-alarm probability/window | probability | `paper/bouncer.tex:459-460` | Consistent |
| `c_sw` | Total transient regret per false-alarm episode | reward | `paper/bouncer.tex:462-463` | Corrected |
| `phi_G,phi_P` | GATED/PROBING exposure fractions | fraction in [0,1] | `paper/bouncer.tex:482-490` | Consistent |
| `T_att` | Windows within drop episodes | nonnegative integer | `paper/bouncer.tex:489-490` | Consistent |
| `R` | Contested/audited domain | nonempty set of resource slices | `paper/bouncer.tex:581-585` | Consistent |
| `beta` | Exchangeability bias bound | nonnegative reward | `paper/bouncer.tex:585-594` | Consistent |
| `epsilon` | Mean degradation margin | positive reward | `paper/bouncer.tex:599-608` | Consistent |
| `delta_R^min(B)` | Finest auditable per-domain gap at budget `B` | reward | `paper/bouncer.tex:652-670` | Conditional on effective independence |
| `q0` | Normalized fallback reward rate | [0,1] | `paper/bouncer.tex:742-760` | Defined before P1 arithmetic |

## 5. Claim-evidence ledger

| Claim | Type | Verdict | Evidence and reproduced number | Scope / qualification |
|---|---|---|---|---|
| Three-term Lemma 1 | Mathematical | SUPPORTED | Statement/proof at `paper/bouncer.tex:501-538`; persistent regression at `experiments/exp_floor_longattack.py:71-116` gives measured 12.34–12.39, obsolete two-term 2.52, loose plug-in 123.6 | Expected regret under A1–A6; numerical plug-in additionally uses measured/assumed `D` |
| Exposure high-probability term | Mathematical | SUPPORTED | `paper/bouncer.tex:540-557`; reproduced T=240 envelope 38.87 with empirical coverage 1.0 | Exposure only; adaptive traffic must be blind to current uniform secret draw |
| P1 causal detection | Empirical | SUPPORTED | `paper/bouncer.tex:819-846`; `results/p1.json` gives 2 windows and 15-window re-trust | Seeded synthetic operating point |
| Steady floor arithmetic | Methodological | SUPPORTED | `paper/bouncer.tex:827-838`; calculation 0.578846%, measured mean 0.580455%, worst 0.635338% | Synthetic reward-to-IPC map, not a universal predictor |
| Descriptive “tight” form | Mathematical/empirical | SCOPED | `paper/bouncer.tex:1095-1111` and `results/floor_longattack.json`: tracker 12.29 under measured 12.34–12.39 | Explicitly not a bound or expectation guarantee |
| Proposition 1 expectation form | Mathematical | SUPPORTED | `paper/bouncer.tex:581-618` | Unconditional expectation; representative/exchangeable within-domain sampling and intact secret |
| Proposition 1 sustained form | Mathematical | SUPPORTED | `paper/bouncer.tex:599-631`; exact DP 0.0038147 and exhaustive 2,068 no-alarm paths | Requires conditional temporal independence and average mean below `tau-epsilon` |
| E3 drift and R-latency | Empirical | SUPPORTED | `paper/bouncer.tex:1016-1058`; `results/rlatency.json`: sigma 0.015625/0.03125, drift 3.2/1.6, latency 2.0→13.875, TPR@10 1→0, TPR@20 1 | Eight tested gaps, 40 seeds/cell, 40-window horizon |
| Warm-up generality mechanism | Empirical/interpretive | SUPPORTED AS SCOPED | `paper/bouncer.tex:984-1008`; corrected run: multiplicative 95%→5%, additive remains 0.300 ±0.0013 | Synthetic slice model only; no real predictor evidence |
| Fixed set-heterogeneity robustness | Empirical | SUPPORTED AS SCOPED | `paper/bouncer.tex:963-981`: TPR 1, floor 0.59–0.64%, latency 2.0→2.7 | Does not test temporal dependence or remove `m_eff` premise |
| Adaptive timing result | Empirical | SUPPORTED AS SCOPED | `paper/bouncer.tex:1061-1083`; 8-window boiling latency, 16.9% harmed windows | Constructed finite-horizon strategies, not a theorem |
| Tier-A implementation and storage | Methodological | SUPPORTED AS PROPOSAL | `bouncer/tier_a.py:1-100`; `experiments/exp_p2_overhead_roc.py:118-149`; 404 B, 0.1541% | Floating-point reference; quantization, RTL area/energy/timing unmeasured |
| ChampSim boundary evidence | Empirical | SUPPORTED AS SCOPED | `paper/bouncer.tex:1192-1343` and committed logs; arithmetic for lbm 7.9%, roms 11.2%, replacement dhat 0.005 vs 0.233 | Figures rebuild from committed logs; only lbm/single replacement scripts automated; not full validation |
| Some TMLR subcommunity would find the work interesting | Interpretive | SUPPORTED | Formal runtime assurance, sequential detection, adaptive-systems monitoring, and ML-for-systems boundary results | Criterion A asks interest, not novelty/significance |

## 6. Proof certificates

### Lemma 1: expected safety floor — PROOF VALID

- Statement: expected window-normalized regret is at most detection/re-trust,
  audit exposure, and false-alarm transient terms.
- Assumptions: A1 bounded window reward; A2 expected fully-open windows; A3
  marginal false-alarm probability; A4 total cost per false-alarm episode; A5
  horizon/episode counts; A6 traffic-blind uniform secret exposure.
- Skeleton: partition windows; charge fully-open windows by `r_max`; charge
  traffic-weighted exposure using each set’s marginal exposure probability;
  charge expected alarm count by linearity; discard nonpositive open-controller
  regret.
- Failure points checked: concentrated traffic, repeated alarms, false re-trust,
  and nonindependent windows. The proof needs only the stated marginals.
- Edge case: a hot set can incur one full-window loss; this refutes a pointwise
  `phi_P` bound but not the expectation.
- Certificate: valid as written at `paper/bouncer.tex:501-538`.

### Exposure refinement — PROOF VALID

- Statement: only cumulative audit-exposure regret has the printed
  high-probability envelope.
- Assumptions: current secret draw is uniform conditional on the past; adversary
  traffic is blind to it; each exposure increment is in `[0,r_max]`.
- Skeleton: subtract conditional means to form martingale differences; their
  conditional range width is `r_max`; apply Hoeffding–Azuma and add the conditional
  mean sum.
- Edge case: gate-history-adaptive traffic is permitted; current-assignment-aware
  traffic is not.
- Certificate: valid at `paper/bouncer.tex:540-557`.

### Proposition 1(i) — PROOF VALID

- Statement: an input-only strategy with expected audit gap at least `tau` gives
  expected follower reward at least fallback + `tau-beta`.
- Assumptions: hidden uniform within-domain pools and exchangeability bias at most
  `beta`.
- Skeleton: exchange Leader-L and follower expectations up to `b_R`, substitute
  the expected gap, and rearrange.
- Edge case: conditioning on realized evasion selects favorable audit noise; the
  proposition explicitly excludes that inference.
- Certificate: valid at `paper/bouncer.tex:581-618`.

### Proposition 1(ii) — PROOF VALID

- Statement: under a sustained mean deficit, block no-alarm probability is at
  most the corrected range-`2r_max` Hoeffding envelope.
- Assumptions: conditional independence across windows, bounded range, average
  conditional mean at most `tau-epsilon`, and `W >= 2H/gamma`.
- Skeleton: no reset occurs on a no-alarm block; the reflected CUSUM dominates
  the unreflected cumulative sum; strict alarm `C>H` means no alarm gives `C<=H`;
  hence the block mean is at least `K-H/W>=tau`; Hoeffding bounds that event.
- Edge cases: equality `C=H` correctly does not alarm; exact DP and exhaustive
  implementation-order sweep agree.
- Certificate: valid at `paper/bouncer.tex:599-631`.

## 7. Whole-paper word and page delta

- Baseline TeXcount: 14,059 tokens/words under the project’s `-inc -sum -brief`
  convention.
- Revised TeXcount: 12,259.
- Net: -1,800 (-12.8%).
- Baseline PDF: 34 pages.
- Revised PDF before final release rebuild: 33 pages.
- No page limit is specified in the supplied prompt; the revision is shorter and
  retains TMLR formatting.

## 8. Unresolved scientific and artifact issues

1. The 16-bit storage count is a proposal. Quantized numerical fidelity, RTL
   area, energy, and timing remain unmeasured.
2. The full three-trace ChampSim study is represented by committed logs and is
   not regenerated by one release command. The setup script runs the `lbm` case;
   the replacement script runs one `xalancbmk` case.
3. Representative sampling, set-locality, and reseed-identifiability are necessary
   scope conditions for this audit design, not a proved general sufficiency
   theorem.
4. The slow-bleed coverage hole, temporal-correlation inflation of false re-trust,
   and assignment leakage remain explicit limitations.
5. Real predictor rewards and a real-system clean-case transition remain untested.

Each issue is stated in the paper; none is used as a hidden premise for a broader
claim.

## 9. Information removed, moved, or corrected

- No supported empirical result, formal assumption, caveat, negative result,
  citation, or reproducibility detail was silently removed.
- Repeated revision-history narration was moved into this audit; the tests and
  reproduced numbers remain in the paper.
- Incorrect claims were not “preserved” as facts: same-window routing, stale
  warm-up state, `b^2/2` at zero drift, the 1-window/14-window values, the
  28/36 sensitivity count, the 8.6% harmed-window value, the “tight bound,” the
  336-byte code match, zero-latency language, and full ChampSim regeneration were
  corrected and recorded here.
- The pinned pre-edit commit `973fa10` is the authoritative baseline for direct
  before/after inspection and the Git diff is the paragraph-level change record.
  Local render and baseline files under `tmp/` are intentionally not versioned.

## 10. Adversarial TMLR verdict

- Criterion C — are claims supported or scoped: **YES after this revision**.
  The formal statements now include their needed premises; affected experiments
  were corrected and regenerated; implementation and artifact claims match the
  released code. Remaining gaps are explicit limitations.
- Criterion A — would some ML subcommunity find it interesting: **YES**. Runtime
  assurance, sequential monitoring, adaptive/robust ML systems, and ML-for-systems
  researchers have a clear technical object and useful boundary results.
- Recommendation under only C and A: **ACCEPT**.

## 11. Prioritized next steps

| Priority | File/section | Required? | Effort | Action | Expected verdict effect |
|---:|---|---|---|---|---|
| 1 | `paper/bouncer.tex` + full artifact | Completed | Medium | Final `run_all.sh`, 40/40 audit, LaTeX warning scan, and all-page render inspection completed | Confirms C=Yes |
| 2 | `champsim_plugin/` | Optional | High | Automate the complete three-trace regeneration and record toolchain hashes | Strengthens reproducibility; no change to scoped C verdict |
| 3 | Tier-A hardware | Optional | High | Quantize, synthesize, and measure area/energy/timing | Converts proposal into measured systems evidence |
| 4 | Real replacement/predictor studies | Optional | High | Multi-trace, multi-seed clean-case transitions with warm-up-aware reseeding | Strengthens external validity, not required by TMLR A/C |
| 5 | Multi-resolution audit | Optional | Research | Address the named coverage hole | Could broaden the security scope |

## 12. Final release verification

- `./run_all.sh` completed with exit code 0 using the pinned local environment;
  all invariants and deterministic experiments passed, the paper rebuilt to 33
  pages, and the integrated number audit reported 40/40.
- A post-edit standalone rebuild of `champsim_plugin/bouncer.cc` passed its
  self-test and reproduced causal routing latency 2 and re-trust latency 10.
- `PYTHONPATH=. python3 scripts/check_paper_numbers.py` was rerun after the last
  generated-artifact wording correction and again reported 40/40.
- All 33 PDF pages were rendered and visually inspected. Dense theorem,
  hypothesis-discharge, real-simulator, storage, and related-work pages were also
  checked at full resolution. No clipping, illegible overlap, or malformed page
  was found.
- The final LaTeX log has no undefined references, undefined citations, or
  overfull boxes. Remaining underfull-box and PDF-string warnings do not alter
  content or legibility.
