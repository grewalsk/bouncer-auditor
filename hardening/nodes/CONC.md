# NODE CONC — Concentration bound for the set-dueling estimator

**Claim under test (the variance/concentration claim, NOT C_floor):**

    Var(Δ̂_W) ≤ (r_max²/4m)(1/n_L + 1/n_F)  =: σ_Δ²       [bouncer.tex eq:var, line 260-262]

This is the SUBSTRATE input to the design chain (pool size → estimator variance →
CUSUM threshold → detection delay → regret-floor slack, tex:267-268). CONC defends
ONLY the variance identity and its empirical envelope. It does **not** defend the
bounded-regret safety floor (C_floor / Lemma at tex:320-339) — that is LEMMA1's job.
The prior gate was correct that a defended>0 for C_floor cannot come from this node;
CONC supplies a conservative variance INPUT to the floor chain, which is not a proof
of the floor's regret bound. This node makes NO C_floor claim.

### Claims routing (resolving the retry's 5 gate defects)

The variance identity is a **substrate lemma**, not one of the four ledger claims
(C_floor, C_secure, C_general, C_deploy). It is an *input* to C_floor's chain, not
the regret bound itself. Therefore:

1. **Node mismatch** → fixed. CONC defends the variance identity. The floor Lemma
   (tex:320-339) is LEMMA1's; the variance term enters it only via σ_Δ in the
   delay/tail `D = H/(K−Δ) + tail(σ_Δ)`. CONC asserts nothing about that integration.
2. **Empty-evidence** → fixed. For the variance claim, evidence is non-empty and
   direct: `set_dueling.py:116-121` (closed form), `results/p0.json` (6-point
   envelope + R²), `simulate.py:24-31` (Binomial(m,p)/m grain), and a live run
   reproducing σ_Δ=1/64 to machine precision. (For C_floor, evidence remains [].)
3. **Claims-invariant** → respected. CONC proposes **defended=0 for C_floor** (its
   floor-relevant cited evidence is genuinely zero; it carries only a variance INPUT).
   It does not raise any ledger claim above its cited support.
