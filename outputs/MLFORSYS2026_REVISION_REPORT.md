# MLForSys 2026 major-upgrade report

## Implemented

1. **Traffic-aware stratified leaders.** The hottest eighth of sets holds 68.2%
   of Zipf-1.2 request mass. Uniform leaders estimate the harmful follower gap
   with the wrong sign (`-0.193` target versus `+0.055` estimate), mean bias
   `+0.247`, and detection in 4/12 seeds. Pre-shift hot/cold strata with
   follower-request weighting produce a `-0.178` target, `-0.179` estimate,
   mean bias `-0.0006`, and detection in 12/12 seeds.

2. **Evidence-adaptive audit allocation.** The stateless trained-controller
   replay starts with two leaders per arm, rotates through an eight-candidate
   cohort, expands on suspicious evidence, and shrinks after four stable
   windows. It averages 2.03 leaders per arm with no clean alarms. At shift
   severities 0.375 and 0.5 it detects 11/12 and 12/12 seeds, versus 10/12 and
   11/12 for fixed eight leaders per arm; at maximal shift it detects 12/12 with
   two leaders per arm.

3. **State-preserving shadow metadata.** In the 20-window multiplicative
   warm-up cell, reset rotation measures `0.015` for a true `0.300` policy gap.
   Fixed leaders measure `0.299`; shadow-updated policy counters measure `0.298`.
   The accounting model uses two 8-bit counters per set: 128 B for 64 sets and
   4 KiB for 2048 sets. This is not a cache-content replica or RTL synthesis.

4. **Finite-population and PSEL characterization.** At severity 0.25, exact
   hypergeometric leader overlap predicts an across-seed gap standard deviation
   of `0.063`, versus `0.066` measured, and a one-window probability `0.649` of
   falling below `K`. Bouncer gates 7/12; PSEL-8 and PSEL-10 each gate 3/12,
   with conditional delays 4.33 and 15.33 windows from the same gap-crossing
   event.

## Paper and artifact status

- 61/61 numerical and boundary checks pass.
- Main text ends on page 4; references begin on page 5.
- Nine pages total: four main-text, two references, three appendix.
- Every PDF page was rendered and visually inspected; no clipping, overlap,
  undefined citations, or overfull boxes remain.
- The paper explicitly distinguishes the fitted trace-replay controller from
  the hand-designed ChampSim LIP/SRRIP boundary experiment.

## Remaining scope

The upgrades are controlled mechanism evidence. They do not establish
application-level generalization, IPC benefit, full stateful cache-content
shadowing, calibrated sequential error control, RTL cost, or production
security.
