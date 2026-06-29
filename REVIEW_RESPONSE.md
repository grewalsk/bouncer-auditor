# Response to the adversarial review

An independent 4-reviewer adversarial audit (theory / code / claims / threat-model)
produced 21 findings (5 blocking). Full record: `results/adversarial_review.json`.
Every blocking finding and the substantive minors are addressed below.

## Blocking findings — all fixed

| # | Finding | Fix |
|---|---------|-----|
| 1 | **Triage is circular** (P3): co-tenant feature derived from the label; fit & scored in-sample; abruptness used the unobservable `delta_true`. | Rewrote `exp_p3_generality.triage`: features are now all **auditor-observable** (abruptness = slope of estimated `Δ̂`, not ground truth); co-tenant signal given real class overlap; **5-fold cross-validation**; **drop-one-feature ablation** shows no single feature (incl. co-tenant) is load-bearing. Result stays 100% because drift vs attack are genuinely separable in observable Tier-A space. |
| 2 | **Prop 1 stated unconditionally**; exchangeability only holds per-domain; heterogeneity bias unquantified; global Δ̂ has no guarantee vs redistribution. | Restated **Prop 1 conditionally** (per-domain dueling within region R, within-R exchangeability up to a bias β), proved the (1−f) residual-signal bound, and added an explicit "what this does/does not cover" block: global Δ̂ gives **no** guarantee vs redistribution; β shrinks under epoch reseeding. |
| 3 | **Plotted Lemma-1 bound ≠ Eq.(floor)**: used `ipc_slope·(1−q0)` not `ipc_slope·r_max`. | Fixed `exp_p1`/`exp_theory` to plot `N_ep·D·r_max` (IPC units); now the loose Eq.(floor) bound (15.1 vs measured 5.9 at N_ep=6) with text noting it is loose. |
| 4 | **"0 ns / <1% / systems result"** presented as measured but analytical. | Relabeled Table II as the **analytical overhead budget**; 0 ns is "by construction" (sampled/off-path); removed "the systems result" framing. |
| 5 | **Entire evaluation is one synthetic harness**; abstract/intro oversell. | Abstract, contributions, and §Methodology now state explicitly: all results are from a **synthetic competence harness**; the ChampSim skeleton is **gate-behavior-verified only, not run on SPEC**; headline reported as `40/40` vs `0/40`, not as proven constants. |

## Substantive minors — addressed

- **ARL validation regime**: noted the Gaussian sweep is a *formula sanity check* (small-drift, heavy-overshoot regime); the deployed detector runs in the strong-drift limit `D≈H/(K−Δ)`, `ARL0` astronomically large (`α≈0`). Geomean ratio corrected to **0.998**.
- **Assumption A2** aligned with the CUSUM: a *drop episode* is `Δ<τ` (the off-policy condition, consistent with `K=τ+γ/2`); `D` stated as a high-probability bound (mean delay + tail term).
- **One-window vs D≈1.8**: P1 now says detection is one window *here* (best case at high SNR); the worked mean delay is ≈1.8 windows.
- **Transient magnitude**: P1 reports the lone pre-detection window dips **36%** below floor (the bounded `≤D·r_max` term).
- **Rounding**: P4 reports **0.975 / 0.075** (was 0.98/0.08); floor **0.63%** (was 0.6%).
- **Leader-F clean tax**: noted the clean tax is exactly the `n_F` sets permanently running π₀.
- **Secrecy-ablation effective pool**: noted the in-region pool is ~4 Leader-L sets (hence a few windows of latency); the cliff is a property of secrecy `f`, not pool size.
- **Online-learning poisoning**: now **explicitly out of scope** for the base model (prominent in §Threat model), not a parenthetical — freezing at GATED stops further poisoning but does not undo it.
- **`RegionalCovertAttack` docstring** corrected: it suppresses *input marginals* and spares guessed leaders; it does **not** fully preserve aggregate reward (which is why per-region dueling is required).
- **"environment-agnostic"** qualified: the guarantees rest only on A1–A5; validated in *one* synthetic environment instantiated three ways.

