#!/usr/bin/env bash
#
# Master sweep: 4 studies, 64 runs (~60 minutes)
# S1: NGMN scalability (25 runs)
# S2: Multi-flow QoS scheduler (12 runs)
# S3: Realistic beamforming (18 runs)
# S4: Fronthaul XR (9 runs)

set -u
NS3=/home/mohammad/projects/ns-3.46
WORK=/home/mohammad/projects/ns3-lena-sweep
RESULTS=$WORK/results
mkdir -p "$RESULTS"

GLOBAL_START=$(date +%s)
TOTAL_RUNS=64
RUN_NUM=0

# ---------- helper ----------
progress() {
    RUN_NUM=$((RUN_NUM + 1))
    local now=$(date +%s)
    local elapsed=$((now - GLOBAL_START))
    printf "[%2d/%d  %4ds] %-42s " "$RUN_NUM" "$TOTAL_RUNS" "$elapsed" "$1"
}

# ============================================================
# S1 — NGMN scalability
# ============================================================
run_s1() {
    echo
    echo "============================================================"
    echo "  S1: NGMN scalability — NGMN mixed traffic, 5 UE counts × 5 seeds"
    echo "============================================================"
    local s1_dir=$WORK/s1_ngmn
    mkdir -p "$s1_dir"
    for ues_per_gnb in 10 20 30 40 50; do
        local ue_count=$((ues_per_gnb * 3))
        for seed in 1 2 3 4 5; do
            local tag="s1_${ue_count}ue_seed${seed}"
            local run_dir="$s1_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-traffic-ngmn-mixed \
                --numRings=0 \
                --uesPerGnb=${ues_per_gnb} \
                --simTimeMs=5000 \
                --outputDir=${run_dir}/ \
                --simTag=${tag} \
                --RngRun=${seed}" > "$run_dir/stdout.log" 2>&1
            if [ $? -eq 0 ]; then
                local d=$(grep -oP 'Mean delay:\s*\K[\d.]+' "$run_dir/stdout.log" | tail -1)
                local t=$(grep -oP 'Mean flow throughput:\s*\K[\d.]+' "$run_dir/stdout.log" | tail -1)
                echo "OK  (delay=${d}ms  thp=${t}Mbps)"
            else
                echo "FAIL"
            fi
        done
    done
}

# ============================================================
# S2 — Multi-flow QoS scheduler comparison
# ============================================================
run_s2() {
    echo
    echo "============================================================"
    echo "  S2: Multi-flow QoS — PF vs QoS scheduler, 2 scenarios × 3 seeds"
    echo "============================================================"
    local s2_dir=$WORK/s2_qos
    mkdir -p "$s2_dir"
    for sched in PF Qos; do
        for scenario in 0 1; do
            for seed in 1 2 3; do
                local tag="s2_${sched}_sc${scenario}_seed${seed}"
                local run_dir="$s2_dir/$tag"
                mkdir -p "$run_dir"
                progress "$tag"
                cd "$NS3"
                local lc_flag="false"
                [ "$sched" = "Qos" ] && lc_flag="true"
                ./ns3 run "cttc-nr-multi-flow-qos-sched \
                    --gNbNum=1 \
                    --ueNumPergNb=2 \
                    --simTime=3 \
                    --schedulerType=${sched} \
                    --enableQoSLcScheduler=${lc_flag} \
                    --priorityTrafficScenario=${scenario} \
                    --enableQosTrafficTraces=true \
                    --outputDir=${run_dir}/ \
                    --simTag=${tag} \
                    --RngRun=${seed}" > "$run_dir/stdout.log" 2>&1
                if [ $? -eq 0 ]; then
                    local d=$(grep -oP 'Mean flow delay:\s*\K[\d.]+' "$run_dir/stdout.log" | tail -1)
                    echo "OK  (delay=${d}ms)"
                else
                    echo "FAIL"
                fi
            done
        done
    done
}

# ============================================================
# S3 — Realistic beamforming (SQLite output)
# ============================================================
run_s3() {
    echo
    echo "============================================================"
    echo "  S3: Realistic beamforming — 2 algorithms × 3 scenarios × 3 seeds"
    echo "============================================================"
    local s3_dir=$WORK/s3_beamforming
    mkdir -p "$s3_dir"
    for alg in Ideal Real; do
        for scen in UMa UMi InH-OfficeOpen; do
            for seed in 1 2 3; do
                local tag="s3_${alg}_${scen}_seed${seed}"
                local run_dir="$s3_dir/$tag"
                mkdir -p "$run_dir"
                progress "$tag"
                cd "$NS3"
                ./ns3 run "cttc-realistic-beamforming \
                    --algType=${alg} \
                    --scenario=${scen} \
                    --rngRun=${seed} \
                    --simTag=${tag} \
                    --resultsDir=${run_dir}/ \
                    --dbName=${tag}.db" > "$run_dir/stdout.log" 2>&1
                if [ $? -eq 0 ]; then
                    echo "OK"
                else
                    echo "FAIL"
                fi
            done
        done
    done
}

# ============================================================
# S4 — Fronthaul XR
# ============================================================
run_s4() {
    echo
    echo "============================================================"
    echo "  S4: Fronthaul XR — 3 UE mixes × 3 seeds"
    echo "============================================================"
    local s4_dir=$WORK/s4_fronthaul
    mkdir -p "$s4_dir"
    # 3 mixes: light, medium, heavy
    local mixes=("1 1 1 1" "3 3 3 3" "5 5 5 5")
    for idx in 0 1 2; do
        local mix="${mixes[$idx]}"
        local ar=$(echo $mix | awk '{print $1}')
        local vr=$(echo $mix | awk '{print $2}')
        local cg=$(echo $mix | awk '{print $3}')
        local vo=$(echo $mix | awk '{print $4}')
        local mix_name=$( [ $idx -eq 0 ] && echo "light" || ([ $idx -eq 1 ] && echo "medium" || echo "heavy") )
        for seed in 1 2 3; do
            local tag="s4_${mix_name}_seed${seed}"
            local run_dir="$s4_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-fh-xr \
                --deployment=SIMPLE \
                --arUeNum=${ar} --vrUeNum=${vr} --cgUeNum=${cg} --voiceUeNum=${vo} \
                --simTag=${tag} \
                --outputDir=${run_dir}/ \
                --RngRun=${seed}" > "$run_dir/stdout.log" 2>&1
            if [ $? -eq 0 ]; then
                local d=$(grep -oP 'Mean flow delay:\s*\K[\d.]+' "$run_dir/stdout.log" | tail -1)
                echo "OK  (delay=${d}ms)"
            else
                echo "FAIL"
            fi
        done
    done
}

# ============================================================
# Main
# ============================================================
echo "============================================================"
echo "  MASTER SWEEP — 4 studies, 64 runs"
echo "  $(date -Is)"
echo "============================================================"

run_s1
run_s2
run_s3
run_s4

GLOBAL_END=$(date +%s)
echo
echo "============================================================"
echo "  Master sweep complete"
echo "  $(date -Is)"
echo "  Total wall-clock: $(( GLOBAL_END - GLOBAL_START )) s"
echo "============================================================"
