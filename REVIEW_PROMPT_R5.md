# Reviewer prompt — TMLR, "Bouncer" revision 5

You are an expert, adversarial reviewer for TMLR. Review the revised paper **"Bouncer:
Competence Auditing for Set-Local Learned Microarchitectural Controllers."** Decide whether the
claims are now supported by accurate evidence, or scoped until they are.

## Where the artifact is

- Repo: `/Users/kabirgrewal/projects/bouncer-hpca`, branch `revision/tmlr-r2`, commit `67df72d`.
- Paper: `paper/bouncer.tex` → `paper/bouncer.pdf`. Reproduce (deterministic, ~5 min):
  ```
  python3.11 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt      # pinned numpy 1.26.4 / scipy 1.11.4 / mpl 3.8.4 / pandas 2.0.3
  ./run_all.sh                                      # auto-uses ./.venv; stage 0 invariants, stage 9 number audit (23/23)
  ```
- Key files: `bouncer/` (`bouncer.py`, `gate_fsm.py`, `cusum.py`, `set_dueling.py`, `theory.py`),
  `experiments/` (`exp_retrust.py`, `exp_floor_traffic.py`, `test_invariants.py`),
  `results/*.json`, `scripts/check_paper_numbers.py`.

## Scope (do not widen)

Evaluate ONLY: **(C)** are all claims supported by accurate evidence, or explicitly scoped until
they are; **(A)** would some TMLR subcommunity find it interesting. Do **not** reject on novelty,
significance, or the absence of real silicon.

## Method

1. **Reproduce.** Build the venv, run `./run_all.sh`; record `DONE`, stage-0 invariants, stage-9
   audit; independently recompute ≥5 headline numbers from `results/*.json`; compile the PDF.
2. **Read `paper/bouncer.tex` end to end.** Treat every quantitative and theoretical claim as a
   hypothesis to falsify; default to refutation.
3. This revision responds to a prior review whose three decisive findings were: (i) the re-trust
   evidence drove a bare `GateFSM` with a 1-window re-gate surrogate instead of the real CUSUM,
   and a correlated audit produces horizon-scaling re-trust the claimed geometric `T_reprobe`
   bound does not cover; (ii) all numeric bounds used detection-only `D_det` while A2 defines a
   detection-plus-re-trust `D`; (iii) Proposition 1's leakage threshold `γ/2` was contradicted by
   the released `f=0.8` result (correct form: clean margin `Δ_clean − K`). The claimed fixes are
   below — **verify each independently; do not take the fix on faith.**

## Prior (R4) findings and claimed (R5) fixes — verify each

1. **Re-trust evidence through the real path.** Claimed fix: `experiments/exp_retrust.py` part (B)
   now instantiates the full `Bouncer` (`C.make_bouncer('full')`) and steps it via `b.step(obs)` —
   the real Tier-B CUSUM (with its true ~12-window re-accumulation delay after a false re-trust)
   and the real FSM — under an AR(1) audit with tunable correlation ρ. Results
   (`results/retrust.json`): reseeded/near-i.i.d. audit gives ≈0 false re-trusts (fully-open
   fraction 0.008–0.067 across parts A and B); a correlated audit inflates it (0.225 at ρ=0.95,
   reproducing your construction through the released controller). The paper (A2 +
   §eval-retrust) now states `D` as a **measured assumption** scoped to the reseeded regime, with
   correlated-audit inflation a **named limitation** — no "finite/design-controlled", no
   geometric-`T_reprobe` claim. **Verify:** does part (B) genuinely exercise the real CUSUM+FSM
   (check `bouncer.py`'s 'full' branch and `cusum.py`'s auto-reset)? Do the JSON numbers match the
   prose? Is any "design-controlled"/"geometric"/"corrected in ~1 window" residual left anywhere?

2. **`D_det` vs `D_open` consistency.** Claimed fix: `bouncer/theory.py` (`regret_bound`),
   `bouncer/cusum.py` (`detection_delay_approx`), `experiments/exp_theory.py`, and the paper's
   knobs paragraph + §eval-retrust all state that every numeric floor (P1's 12.4; theory
   15.1/7.8/5.9; long-attack 123.6, 11.9-vs-2.52) uses the initial-delay approximation
   `D_det = H/(K−Δ)`, **valid where re-trust ≈ 0 as measured**, and that Lorden/Siegmund forms are
   approximations, not upper bounds; `eq:floor`'s first underbrace is now "detection + re-trust".
   **Verify:** is the scoping present at every site that reports a Lemma-1 numeral, and does no
   docstring still assert `≤ D·r_max` as an unscoped upper bound?

3. **Proposition 1 clean-margin threshold.** Claimed fix: the statement and proof now use
   `(1−f)(r̄_clean − r̄_att) ≳ Δ_clean_R − K` (up to O(σ) noise, a realized per-window event), with
   the measured crossing: f=0.6 → E[Δ̂_R]≈0.084<K=0.1, TPR 0.975 (detects); f=0.8 → ≈0.227>K,
   TPR 0.075 (evades). All "degrades smoothly"/"collapses as f→1" narratives (abstract, eval §P4,
   discharge table, README) replaced by the sharp 0.6–0.8-band crossing. **Verify** the algebra
   (spared gap 0.37, attacked gap −0.344) and the consistency of the cliff narrative everywhere.

4. **Scope residuals.** Claimed fixes: `related_work.tex` "any of them"/"applicable to any" now
   scoped to the set-local, reseed-identifiable class; its 17 markdown `*emphasis*` asterisks
   (previously rendered literally in the PDF) converted to `\emph{}`; `bouncer/environment.py`
   docstring lists A1–A6 + set-locality + reseed-identifiability; README: "characterized
   boundary"→demonstrated, Lemma summary now three-term with re-trust scoping and the
   correlated-audit limitation, own-reward paragraph states it does **not** fix prefetch;
   0.581%→0.580% (measured 0.580455); `hardening/state.json` carries a `_HISTORICAL_NOTE`
   labeling it an R1-era snapshot. **Verify** each, and `pdftotext` the compiled PDF to confirm no
   literal asterisks remain.

## Also hunt for NEW defects this revision introduced

The AR(1) construction in `exp_retrust.py` part (B) not being a fair probe of the released
dynamics (e.g., its noise scale vs the harness σ_Δ — the docstring discloses this; is the
disclosure adequate?); a prose numeral disagreeing with regenerated `results/*.json`; the A2
measured-assumption framing contradicting the Lemma statement anywhere; any place where the
scoping "valid where re-trust ≈ 0" is missing from a bound-bearing claim.

## Output format

1. **Reproduction record** — DONE? invariants pass? audit pass? numbers you reproduced.
2. **Per-claim evidence audit** — table: *Claim* | *Verdict* {SUPPORTED / OVERSTATED /
   UNSUPPORTED} | *evidence + `file:line`*. Cover the four items above and any new defects.
3. **TMLR criteria** — (C) Yes/No with reasons; (A) Yes/No.
4. **Recommendation** — Accept / Accept-with-minor / Reject, with the load-bearing reasons.
5. **Prioritized next steps** — table: priority, file/section, required?, effort, action.

Cite `file:line`, prefer refutation. If a claim is now correct, say so plainly. If a fix created a
new problem, that is the most valuable thing you can report.
