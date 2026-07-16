# Reviewer prompt — TMLR, "Bouncer" revision 7

You are an expert, adversarial reviewer for TMLR. Review the revised paper **"Bouncer:
Competence Auditing for Set-Local Learned Microarchitectural Controllers."** Decide whether the
claims are now supported by accurate evidence, or scoped until they are.

## Where the artifact is

- Repo: `/Users/kabirgrewal/projects/bouncer-hpca`, branch `revision/tmlr-r2`, commit `cd0e642`.
- Paper: `paper/bouncer.tex` → `paper/bouncer.pdf` (34 pp). Reproduce (deterministic, ~5 min):
  ```
  python3.11 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt      # pinned numpy 1.26.4 / scipy 1.11.4 / mpl 3.8.4 / pandas 2.0.3
  ./run_all.sh                                      # auto-uses ./.venv; stage 0 invariants, stage 9 audit (expect 27/27)
  ```
- Key files: `bouncer/` (esp. `cusum.py`, `set_dueling.py`), `experiments/` (esp. the extended
  `exp_prop1_selection.py`), `results/*.json`, `scripts/check_paper_numbers.py`,
  `hardening/REVISION_STATUS.md` (canonical status; other `hardening/` files are historical).

## Scope (do not widen)

Evaluate ONLY: **(C)** are all claims supported by accurate evidence, or explicitly scoped until
they are; **(A)** would some TMLR subcommunity find it interesting. Do **not** reject on novelty,
significance, or the absence of real silicon.

## Method

1. **Reproduce.** Build the venv, run `./run_all.sh`; record `DONE`, stage-0 invariants, stage-9
   audit; independently recompute ≥5 headline numbers; compile the PDF.
2. **Read `paper/bouncer.tex` end to end.** Treat every quantitative and theoretical claim as a
   hypothesis to falsify; default to refutation.
3. This revision responds to a prior review that judged **everything else SUPPORTED** (Lemma 1,
   the floor prediction, the occupancy-tight plug-in, plug-in labeling, Prop 1(i), the
   single-window retraction, correlated-audit disclosure, E3, warmup scoping, set-locality
   scoping, audit honesty) and **rejected solely on Proposition 1(ii) as printed**, with three
   sub-findings plus three smaller items. The claimed fixes are below — **verify each
   independently; do not take the fix on faith.**

## Prior (R6) findings and claimed (R7) fixes — verify each

1. **Wrong Hoeffding range.** Prior: Δ̂ ∈ [−r_max, r_max] (width 2r_max), but the paper printed
   `exp(−2Wε²/r_max²)` — 4× too strong in the exponent; an exact W=100, τ=ε=0.2 Rademacher
   example violates it 84.79× (P = 0.028444 vs 0.000335). Claimed fix: the statement, proof,
   §eval-prop1, and README now print `exp(−Wε²/(2r_max²))` (range 2r_max), and
   `experiments/exp_prop1_selection.py::printed_formula_regression` asserts the exact
   counterexample against the OLD formula and that the corrected formula holds. **Verify:** does
   every printed instance of the sustained-evasion bound use the corrected constant? Does the
   regression compute the exact binomial tail (not a simulation) and match `results/
   prop1_selection.json`?

2. **Independence not implied by reseeds.** Prior: fresh secret assignments do not make
   per-window Δ̂_R independent — the reward process, duty, and adaptive adversaries can depend on
   gate history; the proposition needed an explicit premise. Claimed fix: Prop 1(ii) now states
   the temporal premise explicitly (per-window Δ̂_R independent *given the strategy*), notes it
   holds for the harness's i.i.d. reward and is violable by gate-history-dependent strategies,
   and the discharge table (`tab:discharge`) has a corresponding row. **Verify** the premise is
   in the proposition itself (not only the proof), and that no text still derives independence
   from reseeding alone.

3. **False CUSUM step.** Prior: "once the average falls below τ, the CUSUM accumulates ≥ γ/2 per
   window and fires within 2H/γ windows" is false (exact counterexample: prefix [0, 0.09] then
   sixteen 0.09s leaves C = 0.27 < H = 0.8, no alarm). Claimed fix: replaced by the **block
   containment** argument — the CUSUM's max(0,·) floor only raises the statistic, so no alarm in
   W windows forces the block average of Δ̂_R above K − H/W ≥ τ for W ≥ 2H/γ; hence
   P(no alarm) ≤ P(block average ≥ τ) ≤ the corrected Hoeffding envelope. The old step is
   explicitly retracted in the proof. `exp_prop1_selection.py::cusum_block_tests` reproduces the
   {0, 0.09} counterexample on the real `LowerCusum`, verifies the containment on 2000 random
   degrading streams, and checks the empirical no-alarm probability under the envelope.
   **Verify:** (a) is the containment argument correct for the *implemented* update
   `C_t = max(0, C_{t−1} + (K − Δ̂_t))` (check the inequality direction of the max(0,·) floor);
   (b) does the proof avoid any residual "then it fires" step; (c) do the tests drive the real
   detector?

4. **P4 within-region pools mismatch.** Prior: the implementation intersects *global* pools with
   the region (expected in-region pool ≈ 4; a named pool is empty w.p. 0.013/window, either
   0.027, with a Δ̂_R = 0 fallback), which is not Prop 1's fixed nonempty within-R construction.
   Claimed fix: the eval text now disclosed exactly this and labels the experiment an
   *approximation* of the construction. **Verify** the disclosure matches
   `experiments/exp_p4_mimicry.py` / `bouncer/bouncer.py` behavior.

5. **"On real hardware" wording.** Prior: the evidence is a real-trace ChampSim study, not
   hardware measurement. Claimed fix: three sites rephrased ("real-trace ChampSim study",
   "real-trace simulator study", "real program traces in ChampSim"). **Verify** no residual
   "real hardware" evidence claim.

6. **Stale hardening self-reports.** Prior: `hardening/state.json` and `TMLR_R1_RESPONSE.md`
   quoted stale counts/pages as if current. Claimed fix: `hardening/REVISION_STATUS.md` is the
   canonical, count-free status pointer; the historical files carry banners directing there.
   **Verify.**

## Also hunt for NEW defects this revision introduced

An error in the block-containment inequality (e.g. whether `C_t ≥ Σ(K−Δ̂)` truly holds for the
implemented reset semantics, including after intermediate alarms/resets); a mismatch between the
corrected exponent and the two-set experiment's envelope numbers (r_max = 1 there, so the
envelope is exp(−W/8) — check consistency); any site still printing the old constant; prose
numerals disagreeing with the regenerated `results/*.json`.

## Output format

1. **Reproduction record** — DONE? invariants? audit? numbers you independently reproduced.
2. **Per-claim evidence audit** — table: *Claim* | *Verdict* {SUPPORTED / OVERSTATED /
   UNSUPPORTED} | *evidence + `file:line`*. Cover the six items above and any new defects.
3. **TMLR criteria** — (C) Yes/No with reasons; (A) Yes/No.
4. **Recommendation** — Accept / Accept-with-minor / Reject, with the load-bearing reasons.
5. **Prioritized next steps** — table: priority, file/section, required?, effort, action.

Cite `file:line`, prefer refutation. If a claim is now correct, say so plainly. If a fix created a
new problem, that is the most valuable thing you can report.
