#!/usr/bin/env bash
#
# Wave 3 — TDD pattern sweep
# 5 patterns × 3 seeds = 15 runs at 30 UEs (uesPerGnb=10), 3.5 GHz
#
# This is the most private-5G-specific study:
# the TDD pattern is the operator-controlled parameter
# that defines a private deployment.

set -u
NS3=/home/mohammad/projects/ns-3.46
WORK=/home/mohammad/projects/ns3-lena-sweep
S13=$WORK/s13_tdd
mkdir -p "$S13"

START=$(date +%s)

# Pattern name : pattern string
patterns=(
  "8dl2ul:DL|DL|DL|DL|DL|DL|DL|DL|UL|UL|"
  "6dl4ul:DL|DL|DL|DL|DL|DL|UL|UL|UL|UL|"
  "4dl6ul:DL|DL|DL|DL|UL|UL|UL|UL|UL|UL|"
  "2dl8ul:DL|DL|UL|UL|UL|UL|UL|UL|UL|UL|"
  "lte_style:DL|S|UL|UL|DL|DL|S|UL|UL|DL|"
)

echo "============================================================"
echo "  WAVE 3 — TDD pattern sweep"
echo "  5 patterns × 3 seeds = 15 runs at 30 UEs"
echo "  $(date -Is)"
echo "============================================================"

run_n=0
for pat_spec in "${patterns[@]}"; do
    pat_name="${pat_spec%%:*}"
    pat_val="${pat_spec##*:}"
    for seed in 1 2 3; do
        run_n=$((run_n + 1))
        tag="s13_${pat_name}_seed${seed}"
        run_dir="$S13/$tag"
        mkdir -p "$run_dir"
        elapsed=$(( $(date +%s) - START ))
        printf "[%2d/15  %4ds] %-32s " "$run_n" "$elapsed" "$tag"
        cd "$NS3"
        ./ns3 run "cttc-nr-traffic-ngmn-mixed \
            --numRings=0 --uesPerGnb=10 --simTimeMs=5000 \
            --scenario=UMi --operationMode=TDD \
            --tddPattern=${pat_val} \
            --outputDir=${run_dir}/ --simTag=${tag} --RngRun=${seed}" \
            > "$run_dir/stdout.log" 2>&1
        status=$?
        if [ $status -eq 0 ]; then
            delay=$(grep -oP 'Mean delay:\s*\K[\d.]+' "$run_dir/stdout.log" | tail -1)
            thp=$(grep -oP 'Mean flow throughput:\s*\K[\d.]+' "$run_dir/stdout.log" | tail -1)
            echo "OK  (delay=${delay}ms  thp=${thp}Mbps)"
        else
            echo "FAIL"
        fi
    done
done

echo
echo "============================================================"
echo "  Wave 3 complete — $(( $(date +%s) - START ))s"
echo "============================================================"
