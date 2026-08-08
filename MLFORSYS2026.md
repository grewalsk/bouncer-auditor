# NeurIPS 2026 MLForSys workshop package

This branch contains a focused, non-archival workshop version of Bouncer. The
[2026 call](https://mlforsystems.org/call_for_papers.html) sets an August 29,
2026 deadline and a strict four-page main-text limit, excluding references and
an optional appendix. It allows non-anonymous submissions and requires the
NeurIPS 2026 format. This package vendors the June 23 official style file from
the linked NeurIPS archive (SHA-256
`c3fc2894e83d2517ca18b66741d6c595986d97957dc08ec08bb2125a7ec4555a`).

## One-command rebuild

```bash
./run_ml4sys.sh
```

The command regenerates the mechanism diagram, runs the maximal, graded-shift,
traffic-stratified, adaptive-allocation, and shadow-state studies, regenerates
their JSON and figures, checks 61 manuscript claims and boundary values, compiles the
paper, and verifies that the main text ends on page 4 and references begin on
page 5. The workshop path needs NumPy, Matplotlib, and a LaTeX toolchain; the
repository's complete environment remains pinned for the full artifact.

## What the trained-controller study establishes

`experiments/exp_trained_controller.py` trains a four-PC logistic cache-insertion
policy from future-reuse labels on independent seeded training and validation
traces. Predicted-reusable lines are inserted, predicted streams are bypassed,
and true LRU is the fallback. At deployment, the PC/reuse association changes
while each PC still occurs exactly 25% of the time in every set-window. Because
the model score is a deterministic function of PC, both the PC histogram and
the score distribution have total-variation distance zero through the shift.

`experiments/exp_trained_characterization.py` replaces the single maximal
demonstration with a fixed-parameter operating-characteristic study: nine shift
severities, a 16-window ramp, two PSEL counter widths, an adjacent-window A/B
diagnostic, four cache/reuse configurations, and a Zipf/correlated-shift
negative control. The leader sets are fixed to preserve cache state; secrecy is
not tested and is not needed for this benign-shift experiment.

`experiments/exp_trained_upgrades.py` adds three deliberately scoped repairs.
Pre-shift activity strata put both arms in the hot and cold traffic classes and
aggregate their contrasts by follower request mass. An evidence-adaptive audit
rotates two leaders per arm through an eight-candidate cohort and temporarily
expands to eight. A separate counter-like warm-up model maintains two 8-bit
shadow counters per set so leader rotation can restore policy state. The first
two experiments use the stateless trained controller; the shadow experiment is
not a full cache-content model or RTL implementation.

Headline results over 12 seeded repeats per cell:

- validation accuracy 96.28%, majority baseline 50.82%, and log loss 0.1603;
- at maximal shift, learned/LRU/Bouncer hit rates change from
  0.4375/0.3276/0.4237 to 0/0.3279/0.2869, with 12/12 one-window gates;
- with fixed `K=0.02, H=0.12`, detection is 10/12 at 37.5% shifted sets,
  11/12 at 50%, and 12/12 at 62.5% or more;
- at 12.5% shifted sets, the mean gap remains above `K`, yet 1/12 runs gates;
- at 25% severity, the exact hypergeometric leader-overlap model predicts gap
  standard deviation 0.063 versus 0.066 measured; Bouncer gates 7/12 while
  PSEL-8 and PSEL-10 each gate 3/12;
- the 16-window ramp gates 12/12, 4.75 windows on average after the smoothed
  gap first crosses `K`;
- the familiar 87.5% retention/recovery value is the expected 7/8 partition
  allocation ceiling, not an empirical general-performance estimate;
- simulator shadow replay gives the homogeneous estimator mean bias -0.0003 and
  RMSE 0.0104;
- under Zipf-1.2 traffic, uniform leaders have bias +0.247 and gate only 4/12,
  while the activity-stratified estimate has bias -0.0006 and gates 12/12;
- the adaptive audit averages 2.03 leaders per arm with no clean alarms and
  matches or improves fixed-eight detection in all tested shifted cells;
- for the slow warm-up cell, reset rotation measures 0.015 of a true 0.300 gap,
  while fixed leaders and shadow state measure 0.299 and 0.298.

These repeats measure variability within one controlled synthetic family, not
generalization across applications. The study does not establish a calibrated
false-alarm guarantee, IPC gains, hardware overhead, or production security.

Authoritative outputs are `results/trained_controller.json`,
`results/trained_characterization.json`, `figures/trained_controller.pdf`,
`results/trained_upgrades.json`, `results/warmup_predictor.json`,
`figures/trained_characterization.pdf`, `figures/trained_upgrades.pdf`, and
`paper/mlforsys2026/bouncer_ml4sys.pdf`.
