"""Reseed-identifiability of the policy contrast (the second audit condition).

Set-locality is necessary but NOT sufficient for a secret, reseeded competence audit.
The additional condition is not statelessness per se -- it is that the *policy contrast*
E[r_C - r_F] stays bounded away from zero under the short-run (cold) state distribution
that per-epoch reseeding induces. Reseeding reshuffles the leaders every epoch, so no
slice runs one policy long enough to leave the cold state; the audit is faithful exactly
when the contrast the estimator sees in that cold regime still reflects the true gap.

We separate two stateful rewards that share the SAME statefulness (accuracy ramps with
consecutive windows on a policy) but differ in how the *contrast* depends on state:

  * MULTIPLICATIVE warmup:  r_C(k)=mu_C*(1-e^{-ck}),  r_F(k)=mu_F*(1-e^{-ck})
        contrast = (mu_C-mu_F)*(1-e^{-ck})  -- SCALES with the warmup state.
    Under reseeding every slice stays cold (k~1), so the contrast is attenuated toward
    ~(mu_C-mu_F)*c -> 0 as the warmup timescale 1/c lengthens. NOT reseed-identifiable.
    Fixed leaders warm up and recover the true gap. (This is the cache/replacement case.)

  * ADDITIVE warmup:        r_C(k)=mu_C-b*e^{-ck},    r_F(k)=mu_F-b*e^{-ck}
        contrast = mu_C-mu_F = GAP  -- STATE-INVARIANT, despite each reward being stateful.
    Reseeding erases k but not the contrast, so reseeded Delta-hat ~ GAP survives. A
    stateful reward that IS auditable -- the direct counterexample to "statelessness is
    necessary."

So the precise condition is reseed-identifiability of the contrast (statelessness is one
sufficient special case; a state-invariant contrast is another). Deterministic; emits
results/warmup_predictor.json.
"""
import sys, json
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
import matplotlib.pyplot as plt

MU_C, MU_F = 0.80, 0.50          # warm competence gap = 0.30 (C beats F)
GAP = MU_C - MU_F
B_ADD = 0.20                     # additive cold-start deficit (shared by both policies)


def _run(kind, c, reseed, W=160, n_sets=2048, n_L=32, m=64, seed=0):
    """One trajectory. kind in {'mult','add'}. Returns per-window Delta-hat."""
    rng = np.random.default_rng(seed)
    consec = np.zeros(n_sets)     # consecutive windows the slice has run its current leader policy
    pol = np.full(n_sets, -1)     # last-window policy per slice: -1 none, 0=F, 1=C
    perm = rng.permutation(n_sets)
    lC, lF = perm[:n_L], perm[n_L:2 * n_L]
    dhats = []
    for t in range(W):
        if reseed and t > 0:
            perm = rng.permutation(n_sets)
            lC, lF = perm[:n_L], perm[n_L:2 * n_L]
        # warmup counter: increment if this slice ran the same policy last window, else reset to 1
        for arr, p in [(lC, 1), (lF, 0)]:
            consec[arr] = np.where(pol[arr] == p, consec[arr] + 1, 1)
        newpol = pol.copy(); newpol[lC] = 1; newpol[lF] = 0; pol = newpol
        warm = 1 - np.exp(-c * consec)
        if kind == "mult":                          # contrast scales with warm state
            accC = MU_C * warm[lC]
            accF = MU_F * warm[lF]
        else:                                       # additive: contrast state-invariant (= GAP)
            accC = MU_C - B_ADD * np.exp(-c * consec[lC])
            accF = MU_F - B_ADD * np.exp(-c * consec[lF])
        rL = rng.binomial(m, np.clip(accC, 0, 1)) / m
        rF = rng.binomial(m, np.clip(accF, 0, 1)) / m
        dhats.append(float(rL.mean() - rF.mean()))
    return np.array(dhats)


