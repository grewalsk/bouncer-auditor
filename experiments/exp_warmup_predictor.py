"""Warmup-stateful predictor (generalizes the replacement reseed-confound beyond caches).

A predictor-like controller whose per-slice accuracy RAMPS the longer one policy runs
consecutively on a slice (warmup):  acc = mu * (1 - exp(-c * consecutive_windows_on_policy)).
This is the same statefulness that a real cache's replacement reward has (a set must run one
policy consistently to accumulate its policy-specific state). We measure the secret-reseed
confound directly:

  * RESEEDED (leaders reshuffled every epoch, the mechanism that buys mimicry resistance):
    no slice runs one policy long enough to warm up, so both pools stay cold and Delta-hat
    ATTENUATES toward noise as the warmup timescale (1/c) lengthens.
  * FIXED leaders (reseed off): leaders run their policy consistently, warm up, and the same
    estimator RECOVERS the full competence gap.

So set-locality is necessary but not sufficient: a secret reseeded audit also needs a
(near-)stateless reward. This measured statement now covers PC-indexed predictors, not only
the ChampSim cache (single trace). Deterministic; emits results/warmup_predictor.json.
"""
import sys, json
import numpy as np
sys.path.insert(0, 'experiments')
import common as C
import matplotlib.pyplot as plt

MU_C, MU_F = 0.80, 0.50          # warm competence gap = 0.30 (C beats F)
GAP = MU_C - MU_F


def simulate(c, reseed, W=160, n_sets=2048, n_L=32, m=64, seed=0):
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
        # bounded reward: Bernoulli(mu*(1-exp(-c*consec))) averaged over m decisions/slice
        accC = MU_C * (1 - np.exp(-c * consec[lC]))
        accF = MU_F * (1 - np.exp(-c * consec[lF]))
        rL = rng.binomial(m, np.clip(accC, 0, 1)) / m
        rF = rng.binomial(m, np.clip(accF, 0, 1)) / m
        dhats.append(float(rL.mean() - rF.mean()))
    return np.array(dhats)


def cell(c, n_seed=8):
    res, fix = [], []
    for s in range(n_seed):
        dr = simulate(c, reseed=True, seed=s)
        df = simulate(c, reseed=False, seed=s)
        res.append(dr.mean())                    # reseeded: mean over all windows
        fix.append(df[df.shape[0] // 2:].mean())  # fixed: steady-state (2nd half, after warmup)
    return dict(c=c, warmup_windows=round(1.0 / c, 1),
                reseeded_dhat=float(np.mean(res)), reseeded_std=float(np.std(res)),
                fixed_dhat=float(np.mean(fix)), fixed_std=float(np.std(fix)),
                attenuation=float(np.mean(res) / max(np.mean(fix), 1e-9)))


def main():
    C.setstyle()
    cs = [3.0, 1.0, 0.5, 0.2, 0.1, 0.05]     # warmup timescale 1/c: 0.3 .. 20 windows
    rows = [cell(c) for c in cs]
    for r in rows:
        print(f"  c={r['c']:.2f} (warmup ~{r['warmup_windows']} win): reseeded dhat={r['reseeded_dhat']:.3f} "
              f"vs fixed={r['fixed_dhat']:.3f}  (attenuation {r['attenuation']*100:.0f}% of the gap)")

    # the confound: as warmup lengthens, reseeded collapses while fixed recovers the 0.30 gap
    slow = rows[-1]
    fixed_recovers = slow["fixed_dhat"] >= 0.9 * GAP
    reseeded_attenuates = slow["reseeded_dhat"] <= 0.5 * GAP
    print(f"  slowest warmup (c={slow['c']}): fixed recovers gap? {fixed_recovers}  "
          f"reseeded attenuates? {reseeded_attenuates}")

    fig, ax = plt.subplots(figsize=(4.2, 2.9))
    ww = [r["warmup_windows"] for r in rows]
    ax.plot(ww, [r["fixed_dhat"] for r in rows], "s-", color=C.PALETTE["bouncer"], label="fixed leaders")
    ax.plot(ww, [r["reseeded_dhat"] for r in rows], "o-", color=C.PALETTE["unguarded"], label="secret reseed")
    ax.axhline(GAP, color="k", lw=0.8, ls=":", label=f"true gap {GAP:.2f}")
    ax.set_xscale("log")
    ax.set_xlabel("warmup timescale $1/c$ (windows)")
    ax.set_ylabel(r"measured $\hat\Delta$")
    ax.set_title("Stateful predictor: reseed confounds $\\hat\\Delta$; fixed leaders recover")
    ax.legend(loc="center left", fontsize=7)
    C.savefig(fig, "warmup_predictor.pdf")

    C.save_json("warmup_predictor.json", dict(
        note=("Stateful predictor-like reward (accuracy ramps with consecutive windows on a policy). "
              "As the warmup timescale 1/c lengthens, the secret per-epoch reseed keeps both pools cold so "
              "reseeded Delta-hat attenuates toward noise, while FIXED leaders warm up and recover the true "
              "gap. Generalizes the ChampSim replacement reseed-confound (single trace) to PC-indexed "
              "predictors: set-locality is necessary but not sufficient; a near-stateless reward is also required."),
        mu_C=MU_C, mu_F=MU_F, gap=GAP, cells=rows,
        invariants=dict(fixed_recovers_gap_at_slow_warmup=fixed_recovers,
                        reseeded_attenuates_at_slow_warmup=reseeded_attenuates)))
    assert fixed_recovers, "fixed leaders should recover the gap at slow warmup"
    assert reseeded_attenuates, "reseeded should attenuate at slow warmup"


if __name__ == "__main__":
    main()
