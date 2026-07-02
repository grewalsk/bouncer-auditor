cd $HOME/projects/bouncer-champsim
TR=traces/619.lbm.champsimtrace.xz
W=1000000; S=9000000
run() { # name gate attack
  local out=$( BOUNCER_GATE=$2 BOUNCER_ATTACK_WINDOW=$3 BOUNCER_TAU=0.0 BOUNCER_GAMMA=0.04 BOUNCER_H=0.25 BOUNCER_LOG=/tmp/lbm_$1.csv \
    ./bin/champsim_bouncer --warmup-instructions $W --simulation-instructions $S $TR 2>&1 )
  local ipc=$(echo "$out" | grep -i "CPU 0 cumulative IPC:" | tail -1 | sed -E 's/.*IPC: ([0-9.]+).*/\1/')
  local l1miss=$(echo "$out" | grep -i "cpu0_L1D LOAD" | head -1)
  echo "$1: IPC=$ipc | $l1miss"
}
echo "=== lbm 4-config safety-floor study (attack=window 30) ==="
run unguarded_clean 0 -1
run bouncer_clean   1 -1
run unguarded_atk   0 30
run bouncer_atk     1 30
echo "LBM_STUDY_DONE"
