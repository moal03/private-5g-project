#!/usr/bin/env bash
set -u
NS3=/home/mohammad/projects/ns-3.46
WORK=/home/mohammad/projects/ns3-lena-sweep
START=$(date +%s)

progress() {
    local now=$(date +%s)
    printf "[%4ds] %-32s " "$((now - START))" "$1"
}

echo "=== S7: mimo-demo — SISO vs MIMO with dual polarization ==="
s7_dir=$WORK/s7_mimo
for cfg in siso mimo; do
    rowsG=1; colsG=1; rowsU=1; colsU=1; portsG=1; portsU=1; xpol=false; cb="ns3::NrCbTwoPort"
    if [ "$cfg" = "mimo" ]; then
        rowsG=2; colsG=4; rowsU=2; colsU=2
        portsG=2; portsU=2
        xpol=true
        cb="ns3::NrCbTypeOneSp"
    fi
    for seed in 1 2 3; do
        tag="s7_${cfg}_seed${seed}"
        run_dir="$s7_dir/$tag"
        mkdir -p "$run_dir"
        progress "$tag"
        cd "$NS3"
        ./ns3 run "cttc-nr-mimo-demo \
            --numRowsGnb=$rowsG --numColumnsGnb=$colsG \
            --numRowsUe=$rowsU --numColumnsUe=$colsU \
            --numHPortsGnb=$portsG --numVPortsGnb=$portsG \
            --numHPortsUe=$portsU --numVPortsUe=$portsU \
            --xPolGnb=$xpol --xPolUe=$xpol \
            --fullSearchCb=$cb \
            --enableMimoFeedback=true \
            --trafficType=cbr --packetSize=1000 \
            --outputDir=$run_dir/ --simTag=$tag --RngRun=$seed" \
            > "$run_dir/stdout.log" 2>&1
        [ $? -eq 0 ] && echo "OK" || echo "FAIL"
    done
done

echo
echo "=== S8: notching — DL+UL matched ==="
s8_dir=$WORK/s8_notching
for spec in "none:0:0" "light:0:8" "heavy:0:16"; do
    name=${spec%%:*}; rest=${spec#*:}; start=${rest%%:*}; n=${rest##*:}
    for seed in 1 2 3; do
        tag="s8_${name}_seed${seed}"
        run_dir="$s8_dir/$tag"
        mkdir -p "$run_dir"
        progress "$tag"
        cd "$NS3"
        ./ns3 run "cttc-nr-notching \
            --simTime=3 --gNbNum=1 --ueNumPergNb=2 \
            --bandwidth=20000000 --operationMode=TDD \
            --enableOfdma=true \
            --notchedRbStartDl=$start --numOfNotchedRbsDl=$n \
            --notchedRbStartUl=$start --numOfNotchedRbsUl=$n \
            --outputDir=$run_dir/ --simTag=$tag --RngRun=$seed" \
            > "$run_dir/stdout.log" 2>&1
        [ $? -eq 0 ] && echo "OK" || echo "FAIL"
    done
done

echo
echo "=== Complete — $(( $(date +%s) - START ))s ==="
