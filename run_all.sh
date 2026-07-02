#!/usr/bin/env bash
# Regenerate every result, figure, and the compiled paper from scratch.
# Deterministic: all RNG is explicitly seeded. Total runtime ~3-4 min on a laptop.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.

echo "==> [1/8] P0  estimator validation"
python3 experiments/exp_p0_estimator.py
echo "==> [2/8] P1  safety floor (Lemma 1)"
python3 experiments/exp_p1_floor.py
echo "==> [3/8] P2  ROC + §4 chain + overhead"
python3 experiments/exp_p2_overhead_roc.py
echo "==> [4/8] P3  generality + triage"
python3 experiments/exp_p3_generality.py
echo "==> [5/8] P4  mimicry survival + secrecy ablation (headline)"
python3 experiments/exp_p4_mimicry.py
echo "==> [6/8] Theory  ARL + regret-bound validation"
python3 experiments/exp_theory.py
echo "==> [6-floor] Lemma 1 long-attack regression (corrected three-term bound)"
python3 experiments/exp_floor_longattack.py

echo "==> [6a] multi-seed confidence intervals"
python3 experiments/exp_ci.py
echo "==> [6b] sensitivity sweep (tau,H)"
python3 experiments/exp_sensitivity.py
echo "==> [6c] adaptive timing adversaries (boiling-frog, PROBING-exploit)"
python3 experiments/exp_adaptive.py
echo "==> [6c2] misspecification robustness (set heterogeneity)"
python3 experiments/exp_robust_env.py
echo "==> [6c3] E3 transfer-function sensitivity sweep"
python3 experiments/exp_e3_sensitivity.py
echo "==> [6d] ChampSim real-systems figures (prefetcher suite + replacement boundary)"
python3 experiments/exp_champsim_fig.py
python3 experiments/exp_e1_fig.py   # reads committed results/champsim_e1/ logs
echo "==> [6e] paper diagrams (architecture + gate FSM)"
python3 experiments/make_diagrams.py

echo "==> [7/8] ChampSim C++ auditor self-test"
( cd champsim_plugin && c++ -std=c++17 -O2 bouncer.cc -o bouncer_selftest && ./bouncer_selftest )

echo "==> [8/9] compile paper"
( cd paper && pdflatex -interaction=nonstopmode -halt-on-error bouncer.tex >/dev/null \
  && bibtex bouncer >/dev/null \
  && pdflatex -interaction=nonstopmode bouncer.tex >/dev/null \
  && pdflatex -interaction=nonstopmode bouncer.tex >/dev/null )
echo "    paper/bouncer.pdf ($(cd paper && pdfinfo bouncer.pdf 2>/dev/null | awk '/Pages/{print $2" pages"}'))"

echo "==> [9/9] number audit (INV-R1: paper numerals vs released JSON)"
python3 scripts/check_paper_numbers.py

echo "DONE. Results in results/, figures in figures/, paper at paper/bouncer.pdf"
