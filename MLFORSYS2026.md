# NeurIPS 2026 MLForSys workshop package

This branch contains a focused, non-archival workshop version of Bouncer.  The
2026 OpenReview venue is live for December 11, 2026, but as of August 1 its
linked workshop site still displays the 2025 call.  The package therefore uses
the official NeurIPS 2026 style while conservatively enforcing the last
published MLForSys rule: at most four main-text pages, with references and an
optional appendix outside the limit.

## One-command rebuild

```bash
./run_ml4sys.sh
```

This command trains and evaluates the controller, checks every workshop
headline against the released JSON, compiles the paper, and verifies that the
main text ends by page 4 and references begin on page 5.

## Added trained-controller evidence

`experiments/exp_trained_controller.py` trains a four-PC logistic insertion
policy from future-reuse labels derived from independent seeded training and
validation traces.  At deployment, predicted-reusable lines are inserted and
predicted-streaming lines are bypassed; LRU is the fallback.  A controlled
concept shift reverses the PC/reuse association while keeping the PC histogram
exactly uniform.  Fixed secret leader sets avoid the state-reset confound that
the TMLR paper identifies for stateful cache replacement.

The experiment is intentionally modest and exactly scoped: a set-associative
trace replay, not ChampSim, a production controller, or end-to-end IPC.  Its job
is to demonstrate the missing learned-controller mechanism.  The pre-existing
ChampSim evaluation remains a separate real-simulator boundary study.

Headline results across 12 deployment seeds:

- validation accuracy: 96.28%;
- pre-shift hit rate: learned 0.4375, LRU 0.3276, Bouncer 0.4237;
- post-shift hit rate: learned 0, LRU 0.3279, Bouncer 0.2869;
- 12/12 detections, one-window mean delay;
- PC-histogram total variation 0 and zero input-OOD alarms;
- 87.5% of the clean learned gain retained and 87.5% of the shifted fallback
  loss recovered.

The authoritative outputs are `results/trained_controller.json`,
`figures/trained_controller.pdf`, and
`paper/mlforsys2026/bouncer_ml4sys.pdf`.
