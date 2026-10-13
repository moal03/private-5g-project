#!/usr/bin/env bash
set -u

RESULTS=~/projects/private-5g/results/phase11
SCRIPTS=~/projects/private-5g/scripts/phase11
TAG=F05_$(date +%H%M%S)
EDGE_CSV="$RESULTS/${TAG}_edge_probe.csv"
CENTRAL_CSV="$RESULTS/${TAG}_central_probe.csv"
TIMELINE="$RESULTS/${TAG}_timeline.txt"

TARGET_EDGE="10.70.0.10"
TARGET_CENTRAL="10.60.0.10"

echo "=== F05 experiment: UE route failure (blackhole) ==="
echo "tag: $TAG"
echo "blackhole target: $TARGET_EDGE"
echo "control target:   $TARGET_CENTRAL"

# 0. Ensure no leftover blackhole
sudo ip netns exec ue1 ip route del blackhole "$TARGET_EDGE"/32 2>/dev/null

# 1. Record state
{
    echo "=== before ==="
    sudo ip netns exec ue1 ip route
    echo
    sudo ip netns exec ue1 ip -br addr show oaitun_ue1
    sudo ip netns exec ue1 ip -br addr show oaitun_ue1p2
} > /tmp/f05-before.txt
cat /tmp/f05-before.txt

# 2. Start two probes in parallel (30 s each)
echo "[t=0] starting probes (30s each)"
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://"$TARGET_EDGE":8080/ --duration 30 --interval 0.2 \
    --out "$EDGE_CSV" &
PID_EDGE=$!

sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://"$TARGET_CENTRAL":8080/ --duration 30 --interval 0.2 \
    --out "$CENTRAL_CSV" &
PID_CENTRAL=$!

# 3. Baseline period
sleep 6

# 4. Inject fault: blackhole route for edge target only
T_FAULT=$(date -Is)
echo "[t=6s] INJECT: ip route add blackhole $TARGET_EDGE/32   ($T_FAULT)"
sudo ip netns exec ue1 ip route add blackhole "$TARGET_EDGE"/32
echo "      UE routes now:"
sudo ip netns exec ue1 ip route | sed 's/^/      /'

# 5. Fault window
sleep 12

# 6. Recover
T_RECOVER=$(date -Is)
echo "[t=18s] RECOVER: ip route del blackhole $TARGET_EDGE/32   ($T_RECOVER)"
sudo ip netns exec ue1 ip route del blackhole "$TARGET_EDGE"/32

# 7. Recovery window
sleep 12

# 8. Wait for probes
wait $PID_EDGE 2>/dev/null || true
wait $PID_CENTRAL 2>/dev/null || true

# 9. Post-state check
{
    echo "=== after ==="
    sudo ip netns exec ue1 ip route
    echo
    sudo ip netns exec ue1 ip -br addr show oaitun_ue1
    sudo ip netns exec ue1 ip -br addr show oaitun_ue1p2
} > /tmp/f05-after.txt
cat /tmp/f05-after.txt

# 10. Timeline
{
    echo "Experiment: $TAG"
    echo "Fault type: UE routing failure (blackhole route)"
    echo "Target: $TARGET_EDGE (edge-app)"
    echo "Control: $TARGET_CENTRAL (central factory-app)"
    echo "Fault injected:   $T_FAULT"
    echo "Recovery started: $T_RECOVER"
    echo "Edge probe CSV:    $EDGE_CSV"
    echo "Central probe CSV: $CENTRAL_CSV"
} | tee "$TIMELINE"

echo
echo "=== done ==="
