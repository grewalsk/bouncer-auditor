# Current revision status (canonical pointer)

**This file is the single source of truth for the artifact's current verification status.**
Everything else in `hardening/` (`state.json`, `TMLR_R1_RESPONSE.md`, `DELTA_REPORT.md`,
`nodes/`, `manifests/`) is a **historical snapshot** of earlier hardening loops and earlier
review rounds; those files' self-reported counts, page numbers, and no-overclaim verdicts
describe the state *at the time they were written*, not the current artifact.

Current facts (regenerate with `./run_all.sh`; verify against `git log`):

- Revision series: `revision/tmlr-r2` branch, rounds R2 onward responding to adversarial
  TMLR-calibrated reviews (see `REVIEW_PROMPT_R*.md` for each round's pinned commit).
- Number audit (`scripts/check_paper_numbers.py`, run_all stage 9): a **literal-presence
  regression tripwire** (not a semantic audit); the current count is printed by the script —
  do not trust counts quoted in historical files.
- Paper: `paper/bouncer.pdf`, TMLR format (page count printed by run_all stage 8).
- Guarantees as currently stated: Lemma 1 = three-term **expected**-regret bound under A1–A6
  (exposure term additionally has a high-probability Hoeffding envelope); Proposition 1 =
  expectation form + **sustained-evasion** form (range-`2r_max` Hoeffding + CUSUM block
  containment, under an explicit temporal-independence premise). All D_det-based numerals are
  conditional plug-in illustrations, not standalone bounds.
- Known scoped limitations (stated in the paper): sub-resolution slow-bleed coverage hole;
  correlated-audit inflation of A2's D; single-trace ChampSim replacement study; Tier-A maps
  unswept in E3; synthetic-only warmup/predictor evidence; P4's within-region pools are
  global-pool intersections (≈2.7% empty-pool fallback per window), approximating Prop 1's
  fixed within-R construction.
