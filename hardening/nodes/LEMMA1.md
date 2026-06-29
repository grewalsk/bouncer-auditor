# NODE LEMMA1 — Safety floor / bounded-regret envelope (Lemma `lem:floor`)

**Verdict: DONE at defended=2.** The four-bucket accounting proof is a valid
upper envelope on regret-vs-fallback *in the controller's own reward metric r*,
and the two slack constants (D, α) are tied to Siegmund at the realized
operating point with empirical corroboration (ARL ratio 0.998; loose/tight/
measured = 15.1/7.8/5.9 IPC·win at N_ep=6, ordering `measured ≤ tight ≤ loose`
holds at every N_ep ∈ {1..6}). **Scope caveat (binding):** the floor is in r,
not end utility — the r≈utility gap is N1's territory and is NOT certified here.

---

## 1. The claim and the four-bucket partition (tex:308–340)

Lemma `lem:floor` (eq:floor): under assumptions A1–A5, w.p. ≥ 1−δN_ep,
```
Σ_t (r_t^π0 − r_t^Bouncer)  ≤  N_ep · D · r_max  +  α · T · c_sw
```
Proof partitions the T windows into four disjoint buckets and bounds the
positive regret contribution of each:

| Bucket | Windows | Per-window regret vs π0 | Total | Code anchor |
|---|---|---|---|---|
| (i) GATED | runs π0 | **0** (modulo switch transient, counted in iv) | 0 | `gate_fsm.py` GATED→action=fallback; `bouncer.py` routes π0 when gated |
| (ii) pre-detection | ≤ D per episode, N_ep episodes | ≤ r_max (A1) | **N_ep·D·r_max** | D = `cusum.detection_delay_approx(K,H,Δ_true)` = H/(K−Δ_true) |
| (iii) false alarm | ≤ αT (A3) | ≤ c_sw (A4) | **α·T·c_sw** | α = `cusum.false_alarm_rate_per_window` = 1/ARL0 |
| (iv) trusted-and-better | C ≥ π0, gate open | **≤ 0** (non-positive) | drops out | `set_dueling` Δ̂≥τ ⇒ trust C; these windows can only *help* |

Only buckets (ii)+(iii) carry strictly positive regret; (i) is exactly zero and
(iv) is non-positive (controller, when trusted, is at least as good as π0 by the
trust condition Δ̂≥τ — windows where it is strictly better make regret negative,
which is why measured cumulative regret goes negative in P1, tex:496–498). The
per-episode δ failure probabilities union-bound to δN_ep. **This is a textbook
disjoint-bucket upper bound: each bucket's contribution is independently capped
and summed, so the sum is a valid envelope** — no double-counting (switch
transient is attributed once, to iii), no missing positive bucket (i=0, iv≤0).

## 2. D and α tied to Siegmund at the REALIZED params

K = τ + γ/2 = 0.05 + 0.10/2 = **0.10**; H = **0.8**; σ_Δ(m=64,n_L=n_F=32) =
√((1/256)(1/32+1/32)) = **0.015625** (the CONC identity, re-used here as input).

**Detection delay D (bucket ii).** Deployed detector runs in the *strong-drift*
regime: during a drop, standardized increment drift (K−Δ_drop)/σ_Δ = (0.10−
(−0.344))/0.015625 = **28.4** (paper says "≈28", tex:659 — confirmed). At this
drift the Siegmund ARL collapses to the deterministic limit D ≈ H/(K−Δ_true).
results/theory.json D = **1.8018** = 0.8/(0.10−(−0.344)); recomputed from
`detection_delay_approx(0.10, 0.8, −0.344)` to machine precision. The loose
bound is then exactly linear: N_ep·D·ipc_slope·r_max = **2.5225 per episode**
(verified constant across N_ep=1..6 in theory.json).

**False-alarm rate α (bucket iii).** In-control, clean Δ̄ ≫ K so standardized
drift δ=(K−μ)/σ_Δ is large-negative; ARL0 grows exponentially in H/σ_Δ =
0.8/0.0156 ≈ 51. Live `siegmund_arl(0.10, 0.8, μ_clean, 0.0156)` returns the
1e18 clamp for μ_clean ∈ {0.3,0.5,0.7} ⇒ α ≈ 1e-18 ⇒ **α·T·c_sw ≈ 7.8e-16**
(T=780, c_sw≤r_max=1) at N_ep=6. The false-alarm bucket is numerically
negligible at this operating point; the entire loose envelope is the detection
term. This is corroborated empirically by P1 (0/40 clean false alarms,
tex:562), so bucket (iii) being ~0 is not just a formula artifact.