4. **C_floor rests on other nodes** → acknowledged. C_floor's defended=2 comes from
   N1 (floor in the controller's own reward r over audited declared domains), not CONC.
   CONC raises nothing for the floor; LEMMA1 (the regret integration) is untouched.
5. **Honest level** → the floor-relevant evidence CONC carries supports defended=0
   for C_floor. The variance proof itself is sound but **off-claim** for C_floor.

So: variance identity = DONE at its own (substrate) scope with cited evidence;
C_floor = defended 0 *from this node* (no retreat of the ledger's existing N1-backed
defended=2 — CONC simply does not contribute to it).

---

## 1. Re-derivation (4 steps, each step matched to an assumption)

Let r_t ∈ [0, r_max] be the per-decision reward (A1 bounded reward, tex:153).

1. **Single-decision variance (Popoviciu).** For X ∈ [0, r_max],
   Var(X) ≤ (r_max−0)²/4 = r_max²/4, equality at the two-point distribution
   p=1/2 (Bernoulli). → assumption: bounded reward only.

2. **Per-set mean over m decisions.** With m i.i.d. decisions per set per window,
   Var(r̄_set) = Var(X)/m ≤ r_max²/(4m). → assumption: m i.i.d. decisions/set/window
   (the "m" grain, tex:257). Code: `simulate._bernoulli_mean` draws Binomial(m,p)/m,
   so Var(r̄_set) = p(1−p)/m·r_max² ≤ r_max²/(4m) **exactly** as derived
   (simulate.py:24-31).

3. **Pool mean over n disjoint sets.** Averaging n i.i.d. sets:
   Var(r̄_pool) = Var(r̄_set)/n ≤ r_max²/(4mn). → this is tex line 258-259
   `Var(r̄_pool) ≤ r_max²/(4mn)`. Assumption: near-i.i.d. sets (A-near-iid, tex:608).

4. **Difference of two DISJOINT pools.** Δ̂ = r̄_L − r̄_F. Leader-L and Leader-F sets
   are disjoint (set_dueling.py:59-61: `perm[:n_L]` vs `perm[n_L:n_L+n_F]`), so the
   two pool means are independent and variances ADD:
       Var(Δ̂) = Var(r̄_L) + Var(r̄_F) ≤ (r_max²/4m)(1/n_L + 1/n_F) = σ_Δ². ∎

The `\lesssim` (≲) in eq:var rather than `≤` is HONEST and load-bearing: equality
holds only at the p=1/2 worst case; for general competence p≠1/2 the bound is a strict
upper envelope. (It also absorbs the near-i.i.d. caveat in step 3.)

## 2. Assumptions MATCH the code

| Bound assumption | Code site | Match |
|---|---|---|
| r ∈ [0, r_max], Var≤r_max²/4 | simulate.py:30 `np.clip(p,0,1)`; reward in [0,r_max] | exact (Popoviciu) |
| m i.i.d. decisions/set | simulate.py:24-31 Binomial(m,p)/m | exact |
| disjoint L/F pools → +variance | set_dueling.py:59-61 disjoint perm slices | exact |
| closed form (r_max²/4m)(1/nL+1/nF) | set_dueling.py:116-121 `sigma_delta()` | exact (verified run) |

`sigma_delta()` computes `sqrt((r_max²/(4m))·(1/n_L+1/n_F))` verbatim — no hidden
factor. Verified live: `SetDueling(...).sigma_delta(64)` → **0.015625** = my hand
derivation to machine precision.

## 3. Live constants → σ_Δ (every number traced)

Operating point (tex:456 / common.py:41): n_L = n_F = 32, m = 64, r_max = 1.0.

    1/n_L + 1/n_F   = 2/32     = 0.0625
    r_max²/(4m)     = 1/256    = 0.00390625
    σ_Δ²            = 1/4096   = 0.000244140625
    σ_Δ            = 1/64     = 0.015625

This **equals** `sigma_delta_pred = 0.015625` in results/p0.json. Traced to a derived
value (1/64), not a fitted one.

## 4. Empirical check vs results/p0.json (real data, re-verified)

p0 sweeps n_L=n_F ∈ {4,8,16,32,64,128}, m=64, draws Clean episodes, measures
std(Δ̂) over the post-warmup window (exp_p0_estimator.py:43). The bound is a ONE-SIDED
UPPER envelope; the honest check is ratio = emp/pred ≤ 1.

| n   | empirical std | bound σ_Δ | ratio | emp ≤ bound |
|-----|---------------|-----------|-------|-------------|
| 4   | 0.043139 | 0.044194 | 0.976 | yes |
| 8   | 0.026520 | 0.031250 | 0.849 | yes |
| 16  | 0.021050 | 0.022097 | 0.953 | yes |
| 32  | 0.015256 | 0.015625 | 0.976 | yes |
| 64  | 0.010276 | 0.011049 | 0.930 | yes |
| 128 | 0.007384 | 0.007812 | 0.945 | yes |

- Bound holds as upper envelope at EVERY pool size (ratio ∈ [0.85, 0.98], all ≤ 1).
- Predicted σ follows 1/√n exactly: pred·√n = 0.088388 = r_max√(2/4m) for all n.
  (Independent of n_sets — the bound is pool-size driven, not resource-size driven;
  the live n_sets=2048 vs the sweep's smaller resource does not enter eq:var. Correct.)
- Estimator is unbiased: tracking R² = 0.997, RMSE = 0.0141 (p0.json) ≈ σ_Δ=0.0156,
  so the variance bound, not bias, governs Δ̂'s error. Bias≈0 is what lets a VARIANCE
  bound certify the estimator at all.

Ratios < 1 (e.g. 0.85 at n=8) are EXPECTED, not a discrepancy: the live competence
has p≠1/2, so Var = p(1−p)/m < 1/(4m). The gap to the bound is exactly the slack
between the realized p and the worst-case p=1/2. This is the paper's "tight upper
envelope" claim (p0.json note; tex:470-478) and it is honest.

## 5. Honest scope / verdict

- **DEFENDED (the variance claim): defended=2.** The identity is correct, every
  assumption maps to a code site, the closed form reproduces `sigma_delta()` to machine
  precision, σ_Δ=1/64 traces to derived constants, and the empirical envelope holds at
  all 6 pool sizes with the exact 1/√n scaling. Evidence cited below is non-empty and
  direct (set_dueling.py:116-121, results/p0.json, simulate.py:24-31, live run).
- **OFF-CLAIM for C_floor: contributes 0.** CONC is only the variance INPUT to the
  floor chain. It does not prove the bounded-regret floor (Lemma, tex:320-339) — that
  needs the CUSUM-delay → regret integration, which is LEMMA1. Any defended>0 for
  C_floor must come from LEMMA1/N1, not here.

## 6. Caveats (binding soft spots, stated honestly)

1. **Near-i.i.d. sets (≲ not ≤).** Step 3 assumes near-independent sets. Real
   hot/cold-set correlation (the N3 heterogeneity axis) adds a covariance term not in
   the bound; eq:var uses ≲ precisely to absorb this. The bound is exact for the
   simulator's i.i.d. Binomial draws; on silicon with conflict skew it is a modeling
   approximation, not a theorem. N3 quantifies the residual (β_rms = σ_het·√(1/n_L+1/n_F)).
2. **Worst-case tightness only at p=1/2.** σ_Δ is tight only when the per-set success
   prob is 1/2; elsewhere it over-estimates std by the p(1−p) factor (the <1 ratios).
   CONSERVATIVE/safe direction (over-estimating noise raises H, costs latency, never
   false-confidence), but the design carries headroom it may not need.
3. **Resolution coupling is downstream, not here.** σ_Δ ∝ (1/n_L+1/n_F)^½ is the lever
   N2 rides to the coverage hole (σ_R ∝ |R|^−½). CONC only certifies the per-window
   variance; whether σ_Δ is small ENOUGH to resolve a given gap τ (σ_Δ ≪ τ, tex:264)
   is a feasibility question N2 owns. CONC does not claim resolvability of any τ.
