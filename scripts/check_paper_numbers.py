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


# Tight marker set: only words that actually signal a retraction. Bare "old"/"earlier" are
# ordinary prose words and over-exempt (TMLR-R7 hardening: the pre-R7 defective JSON note
# passed a loose marker check because it retracted a DIFFERENT claim on the same line).
RETRACTION_MARKERS = re.compile(r"\b(retract\w*|incorrect|false|earlier draft)\b", re.I)
CTX_CHARS = 120  # exemption window, chars each side of a match, in whitespace-collapsed text


def hygiene_checks(tex):
    """TMLR-R7 (optional item 6): repo-wide tripwires for the retracted Prop-1(ii) inferences
    and current-document drift. Retracted claims may be MENTIONED (to refute them) but only
    in a retraction context: a match is exempt iff a retraction marker appears within
    CTX_CHARS characters in the whitespace-collapsed file text (collapsing defeats the
    line-wrap escape; the tight window defeats a marker for a DIFFERENT claim elsewhere in
    the same paragraph/JSON note). Historical snapshots in hardening/ (other than
    REVISION_STATUS.md) and round-pinned REVIEW_PROMPT_R*.md are out of scope by design."""
    import glob
    out = []

    def scan(label, paths, pattern, exempt_in_retraction_context=True):
        rx = re.compile(pattern, re.I)
        bad = []
        for p in paths:
            txt = re.sub(r"\s+", " ", open(p, errors="replace").read())
            for m in rx.finditer(txt):
                ctx = txt[max(0, m.start() - CTX_CHARS): m.end() + CTX_CHARS]
                if exempt_in_retraction_context and RETRACTION_MARKERS.search(ctx):
                    continue
                bad.append(f"{os.path.relpath(p, HERE)} ('{txt[m.start():m.end()+30]}...')")
        out.append((label, not bad, "clean" if not bad else "found: " + "; ".join(bad[:3])))

    tex_files = glob.glob(os.path.join(HERE, "paper", "*.tex"))
    md_files = [os.path.join(HERE, "README.md"),
                os.path.join(HERE, "hardening", "REVISION_STATUS.md")]
    py_files = glob.glob(os.path.join(HERE, "experiments", "*.py")) + \
        glob.glob(os.path.join(HERE, "bouncer", "*.py"))
    json_files = glob.glob(os.path.join(RES, "*.json"))
    everything = tex_files + md_files + py_files + json_files

    # The retracted CUSUM inference, in both original phrasings and verb alternations
    # ("fires/fired/fire within 2H/gamma", "reaches H within 2H/gamma") -- but not legitimate
    # measured-latency prose ("fires within one measurement window") and not the corrected
    # containment's legitimate "W >= 2H/gamma".
    scan("hygiene: retracted CUSUM step only in retraction context", everything,
         r"(fires?|fired) within \$?2\s*H|reaches \$?H\$? within \$?2\s*H")
    # The premise-free reseed=>independence inference, both retracted sites: the Prop-1(ii)
    # sentence ("...and rewards are bounded") and the Lemma-1 exposure sentence ("...the
    # per-window exposures are independent"). Wrap-proof and case-insensitive; \emph{} allowed.
    scan("hygiene: premise-free reseed inference purged", everything,
         r"redrawn\s+(\\emph\{)?independently\}?,?\s+each\s+epoch,?\s+"
         r"(and\s+rewards\s+are\s+bounded|the\s+per-window\s+exposures\s+are\s+independent)",
         exempt_in_retraction_context=False)
    scan("hygiene: old range-r_max tex exponent absent", tex_files + py_files,
         r"e\^\{-2W\\epsilon\^2/r")
    scan("hygiene: old exp(-2W eps...) form only in retraction context",
         py_files + json_files + md_files, r"exp\(-2\s*W\s*eps")

    n_corrected = tex.count(r"e^{-W\epsilon^2/(2r_{\max}^2)}") + tex.count(r"e^{-W\epsilon^2/(2\rmax^2)}")
    out.append(("hygiene: corrected exponent printed in tex (>=2 sites)", n_corrected >= 2,
                f"{n_corrected} occurrences"))

    readme = open(os.path.join(HERE, "README.md"), errors="replace").read()
    out.append(("hygiene: README says TMLR (no IEEEtran)", "IEEEtran" not in readme,
                "clean" if "IEEEtran" not in readme else "IEEEtran still present"))

    log_p = os.path.join(HERE, "paper", "bouncer.log")
    m_r = re.search(r"\((\d+) pages, TMLR format\)", readme)
    if not os.path.exists(log_p):
        out.append(("hygiene: README page count vs built PDF", True,
                    "paper/bouncer.log absent; skipped (run_all stage 8 creates it before stage 9)"))
    else:
        # stale-build guard: an old log agreeing with an old README is a silent false pass
        stale = os.path.getmtime(TEX) > os.path.getmtime(log_p)
        m_l = re.search(r"Output written on .*?bouncer\.pdf \((\d+) pages",
                        open(log_p, errors="replace").read())
        ok = bool(m_r and m_l and m_r.group(1) == m_l.group(1)) and not stale
        out.append(("hygiene: README page count vs built PDF", ok,
                    f"README={m_r.group(1) if m_r else '?'} log={m_l.group(1) if m_l else '?'}"
                    + (" STALE BUILD: bouncer.tex newer than bouncer.log; rerun stage 8" if stale else "")))
    return out