def cell(kind, c, n_seed=8):
    res, fix = [], []
    for s in range(n_seed):
        dr = _run(kind, c, reseed=True, seed=s)
        df = _run(kind, c, reseed=False, seed=s)
        res.append(dr.mean())                    # reseeded: mean over all windows
        fix.append(df[df.shape[0] // 2:].mean())  # fixed: steady-state (2nd half, after warmup)
    return dict(kind=kind, c=c, warmup_windows=round(1.0 / c, 1),
                reseeded_dhat=float(np.mean(res)), reseeded_std=float(np.std(res)),
                fixed_dhat=float(np.mean(fix)), fixed_std=float(np.std(fix)),
                attenuation=float(np.mean(res) / max(np.mean(fix), 1e-9)))


def main():
    C.setstyle()
    cs = [3.0, 1.0, 0.5, 0.2, 0.1, 0.05]     # warmup timescale 1/c: 0.3 .. 20 windows
    mult = [cell("mult", c) for c in cs]
    add = [cell("add", c) for c in cs]

    print("MULTIPLICATIVE (contrast scales with state -> NOT reseed-identifiable):")
    for r in mult:
        print(f"  c={r['c']:.2f} (warmup ~{r['warmup_windows']} win): reseeded dhat={r['reseeded_dhat']:.3f} "
              f"vs fixed={r['fixed_dhat']:.3f}  (reseeded is {r['attenuation']*100:.0f}% of fixed)")
    print("ADDITIVE (contrast state-invariant = GAP -> reseed-identifiable, though stateful):")
    for r in add:
        print(f"  c={r['c']:.2f} (warmup ~{r['warmup_windows']} win): reseeded dhat={r['reseeded_dhat']:.3f} "
              f"(std {r['reseeded_std']:.4f})  vs fixed={r['fixed_dhat']:.3f}  true gap={GAP:.2f}")

    slow_m, slow_a = mult[-1], add[-1]
    # multiplicative: fixed recovers gap, reseeded attenuates (the cache reseed-confound)
    mult_fixed_recovers = slow_m["fixed_dhat"] >= 0.9 * GAP
    mult_reseeded_attenuates = slow_m["reseeded_dhat"] <= 0.5 * GAP
    # additive: reseeded SURVIVES at ~GAP even at the slowest warmup -> statelessness NOT necessary
    add_reseeded_survives = slow_a["reseeded_dhat"] >= 0.9 * GAP
    print(f"  slow warmup (c={slow_m['c']}): mult fixed recovers? {mult_fixed_recovers}  "
          f"mult reseeded attenuates? {mult_reseeded_attenuates}  |  "
          f"add reseeded survives (stateful yet auditable)? {add_reseeded_survives}")

    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    ww = [r["warmup_windows"] for r in mult]
    ax.plot(ww, [r["fixed_dhat"] for r in mult], "s-", color=C.PALETTE["bouncer"], label="mult., fixed leaders")
    ax.plot(ww, [r["reseeded_dhat"] for r in mult], "o-", color=C.PALETTE["unguarded"],
            label="mult., secret reseed")
    ax.plot(ww, [r["reseeded_dhat"] for r in add], "D--", color=C.PALETTE["oracle"],
            label="add., secret reseed")
    ax.axhline(GAP, color="k", lw=0.8, ls=":", label=f"true gap {GAP:.2f}")
    ax.set_xscale("log")
    ax.set_xlabel("warmup timescale $1/c$ (windows)")
    ax.set_ylabel(r"measured $\hat\Delta$")
    ax.set_title("Reseed-identifiability: contrast that scales with state\ncollapses; state-invariant contrast survives")
    ax.legend(loc="center left", fontsize=6.5)
    C.savefig(fig, "warmup_predictor.pdf")

    C.save_json("warmup_predictor.json", dict(
        note=("Second audit condition = reseed-identifiability of the policy contrast, NOT statelessness. "
              "Multiplicative warmup (contrast scales with the warmup state) is not reseed-identifiable: the "
              "secret per-epoch reseed keeps every slice cold, so reseeded Delta-hat attenuates while fixed "
              "leaders recover the true gap (the ChampSim replacement reseed-confound, isolated here in a "
              "synthetic predictor-like slice model; real PC-indexed predictor rewards remain untested). "
              "Additive warmup (state-invariant contrast = GAP) IS reseed-identifiable: "
              "reseeded Delta-hat survives at ~GAP even though each reward is stateful -- a direct "
              "counterexample to 'statelessness is necessary'. Statelessness is one sufficient special case."),
        mu_C=MU_C, mu_F=MU_F, gap=GAP, b_additive=B_ADD,
        multiplicative_cells=mult, additive_cells=add,
        invariants=dict(mult_fixed_recovers_gap_at_slow_warmup=mult_fixed_recovers,
                        mult_reseeded_attenuates_at_slow_warmup=mult_reseeded_attenuates,
                        additive_reseeded_survives_at_slow_warmup=add_reseeded_survives)))
    assert mult_fixed_recovers, "multiplicative fixed leaders should recover the gap at slow warmup"
    assert mult_reseeded_attenuates, "multiplicative reseeded should attenuate at slow warmup"
    assert add_reseeded_survives, "additive (state-invariant contrast) reseeded should survive -- statelessness is not necessary"


if __name__ == "__main__":
    main()
