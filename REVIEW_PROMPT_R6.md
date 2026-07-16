# Reviewer prompt — TMLR, "Bouncer" revision 6

You are an expert, adversarial reviewer for TMLR. Review the revised paper **"Bouncer:
Competence Auditing for Set-Local Learned Microarchitectural Controllers."** Decide whether the
claims are now supported by accurate evidence, or scoped until they are.

## Where the artifact is

- Repo: `/Users/kabirgrewal/projects/bouncer-hpca`, branch `revision/tmlr-r2`, commit `3e0e5a0`
  (the R6 content spans `82f0e68` + the final relabels in `3e0e5a0`; review the latter).
- Paper: `paper/bouncer.tex` → `paper/bouncer.pdf` (34 pp). Reproduce (deterministic, ~5 min):
  ```
  python3.11 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt      # pinned numpy 1.26.4 / scipy 1.11.4 / mpl 3.8.4 / pandas 2.0.3
  ./run_all.sh                                      # auto-uses ./.venv; stage 0 invariants, stage 9 audit
  ```
- Key files: `bouncer/`, `experiments/` (note the new `exp_prop1_selection.py` and the extended
  `exp_retrust.py` noise sweep), `results/*.json`, `scripts/check_paper_numbers.py`.

## Scope (do not widen)

Evaluate ONLY: **(C)** are all claims supported by accurate evidence, or explicitly scoped until
they are; **(A)** would some TMLR subcommunity find it interesting. Do **not** reject on novelty,
significance, or the absence of real silicon.

## Method

1. **Reproduce.** Build the venv, run `./run_all.sh`; record `DONE`, stage-0 invariants, and the
   stage-9 audit (expect 26/26 — note the paper now honestly labels this a *literal-presence
   audit*, a regression tripwire, not a semantic audit); independently recompute ≥5 headline
   numbers; compile the PDF.
2. **Read `paper/bouncer.tex` end to end.** Treat every quantitative and theoretical claim as a
   hypothesis to falsify; default to refutation.
3. This revision responds to a prior review that **credited** the real-path re-trust experiment,
   the D_det/D_open distinction, the clean-margin leak algebra, E3, the warmup counterexample, and
   the scope repairs, and **rejected** on Proposition 1's selection-bias error plus four narrower
   items. The claimed fixes are below — **verify each independently; do not take the fix on
   faith.**

## Prior (R5) findings and claimed (R6) fixes — verify each

1. **Proposition 1 selection bias (decisive last round).** Prior: the proof used the
   *unconditional* exchangeability identity `E[r_L]=E[r_foll]+b`, then concluded on the *realized*
   evasion event `{Δ̂_R ≥ τ}` — invalid conditioning; a two-set exchangeable counterexample gives
   `E[r_foll | evade] = 0` with `P(evade)=0.5` despite equal unconditional means, falsifying the
   old "cannot be degraded while evading the gate" claim. Claimed fix: Proposition 1 is restated
   in two forms — **(i) expectation**: `E[Δ̂_R] ≥ τ` forces `E[follower reward] ≥ fallback+τ−β`
   (the identity applied unconditionally); **(ii) sustained realized evasion**: with independent
   per-epoch reseeds and bounded rewards, a truly degrading strategy (`E[Δ̂_R] ≤ τ−ε`) keeps the
   W-window average above τ only w.p. `≤ exp(−2Wε²/r_max²)` (Hoeffding), and the CUSUM (reference
   `K > τ`) fires within `2H/γ` windows once the average dips. The single-window realized claim is
   explicitly **retracted** in a new §eval-prop1, and `experiments/exp_prop1_selection.py` *owns*
   the counterexample (`E[r_foll|evade]=0.0000`, `P(evade)=0.4997`), measures the sustained-decay
   envelope (0.50→0.04 for W=1→16), and shows the pinned-operating-point follower selection bias
   is ≈0. **Verify:** (a) is the two-form statement now valid — in particular, is the Hoeffding
   step legitimate (are per-window Δ̂_R genuinely independent across epochs in the released
   system)? (b) does the proof sketch avoid conditioning the identity on the evasion event?
   (c) do the abstract/contribution advertisements match the corrected two-form property?
   (d) does the experiment reproduce and match the prose numerals?

