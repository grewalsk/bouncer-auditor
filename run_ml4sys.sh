#!/usr/bin/env bash
# Rebuild the focused NeurIPS MLForSys workshop artifact.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/bouncer-ml4sys-mpl}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/bouncer-ml4sys-cache}"
PY="${PYTHON:-python3}"
[ -x ./.venv/bin/python ] && PY=./.venv/bin/python

echo "==> workshop mechanism diagram"
"$PY" experiments/make_concept.py

echo "==> trained set-local replacement controller"
"$PY" experiments/exp_trained_controller.py

echo "==> trained-controller operating characteristics"
"$PY" experiments/exp_trained_characterization.py

echo "==> state-preserving shadow metadata"
"$PY" experiments/exp_warmup_predictor.py

echo "==> traffic-aware and adaptive auditing"
"$PY" experiments/exp_trained_upgrades.py

echo "==> trained-controller claim audit"
"$PY" scripts/check_ml4sys_numbers.py

echo "==> four-page MLForSys paper"
(
  cd paper/mlforsys2026
  pdflatex -interaction=nonstopmode -halt-on-error bouncer_ml4sys.tex >/dev/null
  bibtex bouncer_ml4sys >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error bouncer_ml4sys.tex >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error bouncer_ml4sys.tex >/dev/null
)

echo "==> PDF checks"
PAGES=$(pdfinfo paper/mlforsys2026/bouncer_ml4sys.pdf | awk '/^Pages:/{print $2}')
test "$PAGES" -ge 5
pdftotext -f 1 -l 4 paper/mlforsys2026/bouncer_ml4sys.pdf /tmp/bouncer-ml4sys-main.txt
pdftotext -f 5 -l 5 paper/mlforsys2026/bouncer_ml4sys.pdf /tmp/bouncer-ml4sys-ref.txt
grep -q "Limitations and conclusion" /tmp/bouncer-ml4sys-main.txt
grep -q "References" /tmp/bouncer-ml4sys-ref.txt
grep -q "Submitted to the NeurIPS 2026 Workshop on Machine Learning for Systems" /tmp/bouncer-ml4sys-main.txt
if grep -Eq "undefined citations|There were undefined citations" paper/mlforsys2026/bouncer_ml4sys.log; then
  echo "ERROR: undefined citations remain in the workshop paper" >&2
  exit 1
fi
echo "DONE: paper/mlforsys2026/bouncer_ml4sys.pdf ($PAGES total pages; main text ends on page 4)"
