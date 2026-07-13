# Reviewer prompt — TMLR, "Bouncer" revision 4

You are an expert, adversarial reviewer for TMLR. Review the revised paper **"Bouncer:
Competence Auditing for Set-Local Learned Microarchitectural Controllers."** Decide whether the
claims are now supported by accurate evidence, or scoped until they are.

## Where the artifact is

- Repo: `/Users/kabirgrewal/projects/bouncer-hpca`, branch `revision/tmlr-r2`, commit `ef3e72b`.
- Paper: `paper/bouncer.tex` → `paper/bouncer.pdf`. Reproduce (deterministic, ~5 min):
  ```
  python3.11 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt      # pinned numpy 1.26.4 / scipy 1.11.4 / mpl 3.8.4 / pandas 2.0.3
  ./run_all.sh                                      # auto-uses ./.venv; stage 0 invariants, stage 9 number audit
  ```
- Key files: `bouncer/` (harness incl. `gate_fsm.py`, `set_dueling.py`, `theory.py`),
  `experiments/` (incl. `exp_retrust.py`, `exp_floor_traffic.py`, `test_invariants.py`),
  `results/*.json`, `scripts/check_paper_numbers.py`.

## Scope (do not widen)

Evaluate ONLY: **(C)** are all claims supported by accurate evidence, or explicitly scoped until
they are; **(A)** would some TMLR subcommunity find it interesting. Do **not** reject on novelty,
significance, or the absence of real silicon.

## Method

1. **Reproduce.** Build the venv, run `./run_all.sh`; record `DONE`, stage-0 invariants, and the
   stage-9 audit; independently recompute ≥5 headline numbers from `results/*.json`; compile the PDF.
2. **Read `paper/bouncer.tex` end to end.** Treat every quantitative and theoretical claim as a
   hypothesis to falsify; default to refutation.
3. This revision responds to a prior review that **credited** the sampler repair, reproduction,
   the E3 σ/deadline-TPR fix, the additive-warmup counterexample, and signed reseed-identifiability,
   and **rejected** on (i) the safety-floor lemma not covering false re-trust in the released FSM,
   plus (ii) residual deterministic/high-probability language, an A2/A3 "established" overclaim, a
   dimensionally-inconsistent Proposition-1 threshold, and scope contradictions. The claimed fixes
   are below — **verify each independently; do not take the fix on faith.**

## Prior (R3) findings and claimed (R4) fixes — verify each

1. **False re-trust not covered by Lemma 1 (decisive last round).** Prior: A2 charged one
   detection delay per maximal true-drop episode, but PROBING can re-trust to TRUSTED after
   `T_reprobe` noisy audit estimates ≥ τ+hys, re-opening the gate mid-drop; nothing bounded those
   re-openings. Claimed fix: **A2 now bounds the expected number of *fully-open* windows per
   episode** (initial detection + any false re-trust), so the detection term `N_ep·D·r_max` covers
   re-trust by construction; new `experiments/exp_retrust.py` measures it — (A) with the real
   estimator false re-trusts are ≈0 across drop depths (fully-open fraction 0.019–0.067), and (B)
   under worst-case stipulated audit noise the background Tier-B corrects each re-trust in ~1
   window and raising `T_reprobe` drives the rate down geometrically (14.3→2.6→0.2→0 per 1000
   windows). **Verify:** does A2's D really cover re-trust in the proof (`paper/bouncer.tex`,
   Lemma 1 + §eval-retrust)? Does `exp_retrust.py` drive the actual FSM (`gate_fsm.py`)? Are the
   numbers in `results/retrust.json` consistent with the text? Is the claim now "D is finite and
   design-controlled" rather than "re-trust never happens"?

2. **High-probability scope leaked into a three-term guarantee.** Prior: the eval called the
   exposure-only Eq. 5 a "loose three-term high-probability" guarantee. Claimed fix: the loose
   three-term form is the **expectation** guarantee (Eq. 4); only its **exposure** term carries a
   high-probability envelope (Eq. 5); detection/false-alarm are expectation-only. **Verify:** grep
   the paper/README/theory.py for any remaining "three-term high-probability" or "never more"
   /"deterministic guarantee" in a guarantee context.

3. **A2/A3 "established".** Prior: the discharge table marked A2 (mean delay) and A3 (marginal
   alarm) as *established* by Lorden/Siegmund, but those are approximations, not upper bounds, and
   mean ARL does not imply the marginal alarm inequality. Claimed fix: the table now marks both
   **assumed (approximated by** Lorden/Siegmund**)**. **Verify** `tab:discharge`.

4. **Proposition 1 leakage threshold dimensionally wrong.** Prior: `H·σ_{Δ,R}` mixed the CUSUM
   threshold with a reward std. Claimed fix: the condition is now the unprotected degradation
   pushing Δ̂_R below the CUSUM reference `K=τ+γ/2` (margin γ/2, up to O(σ) noise), and Δ̂_R≥τ is
   labeled a realized per-window event. **Verify** the statement and proof of `prop:mimicry`.

5. **Scope contradictions.** Prior: the abstract/methodology/README said the guarantees rest
   "only on bounded reward + a partitionable resource," omitting A2–A6, secrecy, set-locality, and
   reseed-identifiability; and "characterization" overclaimed a theorem. Claimed fix: these now
   list the full assumption set (A1–A6 + set-locality + reseed-identifiability), and
   "characterization" is softened to "two conditions (necessity argued, boundary demonstrated;
   sufficiency future work)". **Verify** consistency across abstract, contributions, methodology,
   discharge table, conclusion, README, and that `results/e3_sensitivity.json`'s scope note now
   says 1.6σ (background) / 3.2σ (full duty).

6. **audited_frac wiring.** Prior: routing used `SetDuelingConfig.audited_frac` but the bound used
   the dead `SimConfig.audited_region_frac`. Claimed fix: single-sourced (`common.py` wires
   `SimConfig.audited_region_frac` into `SetDuelingConfig.audited_frac`), with a runtime assertion
   in `simulate.py` and a `test_invariants.py` check that the implemented rounded exposure ≤ φ_P.
   **Verify.**

## Also hunt for NEW defects this revision introduced

A broken step in the fully-open-windows argument; `exp_retrust.py` not actually exercising the
FSM re-trust path; a number in the prose disagreeing with `results/*.json`; A2's D now being used
inconsistently (mean detection delay in one place, fully-open count in another); any place the
expectation/high-probability distinction is still blurred.

## Output format

1. **Reproduction record** — DONE? invariants pass? audit pass? numbers you reproduced.
2. **Per-claim evidence audit** — table: *Claim* | *Verdict* {SUPPORTED / OVERSTATED /
   UNSUPPORTED} | *evidence + `file:line`*. Cover the six items above and any new defects.
3. **TMLR criteria** — (C) Yes/No with reasons; (A) Yes/No.
4. **Recommendation** — Accept / Accept-with-minor / Reject, with the load-bearing reasons.
5. **Prioritized next steps** — table: priority, file/section, required?, effort, action.

Cite `file:line`, prefer refutation. If a claim is now correct, say so plainly. If a fix created a
new problem, that is the most valuable thing you can report.