**Siegmund accuracy (the "ARL ratio 0.998").** results/theory.json ARL sweep:
ARL0 emp/th geomean = **0.99758**, ARL1 emp/th geomean = **1.00238**
(recomputed live from the H∈[1,6]σ sweep). The formula is validated in the
small-drift heavy-overshoot regime where the 1.166 overshoot correction matters;
the deployed regime is the opposite (strong-drift) limit where D→H/(K−Δ) is even
more robust. So the constants feeding buckets (ii)/(iii) are calibrated, not
asserted.

## 3. Valid-envelope confirmation (the load-bearing check)

The ordering **measured ≤ tight ≤ loose holds at EVERY N_ep** (re-ran from
theory.json):

| N_ep | measured | tight | loose | meas≤tight | tight≤loose |
|---|---|---|---|---|---|
| 1 | 0.989 | 1.306 | 2.523 | ✓ | ✓ |
| 2 | 1.975 | 2.611 | 5.045 | ✓ | ✓ |
| 3 | 2.968 | 3.917 | 7.568 | ✓ | ✓ |
| 4 | 3.950 | 5.223 | 10.090 | ✓ | ✓ |
| 5 | 4.953 | 6.528 | 12.613 | ✓ | ✓ |
| 6 | 5.922 | 7.834 | 15.135 | ✓ | ✓ |

At N_ep=6: loose/measured = **2.56×**, tight/measured = **1.32×**. The loose
Eq.(floor) bound is a genuine (≈2.6×-conservative) upper envelope; the tight
variant (charging the realized gap q0−μ_C^att for D full-resource windows plus
the steady-state n_L/n_sets Leader-L cost over the rest of the attack, tex:662–
665) hugs the data to 1.32× while still dominating it. Both are valid; the loose
one is what Lemma `lem:floor` actually proves.

## 4. Honest limits (no overclaim)

- **(a) Reward-metric only.** The floor bounds Σ(r^π0 − r^Bouncer) in the
  controller's reward r (A1). It does NOT bound end-utility (IPC/latency)
  regret; the r≈utility map is audit-invisible (N1 owns this — on roms the
  proxy mismatch makes Bouncer *over-gate*, losing utility, which is the
  conservative/safe direction but still a real cost). LEMMA1 certifies the r-floor,
  full stop.
- **(b) D is high-probability, not worst-case.** A2 states D as a
  high-probability bound (mean H/(K−Δ) + a tail term shrinking with σ_Δ);
  the δ-failure events (a drop not detected within D) union to δN_ep. The
  envelope is the 1−δN_ep event, not deterministic. Honest and stated.
- **(c) Envelope validated on the synthetic harness.** The measured/tight/loose
  triple is from exp_theory.py's MultiPulse synthetic competence model, where D,
  σ_Δ, gap are all controllable. On ChampSim (champsim.json) competence is not
  directly controllable, so the floor appears as a "floor cap" (Bouncer ends at
  the prefetch-off floor on every trace) rather than a measured D-window
  excursion — consistent with, but not a fresh quantitative test of, eq:floor.
- **(d) c_sw bound assumed, not measured.** Bucket (iii) uses c_sw ≤ r_max; since
  α≈1e-18 here the bucket is negligible regardless of the exact c_sw, so this
  assumption is non-binding at the operating point (it would matter only at much
  smaller H where ARL0 is finite).

## 5. Constants (all traced)

K=0.10, H=0.8, σ_Δ=0.015625, Δ_drop=−0.344, D=1.8018, drift (K−Δ)/σ_Δ=28.4,
H/σ_Δ=51.2, loose-per-episode=2.5225, α·T·c_sw≈7.8e-16 (T=780),
ARL0 emp/th=0.99758, ARL1 emp/th=1.00238, N_ep=6: loose=15.135/tight=7.834/
measured=5.922 (loose/meas=2.56×, tight/meas=1.32×).