## Reviewer-confirmed strengths

Variance bound exactly tight at p=½; Siegmund ARL correct and matches Monte Carlo;
Lemma 1 sound; headline numbers faithfully backed by the released JSON (R²=0.99741,
ARL 927 vs 938, secrecy cliff, 336 B / 0.13% / 0 ns). No fabricated numbers found.

---

# Second-round review (final, post-hardening)

A 3-reviewer HPCA panel (claims / systems / overall) reviewed the hardened paper.
Recommendations: **claims = accept, systems = borderline, overall = weak-accept**;
acceptance odds estimated ~30% as-written → ~50% with the ChampSim reframing.
Full record: `results/final_review.json`. The claims reviewer found **zero**
number-vs-JSON mismatches. The systems reviewer (the only one to read the released
ChampSim per-window logs) caught a real, load-bearing over-interpretation. All 5
blocking findings are now addressed.

| Finding | Fix |
|---------|-----|
| **[CRITICAL] ChampSim over-interpreted as attack-specific detection.** Logs show the gate enters GATED at window 4 in *both* clean and attacked runs (attack onset = window 30); the prefetcher was already distrusted, so "recovery" is "already off," not "saw the attack and reacted." | **Reframed** the entire §Real-systems section to the *safety-floor cap* the data supports: when realized competence says the learned arm is below the floor (benign or adversarial), Bouncer bounds the loss; explicitly stated it is **not** attack-specific detection, and that transition *dynamics* are shown in the synthetic harness (Fig. floor) where competence is controllable. |
| **[MAJOR] Clean-tax "undervalues timeliness, mildly-helpful" unsupported** — logs show Δ̂ persistently negative (reward judges the prefetcher net-harmful). | Replaced with the honest two-direction finding using **both** traces: lbm (proxy says unhelpful → floor cap), roms (proxy under-credits a *genuinely-helpful* prefetcher → 11% over-gating tax). "The auditor is only as good as its competence reward." |
| **[MAJOR] "0 ns added datapath latency by construction" overstated** — the per-access pool-tag lookup + GATED mux are on the prefetch-decision path. | Scoped throughout (abstract, contributions, overhead §) to **"no added latency on the cache-access critical path"**; the per-access cost is a 2-bit tag read + mux (like DIP/DRRIP); only the confirmer/CUSUM/FSM are off-path/epoch-grained. |
| **[MAJOR] R²=0.997 estimator fidelity is synthetic-only, doesn't transfer** (real Δ̂ ~40× noisier; m≈19/bucket). | P0 text now labels it a **controlled-harness** result at m=64 and points to the noisier real-trace regime; the ChampSim §discloses m≈19 and the resulting noise. |
| **[MAJOR] ChampSim operating point undisclosed / inconsistent with synthetic** (τ=0, H=0.25, m≈19 vs τ=0.05, H=0.8, m=64). | The ChampSim § now **states the operating point explicitly and explains** the looser (τ,H) is forced by the noisier real signal; champsim.json records it; stale `m≈12` header comment context noted. |
| Minor: secrecy P4(b) single-run vs 50-seed CI labeling; "sets" = virtual buckets; doc reconciliation. | Robustness §carries the 50-seed CI secrecy curve; ChampSim §clarifies dueling "sets" = `blk mod 2048` buckets; plugin README + this file reconciled to the honest framing. |

**Net:** the ChampSim arm is now an honest *proof of deployment + a candid
reward-proxy lesson* (which motivates the §8 design choice of the controller's own
in-silicon reward), rather than an over-claimed attack-detection result. The
controlled quantitative guarantees remain with the synthetic harness. The single
highest-leverage future step the panel identified — a full SPEC/GAP sweep with a
timeliness-aware reward showing a real TRUSTED→GATED transition — is stated as the
next systems milestone.
