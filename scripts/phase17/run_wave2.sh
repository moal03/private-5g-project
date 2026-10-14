#!/usr/bin/env bash
#
# Wave 2 — Extended feature coverage (8 studies, ~66 runs, ~35 min)
# S5:  simple-qos-sched          (2 scenarios × 3 seeds = 6)
# S6:  cc-bwp-demo               (2 configs × 3 seeds = 6)
# S7:  mimo-demo                 (2 configs × 3 seeds = 6)
# S8:  notching                  (3 notching × 3 seeds = 9)
# S9:  3gpp-xr traffic           (3 mixes × 3 seeds = 9)
# S10: numerology sweep          (4 numerology × 3 seeds = 12)
# S11: bandwidth sweep           (4 bandwidth × 3 seeds = 12)
# S12: frequency sweep           (3 frequency × 3 seeds = 9)

set -u
NS3=/home/mohammad/projects/ns-3.46
WORK=/home/mohammad/projects/ns3-lena-sweep

GLOBAL_START=$(date +%s)

progress() {
    local now=$(date +%s)
    local elapsed=$((now - GLOBAL_START))
    printf "[%4ds] %-42s " "$elapsed" "$1"
}

# ============================================================
run_s5() {
    echo
    echo "=== S5: simple-qos-sched — 2 scenarios × 3 seeds ==="
    local s5_dir=$WORK/s5_simple_qos
    mkdir -p "$s5_dir"
    for scen in 0 1; do
        for seed in 1 2 3; do
            local tag="s5_sc${scen}_seed${seed}"
            local run_dir="$s5_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-simple-qos-sched \
                --gNbNum=1 --ueNumPergNb=2 --simTime=3 \
                --priorityTrafficScenario=${scen} \
                --enableOfdma=true \
                --numerology=1 --centralFrequency=3.5e9 --bandwidth=20e6 \
                --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        done
    done
}

# ============================================================
run_s6() {
    echo
    echo "=== S6: cc-bwp-demo — single-CC vs dual-CC ==="
    local s6_dir=$WORK/s6_ca
    mkdir -p "$s6_dir"
    # single CC vs 2 non-contiguous CCs
    for cfg in single dual; do
        local bands=1
        local contig="true"
        [ "$cfg" = "dual" ] && bands=2 && contig="false"
        for seed in 1 2 3; do
            local tag="s6_${cfg}_seed${seed}"
            local run_dir="$s6_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-cc-bwp-demo \
                --simTime=3 --gNbNum=1 --ueNumPergNb=1 \
                --numBands=${bands} --contiguousCc=false \
                --centralFrequencyBand=3.5e9 \
                --centralFrequencyCc0=3.5e9 \
                --centralFrequencyCc1=3.6e9 \
                --numerology=1 \
                --tddPattern=DL|DL|DL|DL|DL|DL|UL|UL|UL|UL| \
                --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        done
    done
}

# ============================================================
run_s7() {
    echo
    echo "=== S7: mimo-demo — SISO vs MIMO 2x4 ==="
    local s7_dir=$WORK/s7_mimo
    mkdir -p "$s7_dir"
    for cfg in siso mimo; do
        local rowsG=1 colsG=1 rowsU=1 colsU=1
        [ "$cfg" = "mimo" ] && rowsG=2 && colsG=4 && rowsU=2 && colsU=2
        for seed in 1 2 3; do
            local tag="s7_${cfg}_seed${seed}"
            local run_dir="$s7_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            local portsG=1 portsU=1
            [ "$cfg" = "mimo" ] && portsG=2 && portsU=2
            ./ns3 run "cttc-nr-mimo-demo \
                --numRowsGnb=${rowsG} --numColumnsGnb=${colsG} \
                --numRowsUe=${rowsU} --numColumnsUe=${colsU} \
                --numHPortsGnb=${portsG} --numVPortsGnb=${portsG} \
                --numHPortsUe=${portsU} --numVPortsUe=${portsU} \
                --enableMimoFeedback=true \
                --trafficType=cbr --packetSize=1000 \
                --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        done
    done
}

# ============================================================
run_s8() {
    echo
    echo "=== S8: notching — 3 ICIC levels × 3 seeds ==="
    local s8_dir=$WORK/s8_notching
    mkdir -p "$s8_dir"
    # levels: none, light, heavy
    for spec in "none:0:0" "light:0:4" "heavy:0:8"; do
        local name="${spec%%:*}"
        local rest="${spec#*:}"
        local start="${rest%%:*}"
        local n="${rest##*:}"
        for seed in 1 2 3; do
            local tag="s8_${name}_seed${seed}"
            local run_dir="$s8_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-notching \
                --simTime=3 --gNbNum=1 --ueNumPergNb=2 \
                --bandwidth=20000000 --operationMode=TDD \
                --enableOfdma=true \
                --notchedRbStartDl=${start} --numOfNotchedRbsDl=${n} \
                --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        done
    done
}

