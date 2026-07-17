#!/usr/bin/env bash
# Regenerate every synthetic result, all figures, and the compiled paper. ChampSim
# figures are rebuilt from committed logs; this script does not rerun ChampSim.
# Deterministic: all RNG is explicitly seeded. Runtime machine-dependent: ~5 min on a fast
# laptop, ~20 min in a constrained sandbox.
#
# Reproduction environment: pinned in requirements.txt (numpy 1.26.4, scipy 1.11.4,
# matplotlib 3.8.4, pandas 2.0.3 on CPython 3.11). Floating-point results on other
# numpy builds may differ in the last ~1-2 ulps; scripts/check_paper_numbers.py asserts
# to a tolerance, not byte-identity. If ./.venv exists it is used automatically.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.
PY="${PYTHON:-python3}"
[ -x ./.venv/bin/python ] && PY=./.venv/bin/python
echo "==> using interpreter: $($PY -c 'import sys;print(sys.executable)')"

echo "==> [0/11] harness invariants (single-assignment-per-window; reseed)"
$PY experiments/test_invariants.py

echo "==> [1/11] P0  estimator validation"
$PY experiments/exp_p0_estimator.py
echo "==> [2/11] P1  safety floor (Lemma 1)"
$PY experiments/exp_p1_floor.py
echo "==> [3/11] P2  ROC + chain + overhead"
$PY experiments/exp_p2_overhead_roc.py
echo "==> [4/11] P3  generality + triage"
$PY experiments/exp_p3_generality.py
echo "==> [5/11] P4  mimicry survival + secrecy ablation (headline)"
$PY experiments/exp_p4_mimicry.py
echo "==> [6/11] Theory  ARL + regret-bound validation"
$PY experiments/exp_theory.py
echo "==> [6-floor] Lemma 1 long-attack regression (corrected three-term bound)"
$PY experiments/exp_floor_longattack.py
echo "==> [6-traffic] Lemma 1 traffic-weighting counterexample + high-prob envelope"
$PY experiments/exp_floor_traffic.py

echo "==> [6a] multi-seed confidence intervals"
$PY experiments/exp_ci.py
echo "==> [6b] sensitivity sweep (tau,H)"
$PY experiments/exp_sensitivity.py
echo "==> [6c] adaptive timing adversaries (boiling-frog, PROBING-exploit)"
$PY experiments/exp_adaptive.py
echo "==> [6c2] misspecification robustness (set heterogeneity)"
$PY experiments/exp_robust_env.py
echo "==> [6c3] E3 transfer-function sensitivity sweep"
$PY experiments/exp_e3_sensitivity.py
echo "==> [6c4] R-latency + fixed-deadline TPR (positive form of E3)"
$PY experiments/exp_rlatency.py
echo "==> [6c5] reseed-identifiability (multiplicative vs additive warmup contrast)"
$PY experiments/exp_warmup_predictor.py
echo "==> [6c6] coverage-hole slow-bleed (named limitation)"
$PY experiments/exp_coverage_hole.py
echo "==> [6c7] false re-trust: fully-open windows per episode (Lemma 1 detection term D)"
$PY experiments/exp_retrust.py
echo "==> [6c8] Prop 1 selection bias + sustained-evasion envelope"
$PY experiments/exp_prop1_selection.py
echo "==> [6d] ChampSim real-systems figures (prefetcher suite + replacement boundary)"
$PY experiments/exp_champsim_fig.py
$PY experiments/exp_e1_fig.py   # reads committed results/champsim_e1/ logs
echo "==> [6e] paper diagrams (architecture + gate FSM + exposure + concept)"
$PY experiments/make_diagrams.py
$PY experiments/make_concept.py

echo "==> [7/11] ChampSim C++ auditor self-test"
( cd champsim_plugin && c++ -std=c++17 -O2 bouncer.cc -o bouncer_selftest && ./bouncer_selftest )

echo "==> [8/11] compile paper"
( cd paper && pdflatex -interaction=nonstopmode -halt-on-error bouncer.tex >/dev/null \
  && bibtex bouncer >/dev/null \
  && pdflatex -interaction=nonstopmode bouncer.tex >/dev/null \
  && pdflatex -interaction=nonstopmode bouncer.tex >/dev/null )
echo "    paper/bouncer.pdf ($(cd paper && pdfinfo bouncer.pdf 2>/dev/null | awk '/Pages/{print $2" pages"}'))"

echo "==> [9/11] number audit (INV-R1: paper numerals vs released JSON, to tolerance)"
$PY scripts/check_paper_numbers.py

echo "DONE. Results in results/, figures in figures/, paper at paper/bouncer.pdf"
