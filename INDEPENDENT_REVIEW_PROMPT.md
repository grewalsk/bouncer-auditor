# Independent review prompt — Bouncer editorial/TMLR R8

You are an independent, adversarial TMLR reviewer and reproducibility auditor.
Do not assume the authors' audit is correct. Treat every self-reported fix and
verification result as a claim that must be tested.

## Artifact

- Repository: `https://github.com/grewalsk/bouncer-auditor`
- Branch to review: `editorial/tmlr-r8`
- Pre-edit baseline: commit `973fa10f1af4895825083d6d60f03e046743c079`
- Paper: `paper/bouncer.pdf`
- Source: `paper/bouncer.tex` and `paper/related_work.tex`
- Self-report under test: `EDITORIAL_AUDIT_R8.md`

Clone the repository, check out `editorial/tmlr-r8`, record the exact HEAD hash,
and read the paper end to end before relying on the audit report. Compare the
branch against the baseline commit to check that supported results, caveats,
assumptions, negative findings, citations, and reproducibility information were
not silently removed during editing.

## Decision rule

Judge the paper on TMLR's two relevant criteria only:

1. **Criterion C:** Are all claims supported by accurate evidence, or scoped
   until they are?
2. **Criterion A:** Would some machine-learning subcommunity find the work
   interesting?

Do not judge novelty, significance, likely impact, venue fit outside these two
criteria, or the absence of a real-silicon win. Do not import systems-conference
acceptance criteria into the recommendation.

## Reproduction

Run at minimum:

```bash
./run_all.sh
PYTHONPATH=. python3 scripts/check_paper_numbers.py
```

The second command is expected to report 40/40. Also compile and run the C++
self-test in `champsim_plugin/bouncer.cc`. Record commands, environment, exit
codes, regenerated-file differences, and any step you could not reproduce.
Distinguish experiments regenerated from code from figures rebuilt using
committed ChampSim logs.

Render every PDF page and inspect it visually. Check for clipped equations,
illegible figures or tables, bad page breaks, undefined references/citations,
overfull content, and inconsistent notation.

## Load-bearing technical checks

Independently audit at least the following:

1. **Causal routing.** Trace the ordering in `bouncer/bouncer.py` and
   `bouncer/simulate.py`. Verify that evidence from window `w` can affect routing
   only from window `w+1`. Try to construct a same-window look-ahead
   counterexample. Check the reported two-window P1 latency and 15-window
   re-trust value.
2. **Lemma 1.** Re-derive all three expected-regret terms from the definitions
   and implementation. Test concentrated traffic, repeated alarms, long attacks,
   false re-trust, and adaptive traffic. Separate the proved loose three-term
   result from the realized-gap/occupancy descriptive tracker. Verify the
   persistent-attack numbers: measured approximately 12.34–12.39, obsolete
   two-term approximately 2.52, tracker approximately 12.29, and loose plug-in
   approximately 123.6.
3. **Floor calculation.** Recompute
   `(32/2048)(0.5-0.156)(1.4)/1.3`, compare it with the measured mean and worst
   window, and decide whether the text calls it a mechanism calculation rather
   than a universal prediction.
4. **Estimator variance.** Check whether the `1/(mn)` scaling actually follows
   from the stated effective-independence premise. Ensure boundedness alone is
   not presented as sufficient.
5. **CUSUM.** Re-derive the zero-drift ARL limit and verify that the code uses
   `b^2`, not `b^2/2`. Check strict-versus-nonstrict alarm boundaries.
6. **E3 drift-SNR and R-latency.** Reproduce full/background sigma values,
   minimum drift at the trust boundary, the 2.0-to-13.875-window latency range,
   and TPR at the 10- and 20-window horizons. Check whether conclusions are
   limited to the tested grid.
7. **Warm-up/reseed experiment.** Inspect slice-state bookkeeping. Verify that
   nonsampled slices reset and only immediately consecutive same-policy
   assignments accumulate warm-up. Reproduce multiplicative attenuation from
   roughly 95% to 5% and the additive contrast near 0.300. Decide whether this
   supports only a synthetic mechanism claim or an unjustified real-predictor
   generality claim.
8. **Proposition 1.** Check the representative-sampling, exchangeability,
   intact-secret, and temporal premises. Recompute the exact-DP and exhaustive
   checks, including `125/32768 = 0.003814697265625`, and verify the corrected
   range-`2r_max` Hoeffding exponent.
9. **Tier-A/storage.** Match the paper to `bouncer/tier_a.py`: dense 16-by-8
   projection plus projected mean/std and an 18-coefficient forward model.
   Recompute the illustrative 404-byte, 0.154% count. Check that quantization,
   RTL area, energy, and timing remain explicitly unmeasured.
10. **ChampSim scope.** Verify what can actually be freshly regenerated, what is
    plotted from committed logs, and whether the real replacement result is
    presented as a boundary result rather than clean-case validation.

## Editorial audit

Evaluate the revision as prose, not only as code:

- Is the abstract an accurate map of the paper rather than a dense result dump?
- Are definitions introduced before use and are audit window, epoch, drop
  episode, fully-open window, exposure, and descriptive tracker kept distinct?
- Does the evaluation have a readable roadmap and do results clearly separate
  claim, evidence, assumptions, and limitations?
- Are theory statements readable without weakening or hiding their premises?
- Did compression remove redundancy without deleting information needed to
  evaluate the claims?
- Compare TeXcount and page count against the baseline and spot-check the Git
  diff paragraph by paragraph.

## Required report

Produce a copyable TMLR review containing:

1. A concise summary of the paper and the revision.
2. A per-claim evidence table with `SUPPORTED`, `OVERSTATED`, or `UNSUPPORTED`,
   exact `file:line` anchors, and at least one independently reproduced number
   for every load-bearing empirical claim.
3. Separate proof certificates for Lemma 1 and Proposition 1: assumptions,
   derivation skeleton, edge cases, and verdict.
4. A readability/notation table with concrete before-versus-after findings and
   remaining problems, each anchored to source lines or PDF pages.
5. A reproduction record listing successful, failed, and unverifiable steps.
6. Explicit **Yes/No** verdicts for Criterion C and Criterion A.
7. An **Accept**, **minor revision**, or **Reject** recommendation justified only
   by C and A.
8. A prioritized `NEXT STEPS` table. Each entry must state file/section,
   required versus optional, estimated effort, and expected effect on the
   verdict.

Be adversarial. A statement in `EDITORIAL_AUDIT_R8.md` that you cannot verify is
itself a finding. Do not merely list requested changes: determine whether the
current branch already satisfies each claim, and support every verdict with
source evidence.