# ============================================================
run_s9() {
    echo
    echo "=== S9: 3gpp-xr — 3 XR mixes × 3 seeds ==="
    local s9_dir=$WORK/s9_xr
    mkdir -p "$s9_dir"
    for spec in "light:1:1:1" "medium:2:2:2" "heavy:4:4:4"; do
        local name="${spec%%:*}"
        local rest="${spec#*:}"
        local ar=$(echo "$rest" | cut -d: -f1)
        local vr=$(echo "$rest" | cut -d: -f2)
        local cg=$(echo "$rest" | cut -d: -f3)
        for seed in 1 2 3; do
            local tag="s9_${name}_seed${seed}"
            local run_dir="$s9_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$run_dir"
            local ns3_bin="$NS3/build/contrib/nr/examples/ns3.46-cttc-nr-traffic-3gpp-xr-default"
            "$ns3_bin" \
                --arUeNum=${ar} --vrUeNum=${vr} --cgUeNum=${cg} \
                --numerology=1 --frequency=3.5e9 --bandwidth=20e6 \
                --appDuration=3000 --rngRun=${seed} \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
            cd "$NS3"
        done
    done
}

# ============================================================
run_s10() {
    echo
    echo "=== S10: numerology sweep (0=15k, 1=30k, 2=60k, 3=120k) ==="
    local s10_dir=$WORK/s10_numerology
    mkdir -p "$s10_dir"
    for num in 0 1 2 3; do
        for seed in 1 2 3; do
            local tag="s10_num${num}_seed${seed}"
            local run_dir="$s10_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-multi-flow-qos-sched \
                --gNbNum=1 --ueNumPergNb=2 --simTime=3 \
                --numerology=${num} --centralFrequency=3.5e9 --bandwidth=20e6 \
                --schedulerType=Qos --enableQoSLcScheduler=true \
                --priorityTrafficScenario=0 \
                --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        done
    done
}

# ============================================================
run_s11() {
    echo
    echo "=== S11: bandwidth sweep (10/20/40/80 MHz) ==="
    local s11_dir=$WORK/s11_bandwidth
    mkdir -p "$s11_dir"
    for bw in "10m:1e7" "20m:2e7" "40m:4e7" "80m:8e7"; do
        local bw_name="${bw%%:*}"
        local bw_val="${bw##*:}"
        for seed in 1 2 3; do
            local tag="s11_${bw_name}_seed${seed}"
            local run_dir="$s11_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-multi-flow-qos-sched \
                --gNbNum=1 --ueNumPergNb=2 --simTime=3 \
                --numerology=1 --centralFrequency=3.5e9 --bandwidth=${bw_val} \
                --schedulerType=Qos --enableQoSLcScheduler=true \
                --priorityTrafficScenario=0 \
                --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        done
    done
}

# ============================================================
run_s12() {
    echo
    echo "=== S12: frequency sweep (3.5 / 4.9 / 28 GHz) ==="
    local s12_dir=$WORK/s12_frequency
    mkdir -p "$s12_dir"
    for freq in "3.5ghz:3.5e9" "4.9ghz:4.9e9" "28ghz:28e9"; do
        local f_name="${freq%%:*}"
        local f_val="${freq##*:}"
        for seed in 1 2 3; do
            local tag="s12_${f_name}_seed${seed}"
            local run_dir="$s12_dir/$tag"
            mkdir -p "$run_dir"
            progress "$tag"
            cd "$NS3"
            ./ns3 run "cttc-nr-multi-flow-qos-sched \
                --gNbNum=1 --ueNumPergNb=2 --simTime=3 \
                --numerology=1 --centralFrequency=${f_val} --bandwidth=20e6 \
                --schedulerType=Qos --enableQoSLcScheduler=true \
                --priorityTrafficScenario=0 \
                --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
                > "$run_dir/stdout.log" 2>&1
            [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        done
    done
}

# ============================================================
echo "============================================================"
echo "  WAVE 2 — 8 studies, ~66 runs"
echo "  $(date -Is)"
echo "============================================================"

run_s5
run_s6
run_s7
run_s8
run_s9
run_s10
run_s11
run_s12

GLOBAL_END=$(date +%s)
echo
echo "============================================================"
echo "  Wave 2 complete"
echo "  $(date -Is)"
echo "  Total wall-clock: $(( GLOBAL_END - GLOBAL_START )) s"
echo "============================================================"
