# Reviewer prompt — TMLR, "Bouncer" revision 3

You are an expert, adversarial reviewer for TMLR. Review the revised paper **"Bouncer:
Competence Auditing for Set-Local Learned Microarchitectural Controllers."** Decide whether the
claims are now supported by accurate evidence, or scoped until they are.

## Where the artifact is

- Repo: `/Users/kabirgrewal/projects/bouncer-hpca`, branch `revision/tmlr-r2`, commit `9522059`.
- Paper: `paper/bouncer.tex` → `paper/bouncer.pdf`. Reproduce (deterministic, ~5 min):
  ```
  python3.11 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt      # pinned numpy 1.26.4 / scipy 1.11.4 / mpl 3.8.4 / pandas 2.0.3
  ./run_all.sh                                      # auto-uses ./.venv; stage 0 invariants, stage 9 number audit
  ```
- Key files: `bouncer/` (harness), `experiments/` (one script per phase), `results/*.json`,
  `scripts/check_paper_numbers.py`, `experiments/test_invariants.py`.

## Scope (do not widen)

Evaluate ONLY: **(C)** are all claims supported by accurate evidence, or explicitly scoped until
they are; **(A)** would some TMLR subcommunity find it interesting. Do **not** reject on novelty,
significance, or the absence of real silicon.

## Method

1. **Reproduce.** Build the venv, run `./run_all.sh`; record whether it reaches `DONE`, whether
   stage-0 invariants and the stage-9 audit pass, and independently recompute ≥5 headline numbers
   from `results/*.json`. Compile the PDF.
2. **Read `paper/bouncer.tex` end to end.** Treat every quantitative and theoretical claim as a
   hypothesis to falsify; default to refutation.
3. This revision responds to a prior review that **credited earlier fixes** (estimator ordering,
   E3 σ/deadline-TPR, the additive-warmup counterexample, reproduction) but **rejected** on the
   safety-floor theorem plus one implementation bug. The prior findings and this revision's
   claimed fixes are below — **verify each independently; do not take the fix on faith.**

## Prior (R2) findings and claimed (R3) fixes — verify each

1. **PROBING exposure bug (decisive last round).** Prior: PROBING routed C to
   `sorted(followers)[:n_aud]`, so a low-index hot set was exposed with probability
   `1 - n_L/n_sets = 0.984`, not `φ_P` — breaking the safety-floor guarantee in the released
   system; the regression tested a uniform *surrogate* and missed it. Claimed fix: the audit
   subset is now a **uniform secret** subset drawn in `SetDueling._assign` from the *random-order*
   follower portion (`set_dueling.is_audited`), reshuffled each epoch; `exp_floor_traffic.py`
   drives the **actual** `SetDueling` routing and `test_invariants.py` asserts index-independence.
   **Verify:** does the released routing (`bouncer/simulate.py`) use `is_audited`? Re-introduce a
   sorted-prefix audit and confirm `test_invariants.py` (`test_probing_audit_is_uniform_secret`)
   fails. From `results/floor_traffic.json`, is the sorted-prefix low-index exposure ≈0.985 and
   the uniform low/high ≈0.062/0.064 ≈ φ_P? Does A6 in the paper describe exactly this?

2. **Lemma 1 must follow from its assumptions.** Prior: A2 (delay ≤ D w.p. 1−δ) does not imply
   E[delay] ≤ D; A3 (marginal α) does not justify a Hoeffding high-probability false-alarm bound
   for the *stateful* CUSUM. Claimed fix: Lemma 1 is now an **expectation** bound proved by
   linearity from *marginal* assumptions — A2 restated as **E[delay] ≤ D** (Lorden/Siegmund mean
   delay), A3 marginal α gives E[false alarms] ≤ αT by linearity (no independence), A6 gives
   E[exposure] ≤ φ_P·r_max for arbitrary traffic; **high probability is claimed only for the
   exposure term** (independent reseeds, Hoeffding), and the detection/false-alarm high-prob forms
   are explicitly *not* claimed. **Verify:** does `eq:floor` now follow termwise by linearity from
   A2/A3/A6? Is the high-probability refinement correctly restricted to the exposure term? Is the
   exposure independence (fresh reseed each window) real in the code? Do `bouncer/theory.py` and
   its tests match?

3. **Deterministic/worst-case language.** Prior: the abstract, intro, theory, conclusion, and
   related work still called an expectation/high-probability statement deterministic or
   worst-case. Claimed fix: swept to "expected regret" everywhere (paper + README). **Verify:**
   grep for "never more", "worst-case", "deterministic guarantee" in guarantee contexts — are the
   remaining occurrences only *empirical* (a measured maximum), never a claimed guarantee?

4. **Characterization + reseed-identifiability.** Prior: the definition used the *absolute*
   reseeded contrast and "near", admitting a sign flip (true gap +0.3 read as −0.3 passes but
   reverses the gate); "characterize the class" overclaimed a theorem not proven; the discharge
   table invented an "A1 stateless sub-condition". Claimed fix: reseed-identifiability now uses the
   **signed** contrast with a τ-margin (`rem:stateless`); "characterize" softened to "govern
   (necessity argued, boundary demonstrated; sufficiency theorem future work)"; the discharge
   table (`tab:discharge`) drops "A1 stateless", adds A6 and A2-expected-delay rows. **Verify:**
   is the signed condition now decision-preserving? Does any sentence still assert statelessness is
   *necessary* or claim a full characterization theorem?

5. **P4 secrecy attribution.** Prior: the threat model and conclusion still attributed the
   50/50-vs-0/50 headline to secrecy, though the basic mimicry attack does not isolate it. Claimed
   fix: the threat model and conclusion now split *competence measurement* (explains 50/50 vs 0/50,
   the input monitor's failure is definitional) from *secrecy* (defeats a leak-aware attacker;
   quantified by the leak ablation). **Verify** this split is consistent across abstract, threat
   model, §eval, conclusion, related work.

## Also hunt for NEW defects this revision introduced

A broken step in the rewritten expectation proof; a number in the prose that disagrees with the
regenerated `results/*.json`; the A6 premise not matching the code; an inconsistency between the
signed reseed-identifiability condition and the discharge table; a place where the exposure
high-probability claim leaks back into a detection/false-alarm high-probability claim.

## Output format

1. **Reproduction record** — DONE? invariants pass? audit pass? numbers you reproduced.
2. **Per-claim evidence audit** — table: *Claim* | *Verdict* {SUPPORTED / OVERSTATED /
   UNSUPPORTED} | *evidence + `file:line`*. Cover the five items above and any new defects.
3. **TMLR criteria** — (C) Yes/No with reasons; (A) Yes/No.
4. **Recommendation** — Accept / Accept-with-minor / Reject, with the load-bearing reasons.
5. **Prioritized next steps** — table: priority, file/section, required?, effort, action.

Cite `file:line`, prefer refutation. If a claim is now correct, say so plainly. If a fix created a
new problem, that is the most valuable thing you can report.
