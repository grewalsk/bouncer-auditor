# N1 clean-isolation experiment: swap ONLY the reward signal on roms

**Question (from N1.md self-check, lines 136-142).** A skeptic argues roms over-gating
is a *threshold-tuning* artifact of the looser `(tau=0, H=0.25)` operating point forced
by noisier real Δ̂ — not a *proxy-fidelity* artifact. N1 claims the opposite and proposes
the decisive test: **hold `(tau, H, window, partition, FSM)` FIXED at the champsim
operating point and swap ONLY the reward signal** from per-set cache-hit to the
controller's own in-silicon reward. *"If over-gating disappears under the better proxy at
the same threshold, that proves the failure is proxy-fidelity, not threshold tuning."*

This is a **real ChampSim run** (not the Python harness): `champsim_bouncer` on
`654.roms_s`, 1M warmup + 9M sim, L1D `bouncer_pref` module. The only thing varying
across columns is `BOUNCER_REWARD`; everything else is byte-identical (one binary).
Reproduce: `./run_study.sh <reward> 30` then `python3 analyze.py`.

## Reward signals compared (all at the FIXED operating point, window=40000)

| mode | signal | attribution |
|---|---|---|
| `cachehit` | per-access cache-hit (the borrowed proxy; **baseline**) | per-access set (local) |
| `ownacc` | controller's OWN prefetch **accuracy×timeliness**: demand-use=+1 / evict-unused=0, in-module tracked, `pf_pending` cleared each reseed (leak-free across windows) | issuing-trigger set |
| `ownpf` | event-scoped useful/(useful+uncovered-miss) via the cache's `useful_prefetch` bit | per-access set (**leaks**: cache bit persists across reseed) |
| `ownpf_peraccess` | per-access `useful_prefetch` over ALL accesses | per-access set (local, **sparse**) |

## Result 1 — fixed operating point (window=40000): over-gating does NOT disappear

| metric | cachehit (baseline) | **ownacc (own reward)** | ownpf (leaky) | ownpf_peraccess (sparse) |
|---|---|---|---|---|
| unguarded_clean IPC | 1.139 | 1.139 | 1.139 | 1.139 |
| bouncer_clean IPC | 1.011 | **1.028** | 1.005 | 1.022 |
| unguarded_attack IPC | 1.08 | 1.08 | 1.08 | 1.08 |
| bouncer_attack IPC | 1.009 | **1.026** | 1.004 | 1.021 |
| **clean_tax** | **11.24%** | **9.75%** | 11.76% | 10.27% |
| **bouncer_atk vs unguarded_atk** | **−6.57%** | **−5.00%** | −7.04% | −5.46% |
| clean: windows gated | 35/47 | 18/47 | 18/47 | 6/47 |
| clean: mean Δ̂ (unguarded, unconfounded) | +0.0001 | +0.0000 | −0.0654 | −0.0046 |

**Swapping cache-hit → the controller's own reward, at the same threshold, does NOT make
over-gating disappear.** The best faithful own-reward (`ownacc`) recovers only ~1.5
points of an 11-point tax (11.24% → 9.75%); the gate still flickers (PROBING, 18/47
windows gated) and still loses to the attacked-but-ungated prefetcher (−5.0%). The two
other own-reward variants are no better. **This is the exact test N1 proposed, and it
fails:** over-gating persists under the better proxy at the same threshold.

### Why every reward reads Δ̂ ≈ 0 at this window
- **cachehit** Δ̂ has genuinely **negative** windows (−0.09, −0.11, −0.21, −0.22): the
  aggressive prefetcher really *depresses* per-set L1D hit rate in pollution episodes
  while raising IPC. N1's **sign-mismatch mechanism is real** — but it is rare (9/47
  windows) and the unconfounded mean is ≈0, not a clean negative.
- **ownacc** Δ̂ is 0.0000 in 40/47 windows with sparse ±1 spikes (n≈2 prefetch-relevant
  events per 32-set leader pool per 40k window). The −1 spikes are **cross-set leakage**:
  a prefetch triggered on a Leader-C set targets `blk+stride`, which lands on a *different*
  set — sometimes Leader-F — so the dueling mis-credits it. Prefetch benefit is
  **de-localized**; set-dueling needs a **set-local** reward.
