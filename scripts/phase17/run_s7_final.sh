#!/usr/bin/env bash
set -u
NS3=/home/mohammad/projects/ns-3.46
WORK=/home/mohammad/projects/ns3-lena-sweep
START=$(date +%s)

echo "=== S7 MIMO: smaller antenna arrays to keep rank <= 2 ==="
s7_dir=$WORK/s7_mimo

# SISO: 1x1 single-pol
for seed in 1 2 3; do
    tag="s7_siso_seed${seed}"
    run_dir="$s7_dir/$tag"
    mkdir -p "$run_dir"
    printf "[%4ds] %-28s " "$(( $(date +%s) - START ))" "$tag"
    cd "$NS3"
    ./ns3 run "cttc-nr-mimo-demo \
        --numRowsGnb=1 --numColumnsGnb=1 \
        --numRowsUe=1 --numColumnsUe=1 \
        --numHPortsGnb=1 --numVPortsGnb=1 \
        --numHPortsUe=1 --numVPortsUe=1 \
        --xPolGnb=false --xPolUe=false \
        --fullSearchCb=ns3::NrCbTwoPort \
        --enableMimoFeedback=true \
        --trafficType=cbr --packetSize=1000 \
        --outputDir=$run_dir/ --simTag=$tag --RngRun=$seed" \
        > "$run_dir/stdout.log" 2>&1
    [ $? -eq 0 ] && echo "OK" || echo "FAIL"
done

# MIMO: 1x4 gNB dual-pol (8 ports) + 1x2 UE single-pol (2 ports) => rank <= 2
for seed in 1 2 3; do
    tag="s7_mimo_seed${seed}"
    run_dir="$s7_dir/$tag"
    mkdir -p "$run_dir"
    printf "[%4ds] %-28s " "$(( $(date +%s) - START ))" "$tag"
    cd "$NS3"
    ./ns3 run "cttc-nr-mimo-demo \
        --numRowsGnb=1 --numColumnsGnb=4 \
        --numRowsUe=1 --numColumnsUe=2 \
        --numHPortsGnb=4 --numVPortsGnb=1 \
        --numHPortsUe=2 --numVPortsUe=1 \
        --xPolGnb=true --xPolUe=false \
        --fullSearchCb=ns3::NrCbTypeOneSp \
        --enableMimoFeedback=true \
        --trafficType=cbr --packetSize=1000 \
        --outputDir=$run_dir/ --simTag=$tag --RngRun=$seed" \
        > "$run_dir/stdout.log" 2>&1
    [ $? -eq 0 ] && echo "OK" || echo "FAIL"
done

echo
echo "=== Complete — $(( $(date +%s) - START ))s ==="
