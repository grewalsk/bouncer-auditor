#!/usr/bin/env bash
# Regenerate the E1 real-ChampSim REPLACEMENT study (results/champsim_e1/*).
# Requires the ChampSim build with the bouncer_repl LLC module (see
# setup_champsim.sh) and a cache-sensitive trace with DISTRIBUTED LLC reuse
# (xalancbmk). Deterministic; ~30 min on an M-series laptop.
#
# What this demonstrates (an honest boundary result, NOT a clean upside trajectory):
#   - the replacement_cache_fill hook makes Delta-hat a real nonzero signal (without
#     it the module sees hits only and Delta-hat is identically 0 -- the 'dhat~0'
#     artifact the prior draft attributed to sampling);
#   - the whole-cache competence gap is real (learned LIP vs fallback SRRIP-HP);
#   - the SECRET per-epoch reseed confounds the per-window dueling signal for the
#     STATEFUL replacement reward; FIXED leaders (BOUNCER_NORESEED=1) resolve it.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$HOME/projects/bouncer-champsim}"
OUT="$HERE/../results/champsim_e1"; mkdir -p "$OUT"
BIN="$ROOT/bin/champsim_repl"
TRACE="${E1_TRACE:-$HOME/projects/pythia-bw-poison/traces/623.xalancbmk_s-202B.champsimtrace.xz}"
W=1000000

echo "[1] whole-cache policy baselines (FORCE mode, 4M sim)"
hr(){ "$BIN" --warmup-instructions $W --simulation-instructions 4000000 "$TRACE" 2>/dev/null \
  | awk '/LLC TOTAL/{print $6/($6+$8)}' | tail -1; }
LIP=$(BOUNCER_FORCE=learned  BOUNCER_LEARN=3   hr)
SR=$(BOUNCER_FORCE=fallback BOUNCER_FALLBACK=2 hr)
MR=$(BOUNCER_FORCE=learned  BOUNCER_LEARN=3 BOUNCER_ATTACK_WINDOW=0 hr)
python3 - "$LIP" "$SR" "$MR" > "$OUT/baselines.json" <<'PY'
import sys, json
print(json.dumps({"trace":"623.xalancbmk_s-202B",
 "note":"whole-cache hit rate, FORCE mode (all sets one policy), 1M warmup + 4M sim",
 "learned_LIP_insert3":round(float(sys.argv[1]),4),
 "fallback_SRRIP_HP_insert2":round(float(sys.argv[2]),4),
 "corrupted_MRU_insert0":round(float(sys.argv[3]),4),
 "finding":"whole-cache competence gap LIP-vs-SRRIP is real and large; the cache_fill API fix makes dhat nonzero (was identically 0 with the hit-only reward)."}, indent=2))
PY

COMMON="BOUNCER_GATE=1 BOUNCER_NL=256 BOUNCER_NF=256 BOUNCER_WINDOW=4000 BOUNCER_LEARN=3 BOUNCER_FALLBACK=2 BOUNCER_TAU=0.05"
echo "[2] reseeded (secret) clean dueling -> dueling_reseeded.csv"
env $COMMON BOUNCER_ATTACK_WINDOW=-1 BOUNCER_LOG="$OUT/dueling_reseeded.csv" \
  "$BIN" --warmup-instructions $W --simulation-instructions 12000000 "$TRACE" >/dev/null 2>&1
echo "[3] fixed-leader (reseed OFF) clean dueling -> dueling_fixed_leader.csv"
env $COMMON BOUNCER_NORESEED=1 BOUNCER_ATTACK_WINDOW=-1 BOUNCER_LOG="$OUT/dueling_fixed_leader.csv" \
  "$BIN" --warmup-instructions $W --simulation-instructions 8000000 "$TRACE" >/dev/null 2>&1

echo "[4] figure + verdict"
( cd "$HERE/.." && PYTHONPATH=. python3 experiments/exp_e1_fig.py )
echo "done -> results/champsim_e1/, figures/e1_replacement.pdf, results/e1_keystone.json"
