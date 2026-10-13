#!/usr/bin/env bash
set -u

RESULTS=~/projects/private-5g/results/phase11
SCRIPTS=~/projects/private-5g/scripts/phase11
TAG=F01_$(date +%H%M%S)
PROBE_CSV="$RESULTS/${TAG}_probe.csv"
TIMELINE="$RESULTS/${TAG}_timeline.txt"

echo "=== F01 experiment: application HTTP server failure ==="
echo "tag: $TAG"

# 1. Ensure no leftover server
sudo pkill -f "http.server 8090" 2>/dev/null
sleep 1

# 2. Start dedicated F01 HTTP server in edge-app
echo "[t=0] starting HTTP server edge-app:8090"
sudo ip netns exec edge-app python3 -m http.server 8090 --bind 10.70.0.10 \
    > /tmp/f01-http.log 2>&1 &
sleep 2

if ! sudo ip netns exec edge-app ss -tln 2>/dev/null | grep -q 8090; then
    echo "ERROR: HTTP server did not start"
    exit 1
fi
echo "      server is listening on 10.70.0.10:8090"

# 3. Start probe from UE
echo "[t=2s] starting probe (40s @ 200ms)"
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://10.70.0.10:8090/ \
    --duration 40 \
    --interval 0.2 \
    --out "$PROBE_CSV" &
PROBE_PID=$!

# 4. Baseline period
sleep 8

# 5. Inject fault
T_FAULT=$(date -Is)
echo "[t=10s] FAULT INJECTED: killing HTTP server   ($T_FAULT)"
sudo pkill -f "http.server 8090"
sleep 1
if sudo ip netns exec edge-app ss -tln 2>/dev/null | grep -q 8090; then
    echo "      WARNING: port still open"
else
    echo "      port closed"
fi

# 6. Fault window
sleep 14

# 7. Recover
T_RECOVER=$(date -Is)
echo "[t=25s] RECOVERY: restarting HTTP server   ($T_RECOVER)"
sudo ip netns exec edge-app python3 -m http.server 8090 --bind 10.70.0.10 \
    > /tmp/f01-http2.log 2>&1 &
sleep 2
if sudo ip netns exec edge-app ss -tln 2>/dev/null | grep -q 8090; then
    echo "      server is back up"
else
    echo "      WARNING: server did not restart"
fi

# 8. Recovery window
sleep 16

# 9. Wait for probe to finish
wait $PROBE_PID 2>/dev/null || true

# 10. Cleanup
sudo pkill -f "http.server 8090" 2>/dev/null

# 11. Timeline
{
    echo "Experiment: $TAG"
    echo "Fault type: application HTTP server failure"
    echo "Target: edge-app HTTP server on 10.70.0.10:8090"
    echo "Probe: UE -> edge HTTP, every 200ms for 40s"
    echo "Fault injected:   $T_FAULT"
    echo "Recovery started: $T_RECOVER"
    echo "Probe CSV: $PROBE_CSV"
} | tee "$TIMELINE"

echo
echo "=== done. Timeline: $TIMELINE"
echo "=== probe CSV: $PROBE_CSV"
