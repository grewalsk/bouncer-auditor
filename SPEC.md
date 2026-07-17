# Bouncer — Off-Policy Competence Auditor for Learned Microarchitectural Controllers
Spec v0.2 · implemented by this artifact

A runtime monitor + trust gate that bounds the worst-case cost of a learned
microarchitectural controller (prefetcher, replacement policy, memory scheduler,
branch predictor) to that of a known-safe heuristic, under both adversarial
steering and benign distribution shift, without POMDP/belief-state machinery and
without ever sitting on the datapath's critical path.

## 1. Formal setting
A learned controller `C` is invoked at decision points `t = 1,2,…`. At each it
observes microarchitectural state `xₜ ∈ ℝ^d`, emits action `aₜ`, and after a
short horizon yields a bounded reward `rₜ ∈ [0, r_max]` (prefetch hit×timeliness,
cache hit, −latency, branch correct). `C` was validated on `D_val`. A fixed safe
fallback `π₀` has a known competence floor.

**Competence advantage** over a window `W`:
`Δ_W = (1/|W|) Σ_{t∈W} (rₜ^C − rₜ^{π₀})`. `rₜ^{π₀}` is counterfactual; §4
estimates it without counterfactuals via set-dueling.

**Off-policy condition.** Off-policy at `W` iff `Δ_W < τ`. This single scalar
unifies the two threats: an adversarial push toward `C`'s decision boundary, and
benign drift off `D_val`. Both manifest as `Δ_W` falling.

## 2. Threat model
- **Adversary:** a co-located tenant sharing `C`, issuing arbitrary accesses,
  knowing the design (Kerckhoffs). Goal: DoS the victim or steer `C` into a
  covert channel. Online-learning poisoning is an extension (GATED freezes
  learning). Out of scope: physical/fault attacks, weight tampering.
- **The secret:** the per-epoch RNG seed assigning dueling sets, never exposed
  through any architectural channel.
- **Headline (adaptive):** mimicry — keep Tier-A statistics in-distribution while
  degrading `C`. Defeated by the secrecy + reseeding of the competence sampler
  (Prop. 1); an attacker who identifies the dueling sets defeats it, which is why
  the randomized-sampling ablation is the headline experiment.

## 3. Architecture (two-tier)
Cheap signals are spoofable; the unspoofable signal is expensive. Run the cheap
tripwires always; let them gate the expensive confirmer.

- **Tier-A (hot, off-crit-path, few adds/dec):** `S_in` covariate-shift sketch,
  `S_dec` confidence collapse, `S_res` forward-model innovation (CUSUM).
- **Tier-B (warm, mgmt core/fw, epoch-grained):** `Δ̂_W` competence via
  randomized-secret set-dueling → one-sided CUSUM vs `τ`.
- **Gate FSM:** `TRUSTED → SUSPECT → GATED → PROBING`.

Hysteresis (τ to enter GATED, τ+Δ_hys to leave PROBING) + minimum dwell prevent
thrash; PROBING makes re-trust measured, not timed. (Refinement surfaced by the
build: background Tier-B may drive TRUSTED→GATED directly so pure mimicry, which
keeps Tier-A silent, cannot evade.)

## 4. Tier-B: competence via randomized-secret set-dueling (the spine)
Partition the resource (cache sets / banks / PC-hash buckets) into three pools,
reseeded each epoch from a hardware RNG, unobservable to software: Leader-L
(`n_L` sets, run `C`), Leader-F (`n_F` sets, run `π₀`), Follower (rest, run the
winner). Estimator `Δ̂_W = r̄_L − r̄_F` (measured, not counterfactual).

Under effectively independent bounded samples, concentration → detection latency:
`Var(Δ̂_w) ≲ (r_max²/4m_eff)(1/n_L + 1/n_F) =: σ_Δ²`. Boundedness alone does
not imply this scaling. The chain **pool size → σ_Δ →
CUSUM threshold H → detection delay D → regret floor** is the central design
dependency. Detector: one-sided lower CUSUM, `Cₜ⁻ = max(0, Cₜ₋₁⁻ + (K − Δ̂))`,
`K = τ + γ_detect/2`, alarm at `Cₜ⁻ > H` (resets on alarm).

## 5. Tier-A: cheap tripwires
- `S_in` — dense random projection with projected mean/std reference;
  spoofable (monitored marginals held fixed), high-sensitivity.
- `S_dec` — action-entropy collapse / max-Q margin / TD magnitude; nearly free
  where confidence is already in silicon.
- `S_res` — 18-coefficient linear forward model `g:(x,a)→r̂` at `d=16`;
  two-sided CUSUM on the
  innovation `e = r − r̂`; catches "the world responds differently than at
  validation" even when input marginals look clean.

Tier-A never gates on its own — it only escalates to SUSPECT (raises Tier-B duty
cycle), so its false positives cost energy, never correctness.

## 6. Guarantees (no POMDP)
- **Lemma 1 (safety floor):** with bounded normalized window reward, expected
  fully-open windows per episode ≤ `D`, marginal false-alarm rate ≤ `α`, total
  transient cost per false-alarm episode ≤ `c_sw`, and secret uniform audit
  exposure ≤ `φ_P`:
  `E[Σ_w(r̄_w^{π₀}−r̄_w^{Bouncer})] ≤ N_ep·D·r_max +
  φ_P·T_att·r_max + α·T·c_sw`. Only the exposure term receives the separate
  high-probability envelope. `H/(K−Δ_true)` is a mean-delay approximation, not
  an upper bound on `D`.
- **Prop. 1 (mimicry resistance):** with secret uniform Leader-L/F assignment,
  evading GATE while degrading the victim requires `C` to earn ≥ r^{π₀}+τ on a
  secret random subset — incompatible with degrading the exchangeable victim sets.
  Evasion budget bounded by σ_Δ; a leaked fraction `f` of the assignment biases
  Δ̂ up by ~f·(degradation). Caveat: exchangeability is in expectation; a
  redistributive attack preserving the global mean needs per-domain dueling.

## 7. Attack-vs-drift triage (secondary; detection doesn't depend on it)
Logistic model over `(ΔS_in, ΔS_res, co-tenant-corr, abruptness)`. Drift: slower,
phase-correlated, self-consistent. Attack: abrupt, boundary-targeted (high S_res,
low S_in), co-tenant-correlated. Misclassification only mis-selects between
equally-safe responses.

## 8–12. Instantiation, overhead, evaluation, build plan, hyperparameters
See `paper/bouncer.tex` §8–12 and `champsim_plugin/champsim_knobs.md`. Pinned
operating point: `n_sets=2048, n_L=n_F=32, m=64, τ=0.05, K=0.10, H=0.8`. Targets
Illustrative storage: 406 bytes at 16 bits per coefficient/statistic (0.155% of
a 256 KB SRAM). The released Python uses floating point; quantized fidelity,
RTL area, energy, and timing are unmeasured. Estimator/gate work is organized
off path, but the per-access tag lookup and output mux remain.

## 13. Risks (each tied to an in-spec mitigation)
- Counterfactual cost (memory scheduler) → model-based Δ̂, scoped last.
- Mimicry on competence itself → holds only for secret sets; quantified as the P4
  randomization-budget vs detection-power tradeoff.
- Ground-truth labeling → anchor to a measured competence drop beyond a margin.
- Overhead vs sensitivity → the minimal-overhead operating point (the §4 knee) is
  the result, reported as a Pareto curve.