- **ownpf_peraccess** is correctly set-local but the useful-prefetch *rate* at L1D on roms
  is ~0.15% (6810 useful / 4.5M accesses) → mean Δ̂ ≈ 0, below K=τ+γ/2=0.02 → still gates.

There is a **fundamental tension**: the cache-hit reward is *localizable* (per-set hit
rate) but a poor utility proxy; the own-accuracy reward is a faithful utility proxy but
*not cleanly set-localizable* (prefetches cross sets) — so its dueling Δ̂ collapses to 0.

## Result 2 — supplementary: the operating point (window length) is the dominant lever

Same reward signals, `(tau=0, H=0.25)` unchanged, **window 40000 → 200000 (5×)**.
(Attack onset `window 30` never fires at 9 windows, so attack columns = clean here.)

| reward | bouncer_clean IPC | clean_tax | windows gated | mean Δ̂ |
|---|---|---|---|---|
| cachehit | 1.138 | **~0%** | 0/9 (TRUSTED) | −0.0059 |
| ownacc | 1.138 | **~0%** | 0/9 (TRUSTED) | +0.0154 |

**At a 5× window the over-gate vanishes for BOTH the borrowed proxy AND the own reward
(clean_tax → ~0%).** Lengthening the measurement window — i.e. moving the operating point
— eliminates the over-gating that swapping the reward could not. This is precisely the
"looser operating point forced by noisier real Δ̂" the skeptic named (champsim.json:5-14).

## Verdict

**The clean isolation does NOT support N1's strong claim; it largely supports the skeptic.**

1. **Proxy fidelity is neither necessary nor sufficient** to explain roms over-gating. At
   the fixed operating point the better proxy leaves an 9.75% tax (over-gate persists);
   at a longer window even the *bad* proxy over-gates ~0%.
2. **The dominant cause is observability / operating point**, not reward sign: roms's
   prefetch benefit lives in ~31K rare, high-latency (176-cyc) misses and in cross-set
   prefetches that no bounded **set-local** reward captures densely enough at a 40k-access
   window. The signal is too sparse and too de-localized for the dueling estimator —
   exactly the SNR problem that forced `(tau=0, H=0.25)`.
3. **N1's sign-mismatch mechanism is real but minor** (genuine negative cache-hit windows
   exist), and it is swamped by the SNR effect; it does not control the over-gate.
4. The own reward is directionally better (only proxy with a non-negative, correctly-signed
   Δ̂; best clean_tax) but **cannot be cleanly set-dualized** for a prefetcher.

**Recommended correction to N1.md.** §4 ("Over-gating is a PREDICTION of the proxy,
confirmed on roms") and §5's verdict overclaim. roms is *not* "the clean empirical
confirmation that the limiting factor is proxy fidelity, not the dueling/CUSUM/FSM
machinery." The honest statement: roms over-gating is co-caused by (a) a low-SNR,
de-localized competence signal at L1D and (b) the short-window operating point that signal
forces; swapping to the controller's own reward at fixed threshold only dents it
(11.2%→9.7%), while lengthening the window removes it. The §8 "use the controller's own
reward" remedy is **insufficient by itself** for the memory-bound case; it must be paired
with a denser/latency-weighted, set-localizable reward and/or a longer epoch.

## Caveats (do not over-read)
- `ownacc`/`ownpf` carry known attribution limitations (cross-set, cross-window); the
  cleanest set-local own-signal (`ownpf_peraccess`) is the one that is fundamentally
  sparse. The conclusion "no reward swap fixes it at fixed window" holds across **all
  four** variants, which is the robust part.
- The window=200k probe also has fewer CUSUM steps (9 vs 47), so "fewer windows to
  accumulate" and "less per-window noise" both push toward less gating; both are facets of
  the same operating-point sensitivity, but it is not a pure per-window-SNR isolation.
- Single trace, single seed (hw_seed fixed). Multi-seed CIs would quantify the ±1-spike
  noise but would not change the qualitative verdict (Δ̂ mean ≈ 0 at the fixed window).
