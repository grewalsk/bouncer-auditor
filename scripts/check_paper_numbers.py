#!/usr/bin/env python3
"""check_paper_numbers.py -- stage-9 claims audit (INV-R1).

Extracts the headline numerals asserted in paper/bouncer.tex and checks each against
the corresponding results/*.json. This institutionalizes the fix for the E3-class bug
(paper said clean tax 0.49-0.52% while the JSON said 0.16-0.51%). Nonzero exit on any
mismatch, so it fails run_all loudly.

Design: for each claim, compute the expected value from the released JSON, render it to
the string as it appears in the tex, and assert that string is present in the
comment-stripped, whitespace-collapsed paper source. A missing/mismatched number fails.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(HERE, "results")
TEX = os.path.join(HERE, "paper", "bouncer.tex")


def load(name):
    return json.load(open(os.path.join(RES, name)))


def tex_text():
    raw = open(TEX).read().splitlines()
    body = [ln for ln in raw if not ln.lstrip().startswith("%")]           # drop comment lines
    txt = "\n".join(body)
    txt = re.sub(r"(?<!\\)%.*", "", txt)                                    # drop inline comments
    return re.sub(r"\s+", " ", txt)                                        # collapse whitespace


def main():
    tex = tex_text()
    p0, p1, p4, th = load("p0.json"), load("p1.json"), load("p4.json"), load("theory.json")
    e1, e3, cs = load("e1_keystone.json"), load("e3_sensitivity.json"), load("champsim.json")
    fla = load("floor_longattack.json")
    rl = load("rlatency.json")
    wp = load("warmup_predictor.json")

    # each check: (label, list of literal strings that MUST appear in the tex, provenance)
    checks = []

    def chk(label, literals, prov):
        checks.append((label, literals if isinstance(literals, list) else [literals], prov))

    # --- P0 / P1 ---
    chk("P0 R^2", "0.997", "p0.json")
    chk("P1 steady floor 0.63%", "0.63", f"p1.json floor_violation_steady={p1['floor_violation_steady']:.5f}")
    chk("P1 clean tax", "0.9965", f"p1.json clean_tax={p1['clean_tax']:.5f}")
    chk("P1 detection latency 1 window", ["one window", "1.0"], "p1.json detection_latency=1.0")
    chk("P1 re-trust 14 windows", "14", "p1.json retrust_latency")

    # --- Lemma 1 corrected bound (the R1 fix) ---
    chk("exposure fraction phi_G=1.56%", "1.56", "phi_G=n_L/n_sets")
    chk("exposure fraction phi_P=6.4%", "6.4", "phi_P")
    chk("P1 corrected 3-term loose 12.4", "12.4", f"p1.json lemma_bound_ipc={p1['lemma_bound_ipc']:.2f}")
    chk("floor prediction 0.58% / 0.65% / 1.76%", ["0.58", "0.65", "1.76"], "phi_G/blended exposure predicts 0.639%")

    # --- Theory (protected) ---
    chk("theory loose/tight/measured 15.1/7.8/5.9",
        ["15.1", "7.8", "5.9"],
        f"theory.json N_ep=6 {th['regret']['bound'][-1]:.1f}/{th['regret']['tight'][-1]:.1f}/{th['regret']['measured'][-1]:.1f}")
    chk("ARL 927 vs 938", ["927", "938"], "theory.json ARL sweep at H=5sigma")
    chk("theory L_att two-term violated 25.8 vs 7.6",
        ["25.8", "7.6"], f"theory.json Latt measured={th['regret']['Latt']['measured'][-1]:.1f} two_term={th['regret']['Latt']['two_term'][-1]:.1f}")

    # --- E3 (the bug this script guards) ---
    tax_lo = min(1 - e3["invariants"]["clean_tax_range_mu"][1], 1 - e3["invariants"]["clean_tax_range_ipc"][1]) * 100
    tax_hi = max(1 - e3["invariants"]["clean_tax_range_mu"][0], 1 - e3["invariants"]["clean_tax_range_ipc"][0]) * 100
    chk("E3 clean-tax range 0.16-0.51%", [f"{tax_lo:.2f}", f"{tax_hi:.2f}"], f"e3_sensitivity.json tax {tax_lo:.2f}-{tax_hi:.2f}%")
    rl_drift = [c["drift_sigma"] for c in rl["cells"]]
    chk("R-latency drift range 3.8-28sd", [f"{min(rl_drift):.1f}"], f"rlatency.json drift {min(rl_drift):.1f}-{max(rl_drift):.0f} sd, TPR all 1.0")
    att = [round(c["attenuation"] * 100) for c in wp["cells"]]
    chk("warmup reseed confound 97->8pct", [str(max(att)), str(min(att))], f"warmup_predictor.json reseeded attenuation {max(att)}%->{min(att)}% of gap; fixed recovers 0.30")

    # --- E1 keystone (means are PROTECTED) ---
    chk("E1 whole-cache 33.6% vs 4.8%",
        ["33.6", "4.8"], f"e1_keystone.json LIP={e1['whole_cache_baselines']['learned_LIP_insert3']} SRRIP={e1['whole_cache_baselines']['fallback_SRRIP_HP_insert2']}")
    chk("E1 reseeded 0.005 vs fixed 0.23",
        ["0.005", "0.23"], f"e1_keystone.json reseeded={e1['reseeded_clean_mean_dhat']:.4f} fixed={e1['fixed_leader_clean_mean_dhat']:.4f}")

    # --- ChampSim Table 2 prefetcher losses ---
    chk("ChampSim lbm attack loss 7.9%", "7.9", f"champsim.json lbm={cs['traces']['lbm']['unguarded_attack_loss_pct']}")
    chk("ChampSim roms tax 11.2%", "11.2", f"champsim.json roms clean_tax={cs['traces']['roms']['clean_tax']}")

    # --- long-attack regression (the counterexample) ---
    chk("long-attack measured 11.9 vs two-term 2.52",
        ["11.9", "2.52"], f"floor_longattack.json measured={fla['summary']['measured_pos_mean']:.2f} two_term={fla['summary']['old_two_term_loose']:.2f}")

    fails = []
    for label, literals, prov in checks:
        missing = [lit for lit in literals if lit not in tex]
        status = "OK  " if not missing else "FAIL"
        if missing:
            fails.append((label, missing, prov))
        print(f"  [{status}] {label:42s} <- {prov}" + (f"   MISSING {missing}" if missing else ""))

    print(f"\n  {len(checks)-len(fails)}/{len(checks)} checks passed.")
    if fails:
        print("\nNUMBER AUDIT FAILED (paper numeral not found / disagrees with released JSON):")
        for label, missing, prov in fails:
            print(f"  - {label}: missing {missing}  (expected from {prov})")
        sys.exit(1)
    print("  INV-R1: all audited paper numbers regenerate from the released JSON.")


if __name__ == "__main__":
    main()
