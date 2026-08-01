# NeurIPS 2026 MLForSys workshop package

This branch contains a focused, non-archival workshop version of Bouncer.  The
live [2026 call](https://mlforsystems.org/call_for_papers.html) sets an August
29, 2026 submission deadline and a strict limit of
four main-text pages, excluding references and an optional appendix.  It allows
non-anonymous submissions and requires the NeurIPS 2026 format.  This package
vendors the June 23 official style file from the linked NeurIPS archive (SHA-256
`c3fc2894e83d2517ca18b66741d6c595986d97957dc08ec08bb2125a7ec4555a`).

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
- validation majority baseline: 50.82%; validation log loss: 0.1603;
- pre-shift hit rate: learned 0.4375, LRU 0.3276, Bouncer 0.4237;
- post-shift hit rate: learned 0, LRU 0.3279, Bouncer 0.2869;
- 12/12 detections, one-window mean delay;
- PC-histogram total variation 0 and zero input-OOD alarms;
- 87.5% of the clean learned gain retained and 87.5% of the shifted fallback
  loss recovered.

Intervals in the JSON and Figure 2 are two-sided 95% Student-t intervals over
the 12 deployment seeds (11 degrees of freedom).  Seeds randomize leader
placement and within-window access order inside one controlled workload family;
they are not twelve independent application traces.

The authoritative outputs are `results/trained_controller.json`,
`figures/trained_controller.pdf`, and
`paper/mlforsys2026/bouncer_ml4sys.pdf`.
