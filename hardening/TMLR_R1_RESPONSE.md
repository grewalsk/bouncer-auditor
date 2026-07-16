> **HISTORICAL (R1-era).** This response describes revision/tmlr-r1. For current status see `hardening/REVISION_STATUS.md` and `REVIEW_PROMPT_R*.md` (later rounds superseded several statements below, including the Lemma form and audit counts).
# TMLR R1 response — Bouncer (`revision/tmlr-r1`)

Response to the hostile TMLR-calibrated review (verdict: Claims-and-Evidence = **No**, one
reject-grade defect + four smaller claim/evidence defects; Audience = Yes; Reject as
submitted, flips to Accept after the Critical fixes). Every fix is on `revision/tmlr-r1`,
committed with a phase-tagged message, and verified by a regenerated number or a grep. The
reject-grade defect (Lemma 1) was independently re-adjudicated by a hostile critic (gate G1).

## Critical items (the accept/reject pivot)

| # | Review defect | Fix | Commit | Verification |
|---|---|---|---|---|
| **C1** | **Lemma 1 is false as stated**: the two-term bound `N_ep·D·r_max + α·T·c_sw` omits the regret from the n_L Leader-C sets that keep running C in every gate state (reviewer's numerical counterexample). | Restated Lemma 1 as **three-term**, adding an audit-exposure term `φ_P·T_att·r_max` (φ_G=1.56%, φ_P=6.4%). Proof repaired (bucket (i) GATED is φ_G·gap, not 0; +PROBING bucket (i′)). Reframed as a **strength**: the exposure term *predicts* the mean attacked-GATED floor (φ_G→0.579% vs measured 0.581%; the 0.63% is the worst single window). New regression `exp_floor_longattack.py` + `results/floor_longattack.json`; `exp_theory.py` L_att sweep; `exp_p1_floor.py` bound line → corrected 12.4. | `391d2a1` | **G1 GREEN** (independent critic): re-derived the bound from `simulate.py:82` alone; no counterexample survived the LOOSE bound across an adversarial battery (probing-exploit, τ-oscillators, PROBING-concentrators); the R2 reviewer separately showed the mean-D TIGHT form grazes on weak drops (now scoped high-probability); regression asserts `measured ≤ corrected-loose` strictly; two-term violated at L_att=960 (25.8 > 7.6). Protected 15.1/7.8/5.9 + P1 0.639%/lat1/tax0.99653 intact. |
| **C2** | E3 clean-tax range **"0.49–0.52%"** disagrees with `e3_sensitivity.json` (actual 0.16–0.51%). | Replaced with **0.16–0.51%** (overall from the JSON invariants). | `573a7bb` | `scripts/check_paper_numbers.py` recomputes the range from JSON and asserts the tex literal; 20/20. |
| **C3** | E3 **"|Δ_W|=0.015 ≫ σ_Δ"** is false (σ_Δ=0.015625 > 0.015) and conflates estimator resolution with drift SNR. | Removed from all 4 paper sites + the generator. Reframed: for any off-policy gap (Δ<τ) the CUSUM **drift** K−Δ ≥ γ/2 = 3.2σ_Δ, so TPR≈1 across the off-policy range (flat sweep is **consistent** with theory); what grows toward τ is **latency** D≈H/(K−Δ), up to ~16 windows. | `573a7bb` | Regenerated `e3_sensitivity.json` scope string; G3 grep `\gg\sigd`/`>> sigma` empty. |
| **C4** | Conclusion **"faithful exactly when reward shares a set"** (iff) is contradicted one sentence later. | Changed to **necessity** ("requires that reward share a set"), with the (near-)stateless second condition following. `state.json` C_setlocal iff removed. | `c8a9acc` | G3 grep "faithful exactly when" empty; conclusion now internally consistent with Remark 1. |
| **C5** | **PC-indexed predictors** claimed "faithfully audited" (set-local) but the statelessness condition was never checked for them; no experiment instantiates one. | Scoped to **"expected set-local; statelessness untested"** at the abstract, formal setting, and Table 1 caption. | `c8a9acc` | Predictors no longer asserted as audited; Table 1 caption carries the caveat. |

**Net:** all five Criticals resolved by scoping claims to the evidence (C2–C5, zero experimental
cost) or correcting the theorem to match the built system (C1). No claim was strengthened;
`state.json` Gap = 0, INV-1..R7 green.

## Minor items (reduce Action-Editor round-trips)

| Item | Fix | Commit |
|---|---|---|
| P4 input-OOD 0/40 read as an earned result | Marked **definitional** (mimicry holds S_in in-distribution via `suppress_features`); earned result is Bouncer 40/40 + secrecy ablation. Numbers kept. | `c8a9acc` |
| "no added latency" stated as fact | "**by construction / analytical**, RTL timing future work" at every site (abstract, contributions, overhead, champsim, conclusion, README, `champsim_knobs.md`, `exp_p2`). | `888b28b` (+prior) |
| Bald "0 ns" in the artifact | `exp_p2` field → `added_latency_analytical_ns`; print + `champsim_knobs.md` scoped. | `888b28b` |
| Stale `champsim.json` "tracks real benefit" | Interpretation rewritten to the current finding (own-reward does **not** fix the prefetcher; localizability decisive) + `provenance` field; numbers untouched. | `888b28b` |
| Stale `final_review.json` (validated the false Lemma) | Removed (superseded review of a pre-hardening draft). | `<phase6>` |
| N1 reward-swap placement | Single-trace/single-seed caveat + pointer to `hardening/experiments/N1_reward_swap/`. | `888b28b` |
| E1 single-trace disclosure | fixed-leader std 0.57, mean-level (~3 SE / ~50 windows), GATED 89%/80%, different log protocols (verified from CSVs), multi-trace future work. | `888b28b` |
| Prop 1 hygiene | Dangling "(Sec. below)" → explicit β assumption + σ_het empirical proxy. | `c8a9acc` |
| Bibliography | Suitability Filter (ICML'25), Sequential Harmful Shift (NeurIPS'24), D3M (NeurIPS'25) verified; shojaei author verified (Alireza Shojaei). | `888b28b` (+prior) |
| Lemma 6.1 / Prop 6.2 legacy numbering; docstring window 100/220 vs 90/200 | Normalized to Lemma 1 / Prop 1; docstring fixed to 90/200. | `888b28b` |
| Anonymity | author-name absolute paths -> $HOME; a case-insensitive author-name grep over tracked source returns empty. | `888b28b` |
| INV-R1 number audit | `scripts/check_paper_numbers.py` (20 numerals vs JSON) wired as run_all stage 9. | `888b28b` |

## Invariants at HALT
INV-R1 (no overclaim, number audit 20/20), INV-R2 (byte-identical `run_all`, manifests in
`hardening/manifests/`), INV-R3 (no over-retreat: every PROTECTED CLAIM intact, G1-verified),
INV-R4 (GATED semantics consistent across 5 sites, G1-verified), INV-R5 (anonymity: author-name grep empty),
INV-R7 (new prose em-dash-free).

## FLAG_FOR_HUMAN (not faked)
- **Anonymized artifact mirror** for double-blind submission (the public repo URL de-anonymizes).
- **≥3-trace replication** of the replacement reseed-confound (needs the ChampSim build + traces):
  the single biggest optional evidentiary upgrade.
- ~~Optional R-latency sweep (2.4)~~ DONE (commit 8047bef): fig:rlatency, latency 1->13 tracking H/(K-Delta).
- ~~Optional warmup-stateful predictor (3.2)~~ DONE (commit 160779b): fig:warmup, synthetic demonstration.
- Full **TMLR .sty conversion** status: see `hardening/state.json` gates (tmlr.sty fetched; conversion
  scope recorded there).
