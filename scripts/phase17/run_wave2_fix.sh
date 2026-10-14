#!/usr/bin/env bash
# Re-run only the three failed studies: S7, S8, S9
set -u
NS3=/home/mohammad/projects/ns-3.46
WORK=/home/mohammad/projects/ns3-lena-sweep
START=$(date +%s)

progress() {
    local now=$(date +%s)
    printf "[%4ds] %-32s " "$((now - START))" "$1"
}

echo "=== S7: mimo-demo — SISO vs MIMO 2x4 ==="
s7_dir=$WORK/s7_mimo
for cfg in siso mimo; do
    rowsG=1; colsG=1; rowsU=1; colsU=1; portsG=1; portsU=1
    if [ "$cfg" = "mimo" ]; then rowsG=2; colsG=4; rowsU=2; colsU=2; portsG=2; portsU=2; fi
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
            --enableMimoFeedback=true \
            --trafficType=cbr --packetSize=1000 \
            --outputDir=$run_dir/ --simTag=$tag --RngRun=$seed" \
            > "$run_dir/stdout.log" 2>&1
        [ $? -eq 0 ] && echo "OK" || echo "FAIL"
    done
done

echo
echo "=== S8: notching — RBG-aligned ==="
s8_dir=$WORK/s8_notching
for spec in "none:0:0" "light:0:4" "heavy:0:8"; do
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
            --outputDir=$run_dir/ --simTag=$tag --RngRun=$seed" \
            > "$run_dir/stdout.log" 2>&1
        [ $? -eq 0 ] && echo "OK" || echo "FAIL"
    done
done

echo
echo "=== S9: 3gpp-xr — direct binary, no outputDir/simTag ==="
s9_dir=$WORK/s9_xr
for spec in "light:1:1:1" "medium:2:2:2" "heavy:4:4:4"; do
    name=${spec%%:*}; rest=${spec#*:}
    ar=$(echo "$rest" | cut -d: -f1)
    vr=$(echo "$rest" | cut -d: -f2)
    cg=$(echo "$rest" | cut -d: -f3)
    for seed in 1 2 3; do
        tag="s9_${name}_seed${seed}"
        run_dir="$s9_dir/$tag"
        mkdir -p "$run_dir"
        progress "$tag"
        cd "$run_dir"
        "$NS3/build/contrib/nr/examples/ns3.46-cttc-nr-traffic-3gpp-xr-default" \
            --arUeNum=$ar --vrUeNum=$vr --cgUeNum=$cg \
            --numerology=1 --frequency=3.5e9 --bandwidth=20e6 \
            --appDuration=3000 --rngRun=$seed \
            > "$run_dir/stdout.log" 2>&1
        [ $? -eq 0 ] && echo "OK" || echo "FAIL"
        cd "$NS3"
    done
done

echo
echo "=== Fix run complete — $(( $(date +%s) - START ))s ==="
