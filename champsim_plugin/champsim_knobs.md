# §12 hyperparameters as ChampSim build knobs (pinned to the P0 sweep values)

These are the values the Python sweep selected as the minimal-overhead operating
point (the knee of the §4 latency/overhead Pareto). They map directly to
`BouncerConfig` in `bouncer.h`.

| §12 knob                  | symbol        | value            | ChampSim placement / note |
|---------------------------|---------------|------------------|----------------------------|
| dueling pool sizes        | `n_L, n_F`    | 32, 32           | reuse DIP/DRRIP sampled-set tags; secret reseed each epoch |
| total dueling sets        | `n_sets`      | 2048             | LLC set count (or PC-hash buckets for Pythia) |
| decisions / set / window  | `m`           | 64               | sets window length |W| ≈ m·n_sets ≈ 1.3×10⁵ decisions |
| trust threshold           | `tau`         | 0.05             | r_max-normalized competence margin |
| CUSUM reference slack      | `gamma_detect`| 0.10 ⇒ K=0.10    | K = tau + gamma/2 |
| Tier-B CUSUM threshold    | `tierb_H`     | 0.8              | ARL₀ ≫ 10⁶ windows at this point (Siegmund) |
| TRUSTED duty cycle        | `n_L/F_bg`    | 8, 8             | background pool size; SUSPECT raises to full 32 |
| Tier-A sample rate        | `1/k`         | 1/8              | sketch update fraction |
| RNG reseed period         | —             | 1 epoch          | from on-die TRNG/PUF; tag unobservable to SW |
| gate dwell / reprobe      | `T_dwell`, `T_reprobe` | 6, 4   | + exp backoff to T_dwell_max=24; hysteresis Δ_hys=0.05 |

## Operating-point rationale (from `../results/`)

* `n_L=n_F=32` sits past the knee of the latency/overhead curve (`p2.json`):
  detection is gap-limited (≤1 window) and pool-insensitive there, so larger
  pools only add overhead. Pools below ~8 enter the estimator-noise-bound regime.
* `tierb_H=0.8` gives an astronomically large ARL₀ at this gap (the competence
  signal sits ~17σ above K), i.e. effectively zero false bounces; the §4 chain
  only binds for short windows / subtle regressions (`p2_latency_pool.pdf`).
* Illustrative auditor storage is **404 bytes** (`p2.json`) at 16 bits/scalar:
  a dense 16×8 random projection plus 16 projected means and standard deviations
  (S_in), an 18-coefficient forward model (S_res), four CUSUM register pairs, and
  the reused dueling counters. This is 0.154% of a 256 KB SRAM. The estimate is a
  floating-point-reference state count; quantization, RTL area/energy, and timing
  remain unmeasured.