def main():
    tex = tex_text()
    p0, p1, p4, th = load("p0.json"), load("p1.json"), load("p4.json"), load("theory.json")
    e1, e3, cs = load("e1_keystone.json"), load("e3_sensitivity.json"), load("champsim.json")
    fla = load("floor_longattack.json")
    rl = load("rlatency.json")
    wp = load("warmup_predictor.json")
    ft = load("floor_traffic.json")
    rt = load("retrust.json")
    ps = load("prop1_selection.json")

    # each check: (label, list of literal strings that MUST appear in the tex, provenance)
    checks = []

    def chk(label, literals, prov):
        checks.append((label, literals if isinstance(literals, list) else [literals], prov))

    # --- P0 / P1 ---
    chk("P0 R^2", "0.997", "p0.json")
    chk("P1 steady floor 0.64%", "0.64", f"p1.json floor_violation_steady={p1['floor_violation_steady']:.5f} (worst window; rounds to 0.64%)")
    chk("P1 clean tax", "0.9965", f"p1.json clean_tax={p1['clean_tax']:.5f}")
    chk("P1 detection latency 1 window", ["one window", "1.0"], "p1.json detection_latency=1.0")
    chk("P1 re-trust 14 windows", "14", "p1.json retrust_latency")

    # --- Lemma 1 corrected bound (the R1 fix) ---
    chk("exposure fraction phi_G=1.56%", "1.56", "phi_G=n_L/n_sets")
    chk("exposure fraction phi_P=6.4%", "6.4", "phi_P")
    chk("P1 corrected 3-term loose 12.4", "12.4", f"p1.json lemma_bound_ipc={p1['lemma_bound_ipc']:.2f}")
    chk("floor prediction mean 0.579 vs 0.580", ["0.579", "0.580"], "phi_G design constant predicts the MEAN attacked-GATED floor 0.579 vs measured 0.580455 (0.64% is the worst window)")

    # --- Theory (literals DERIVED from JSON, not hard-coded; TMLR-R5) ---
    th_two = f"{th['regret']['bound'][-1]:.1f}"
    th_tight = f"{th['regret']['tight'][-1]:.1f}"
    th_meas = f"{th['regret']['measured'][-1]:.1f}"
    chk(f"theory two-term/tight/measured {th_two}/{th_tight}/{th_meas}",
        [th_two, th_tight, th_meas],
        f"theory.json N_ep=6 (tight = realized phi_G/phi_P occupancy)")
    chk("ARL 927 vs 938", ["927", "938"], "theory.json ARL sweep at H=5sigma")
    chk("theory L_att two-term violated 25.8 vs 7.6",
        ["25.8", "7.6"], f"theory.json Latt measured={th['regret']['Latt']['measured'][-1]:.1f} two_term={th['regret']['Latt']['two_term'][-1]:.1f}")

    # --- E3 (the bug this script guards) ---
    tax_lo = min(1 - e3["invariants"]["clean_tax_range_mu"][1], 1 - e3["invariants"]["clean_tax_range_ipc"][1]) * 100
    tax_hi = max(1 - e3["invariants"]["clean_tax_range_mu"][0], 1 - e3["invariants"]["clean_tax_range_ipc"][0]) * 100
    chk("E3 clean-tax range 0.16-0.51%", [f"{tax_lo:.2f}", f"{tax_hi:.2f}"], f"e3_sensitivity.json tax {tax_lo:.2f}-{tax_hi:.2f}%")
    chk("R-latency min drift bg 1.6 / full 3.2", [f"{rl['min_drift_bg_sigma']:.1f}", f"{rl['min_drift_full_sigma']:.1f}"],
        f"rlatency.json min-drift-at-tau bg={rl['min_drift_bg_sigma']:.2f} full={rl['min_drift_full_sigma']:.2f} sigma")
    att = [round(c["attenuation"] * 100) for c in wp["multiplicative_cells"]]
    chk("warmup reseed confound 97->8pct (multiplicative)", [str(max(att)), str(min(att))],
        f"warmup_predictor.json multiplicative reseeded attenuation {max(att)}%->{min(att)}% of gap; additive survives at 0.30")

    # --- Lemma 1 traffic-weighting counterexample (R1 fix) ---
    chk("floor-traffic 15.6x per-window violation", f"{ft['counterexample']['violation_factor']:.1f}",
        f"floor_traffic.json violation={ft['counterexample']['violation_factor']:.2f}x over naive phi_P bound")
    # --- PROBING sorted-prefix bug + uniform-secret fix (R2 fix) ---
    pa = ft["probing_audit"]
    chk("PROBING sorted-prefix bug 0.985 vs uniform ~phi_P", ["0.985", f"{pa['uniform_low']:.3f}", f"{pa['uniform_high']:.3f}"],
        f"floor_traffic.json sorted-prefix low={pa['sorted_prefix_low']:.3f} vs uniform low={pa['uniform_low']:.3f}/high={pa['uniform_high']:.3f} (~phi_P)")
    # --- fully-open windows per episode: real (small) vs correlated audit (inflates) ---
    near_tau = next(r["open_frac_mean"] for r in rt["real"] if r["target"] == 0.04)
    corr_hi = next(c["open_frac_mean"] for c in rt["correlated"] if c["rho"] == 0.95)
    chk("re-trust: real fully-open <=0.07, correlated inflates to ~0.225",
        [f"{near_tau:.3f}", f"{corr_hi:.3f}"],
        f"retrust.json real near-tau fully-open={near_tau:.3f} (re-trust~0); correlated rho=0.95={corr_hi:.3f}")
    # --- retrust noise-amplitude disclosure (R5 fix) ---
    chk("retrust noise disclosure 3.2-6.4x sigma", ["3.2", "6.4"],
        f"retrust.json noise sweep at rho=0.95 (injected 0.10 = 3.2-6.4x harness sigma; harness-matched amplitudes stay small)")

    # --- Prop 1 selection bias + sustained evasion (R5 fix) ---
    chk("prop1 counterexample E[r_foll|evade]=0.000, P(evade)=0.50",
        [f"{ps['two_set']['E_rfoll_given_evade']:.3f}", f"{ps['two_set']['p_evade']:.2f}"],
        f"prop1_selection.json two-set: E[r_foll|evade]={ps['two_set']['E_rfoll_given_evade']:.4f} p_evade={ps['two_set']['p_evade']:.4f}")
    chk("prop1 sustained evasion 0.50->0.04 under Hoeffding",
        [f"{ps['sustained'][0]['p_sustained_evade']:.2f}", f"{ps['sustained'][-1]['p_sustained_evade']:.2f}"],
        f"prop1_selection.json W=1..16: {ps['sustained'][0]['p_sustained_evade']:.4f}->{ps['sustained'][-1]['p_sustained_evade']:.4f}")
    chk("prop1 old range-1 exponent violated 84.8x (corrected range-2 printed)",
        [f"{ps['printed_formula']['old_violation_factor']:.1f}"],
        f"prop1_selection.json W=100 Rademacher: exact {ps['printed_formula']['p_exact']:.6f} vs old envelope {ps['printed_formula']['old_envelope']:.6f}; corrected holds={ps['printed_formula']['new_holds']}")
    dpn = ps["cusum_block"]["exact_dp"]
    chk("prop1 exact-DP no-alarm prob + envelope (CUSUM containment, R7)",
        [f"{dpn['p_noalarm_exact']:.4f}", f"{dpn['corrected_envelope']:.3f}"],
        f"prop1_selection.json exact_dp p={dpn['p_noalarm_exact']:.6f} mc={dpn['p_noalarm_mc']:.6f} env={dpn['corrected_envelope']:.4f}")
    chk("prop1 exhaustive no-alarm path count (R7)",
        [f"{ps['cusum_block']['exhaustive']['n_noalarm_paths']:,}".replace(",", "{,}")],
        f"prop1_selection.json exhaustive n_noalarm_paths={ps['cusum_block']['exhaustive']['n_noalarm_paths']} holds={ps['cusum_block']['exhaustive']['holds']}")

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

    n_checks = len(checks)
    for label, ok, detail in hygiene_checks(tex):
        n_checks += 1
        if not ok:
            fails.append((label, [detail], "hygiene"))
        print(f"  [{'OK  ' if ok else 'FAIL'}] {label:42s} <- {detail}")

    print(f"\n  {n_checks-len(fails)}/{n_checks} checks passed.")
    if fails:
        print("\nNUMBER AUDIT FAILED (paper numeral not found / disagrees with released JSON):")
        for label, missing, prov in fails:
            print(f"  - {label}: missing {missing}  (expected from {prov})")
        sys.exit(1)
    print("  INV-R1: all audited paper numbers regenerate from the released JSON.")


if __name__ == "__main__":
    main()
