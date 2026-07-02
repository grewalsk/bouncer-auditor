#!/usr/bin/env bash
# N1 clean-isolation driver: hold (tau,H,window,partition,FSM) FIXED at the
# champsim operating point; run the 4-config safety-floor study on roms, swapping
# ONLY the reward signal (BOUNCER_REWARD=cachehit|ownpf|ownpf_peraccess).
set -u
CS=$HOME/projects/bouncer-champsim
TR=$CS/traces/654.roms.champsimtrace.xz
OUT=$HOME/projects/bouncer-hpca/hardening/experiments/N1_reward_swap
BIN=$CS/bin/champsim_bouncer
W=1000000; S=9000000
REWARD="${1:-cachehit}"
ATKW="${2:-30}"

# FIXED champsim operating point — identical across every reward signal
export BOUNCER_TAU=0.0 BOUNCER_GAMMA=0.04 BOUNCER_H=0.25
export BOUNCER_REWARD="$REWARD"

gatesummary() { # csv -> "finalState gatedWindows/total meanDelta"
  local csv=$1
  [ -f "$csv" ] || { echo "n/a"; return; }
  awk -F, 'NR>1{n++; d+=$2; if($3=="GATED")g++; last=$3}
           END{printf "%s gated=%d/%d meanDhat=%.4f", last, g+0, n+0, (n? d/n:0)}' "$csv"
}

run() { # name gate attack
  local name=$1 gate=$2 atk=$3
  local log="$OUT/${REWARD}_${name}.log" csv="$OUT/${REWARD}_${name}.gate.csv"
  BOUNCER_GATE=$gate BOUNCER_ATTACK_WINDOW=$atk BOUNCER_LOG="$csv" \
    "$BIN" --warmup-instructions $W --simulation-instructions $S "$TR" > "$log" 2>&1
  local ipc=$(grep -i "cumulative IPC" "$log" | tail -1 | sed -E 's/.*IPC: ([0-9.]+).*/\1/')
  printf "%-18s gate=%s atk=%-3s IPC=%-7s | %s\n" "$name" "$gate" "$atk" "$ipc" "$(gatesummary "$csv")"
}

echo "=== roms 4-config | REWARD=$REWARD | tau=0 gamma=0.04 H=0.25 window=40000 | atk_w=$ATKW ==="
run unguarded_clean  0 -1
run bouncer_clean    1 -1
run unguarded_attack 0 "$ATKW"
run bouncer_attack   1 "$ATKW"
echo "STUDY_DONE REWARD=$REWARD"
