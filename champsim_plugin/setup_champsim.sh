#!/usr/bin/env bash
# Reproduce the real ChampSim integration: clone + build ChampSim, drop in the
# Bouncer L1D prefetcher module, fetch a public SPEC CPU2017 trace, and run the
# 4-config safety-floor study. Verified on macOS (Apple clang 17) + Linux.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$HOME/projects/bouncer-champsim}"

echo "[1] clone + bootstrap ChampSim at $ROOT"
[ -d "$ROOT" ] || git clone --depth 1 https://github.com/ChampSim/ChampSim.git "$ROOT"
cd "$ROOT"
git submodule update --init --depth 1
./vcpkg/bootstrap-vcpkg.sh -disableMetrics
./vcpkg/vcpkg install --x-manifest-root=.

echo "[2] install the Bouncer prefetcher module"
mkdir -p prefetcher/bouncer_pref
cp "$HERE/bouncer_pref/"* prefetcher/bouncer_pref/
python3 - <<PY
import json
c=json.load(open('champsim_config.json'))
c['executable_name']='champsim_bouncer'
c['L1D']['prefetcher']='bouncer_pref'   # L1D sees every load -> dense reward
json.dump(c,open('champsim_bouncer.json','w'),indent=2)
PY

echo "[3] build"
./config.sh champsim_bouncer.json
make -j4

echo "[4] fetch a public SPEC trace (streaming, memory-bound)"
mkdir -p traces
[ -f traces/619.lbm.champsimtrace.xz ] || \
  curl -L -o traces/619.lbm.champsimtrace.xz \
  https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu/619.lbm_s-4268B.champsimtrace.xz

echo "[5] 4-config safety-floor study (corruption attack at window 30)"
TR=traces/619.lbm.champsimtrace.xz; W=1000000; S=9000000
run(){ BOUNCER_GATE=$2 BOUNCER_ATTACK_WINDOW=$3 BOUNCER_TAU=0.0 BOUNCER_GAMMA=0.04 BOUNCER_H=0.25 \
  ./bin/champsim_bouncer --warmup-instructions $W --simulation-instructions $S $TR 2>&1 \
  | grep -i "CPU 0 cumulative IPC:" | sed "s/^/$1: /"; }
run unguarded_clean 0 -1
run bouncer_clean   1 -1
run unguarded_attack 0 30
run bouncer_attack   1 30
echo "done."