2. **D_det numerals called "bounds".** Prior: `12.4`, `15.1`, `123.6` were called Lemma "bounds"
   though `H/(K−Δ)` is a mean approximation the paper itself says is not an upper bound. Claimed
   fix: all such numerals are relabeled **conditional plug-in illustrations** of Eq. (floor),
   with the mean-not-upper-bound caveat inline (P1 site, theory-validation panel walkthroughs,
   §eval-retrust, README). **Verify** no remaining site presents a D_det plug-in numeral as a
   bound or guarantee.

3. **Correlated-audit noise scale undisclosed.** Prior: the ρ=0.95 headline (fully-open 0.225)
   injected AR(1) noise 0.10 = 3.2–6.4× the harness σ, undisclosed; and near-independence was
   equated with reseed-identifiability. Claimed fix: a noise sweep at ρ=0.95
   (≈0.006 @ σ_full, ≈0.022 @ σ_bg, ≈0.096 @ 0.05, ≈0.225 @ 0.10) is released in
   `results/retrust.json` and disclosed in the paper, which now frames the 0.225 as a property of
   a *constructed* correlated/high-variance counterexample and states temporal independence is
   **distinct** from reseed-identifiability's signed-mean condition. **Verify** the sweep runs
   through the real controller and the prose matches.

4. **Tight form missing PROBING occupancy.** Prior: the N_ep sweep computed
   `D + φ_G(60−D)`, never charging PROBING at φ_P (released 7.834 vs stated-formula 8.290).
   Claimed fix: the sweep now charges realized `φ_G·n_GATED + φ_P·n_PROBING` per trajectory;
   the tight value changed 7.8 → **9.5** (ordering 5.9 ≤ 9.5 ≤ 47.4 holds), regenerated in
   `results/theory.json`, and the audit literal is now **derived from the JSON** rather than
   hard-coded. **Verify** `experiments/exp_theory.py` matches the prose formula and the paper
   numeral matches the JSON.

5. **def:setlocal internal contradiction.** Prior: the definition claimed set-locality alone
   yields unbiased/faithful Δ̂, contradicting the remark and the replacement result. Claimed fix:
   the definition now states **spatial attribution only** and explicitly conditions faithfulness
   on reseed-identifiability. **Verify** the definition, remark, and real-systems section are now
   mutually consistent.

6. **Audit honesty + README metadata.** Prior: the reproducibility statement claimed the checker
   "asserts every headline numeral" (it is literal-presence); README said 11-page IEEEtran/~4 min.
   Claimed fix: the statement now calls it a *literal-presence audit / regression tripwire, not an
   exhaustive semantic audit*; three new checks added (prop-1 counterexample, sustained decay,
   noise disclosure); README updated (34 pp TMLR, ~5 min, 0.64%, 9.5 tight, expectation-form
   Prop 1). **Verify.**

## Also hunt for NEW defects this revision introduced

A gap in the two-form Proposition (e.g. the `2H/γ` CUSUM step, or independence of per-window
Δ̂_R under the leak-ablation's *within-region* pools); a place where the retracted single-window
claim survives (threat model, related work, discharge table, README); prose numerals disagreeing
with the regenerated `results/*.json` (the tight 9.5 changed this round); any residual "bound"
label on a plug-in numeral.

## Output format

1. **Reproduction record** — DONE? invariants? audit? numbers you independently reproduced.
2. **Per-claim evidence audit** — table: *Claim* | *Verdict* {SUPPORTED / OVERSTATED /
   UNSUPPORTED} | *evidence + `file:line`*. Cover the six items above and any new defects.
3. **TMLR criteria** — (C) Yes/No with reasons; (A) Yes/No.
4. **Recommendation** — Accept / Accept-with-minor / Reject, with the load-bearing reasons.
5. **Prioritized next steps** — table: priority, file/section, required?, effort, action.

Cite `file:line`, prefer refutation. If a claim is now correct, say so plainly. If a fix created a
new problem, that is the most valuable thing you can report.
