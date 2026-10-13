#!/usr/bin/env bash
set -u

RESULTS=~/projects/private-5g/results/phase11
SCRIPTS=~/projects/private-5g/scripts/phase11
TAG=F06_$(date +%H%M%S)
EDGE_CSV="$RESULTS/${TAG}_edge_probe.csv"
CENTRAL_CSV="$RESULTS/${TAG}_central_probe.csv"
TIMELINE="$RESULTS/${TAG}_timeline.txt"

echo "=== F06 experiment: stop UPF-B (open5gs-upfd-edge) ==="
echo "tag: $TAG"

# 0. Capture pre-state
{
    echo "=== before stopping UPF-B ==="
    echo "--- UPF-B service ---"
    systemctl is-active open5gs-upfd-edge
    echo "--- ogstun2 ---"
    ip addr show ogstun2 2>/dev/null | grep -E 'state|inet '
    echo "--- UE interfaces ---"
    sudo ip netns exec ue1 ip -br addr 2>/dev/null | grep oaitun
    echo "--- UE routes ---"
    sudo ip netns exec ue1 ip route 2>/dev/null
} > /tmp/f06-before.txt
cat /tmp/f06-before.txt

# 1. Start two probes (60 s each, so we have time for a slow restart)
echo "[t=0] starting probes (60s)"
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://10.70.0.10:8080/ --duration 60 --interval 0.3 \
    --out "$EDGE_CSV" &
PID_EDGE=$!
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://10.60.0.10:8080/ --duration 60 --interval 0.3 \
    --out "$CENTRAL_CSV" &
PID_CENTRAL=$!

# 2. Baseline
sleep 8

# 3. Stop UPF-B
T_FAULT=$(date -Is)
echo "[t=8s] STOP: systemctl stop open5gs-upfd-edge   ($T_FAULT)"
sudo systemctl stop open5gs-upfd-edge
sleep 2
echo "      UPF-B active? $(systemctl is-active open5gs-upfd-edge)"
echo "      ogstun2 exists? $(ip link show ogstun2 >/dev/null 2>&1 && echo yes || echo no)"

# 4. Fault window
sleep 20

# 5. Restart UPF-B
T_RECOVER=$(date -Is)
echo "[t=28s] RESTART: systemctl start open5gs-upfd-edge   ($T_RECOVER)"
sudo systemctl start open5gs-upfd-edge
sleep 4
echo "      UPF-B active? $(systemctl is-active open5gs-upfd-edge)"

# 6. Try to bring ogstun2 back up if the service creates it but leaves it down
if ip link show ogstun2 >/dev/null 2>&1; then
    sudo ip link set ogstun2 up 2>/dev/null || true
    sudo ip addr add 10.46.0.1/16 dev ogstun2 2>/dev/null || true
    echo "      ogstun2: $(ip -br addr show ogstun2 2>/dev/null)"
fi

# 7. Recovery window
sleep 30

# 8. Wait for probes
wait $PID_EDGE 2>/dev/null || true
wait $PID_CENTRAL 2>/dev/null || true

# 9. Capture post-state
{
    echo "=== after restarting UPF-B ==="
    echo "--- UPF-B service ---"
    systemctl is-active open5gs-upfd-edge
    echo "--- ogstun2 ---"
    ip addr show ogstun2 2>/dev/null | grep -E 'state|inet '
    echo "--- UE interfaces ---"
    sudo ip netns exec ue1 ip -br addr 2>/dev/null | grep oaitun
    echo "--- UE routes ---"
    sudo ip netns exec ue1 ip route 2>/dev/null
} > /tmp/f06-after.txt
cat /tmp/f06-after.txt

# 10. Timeline
{
    echo "Experiment: $TAG"
    echo "Fault type: core-function failure (systemctl stop open5gs-upfd-edge)"
    echo "Target: UPF-B (edge DNN, factory path)"
    echo "Control: 10.60.0.10 (central factory-app, via UPF-A)"
    echo "Affected: 10.70.0.10 (edge-app, via UPF-B)"
    echo "Fault injected:   $T_FAULT"
    echo "Recovery started: $T_RECOVER"
    echo "Edge probe CSV:    $EDGE_CSV"
    echo "Central probe CSV: $CENTRAL_CSV"
} | tee "$TIMELINE"

echo
echo "=== done ==="
