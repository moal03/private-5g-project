#!/usr/bin/env bash
set -u

RESULTS=~/projects/private-5g/results/phase10
SCRIPTS=~/projects/private-5g/scripts/phase10
TAG=F02_$(date +%H%M%S)
EDGE_CSV="$RESULTS/${TAG}_edge_probe.csv"
CENTRAL_CSV="$RESULTS/${TAG}_central_probe.csv"
TIMELINE="$RESULTS/${TAG}_timeline.txt"

IFACE="ogstun2"
DELAY="50ms"

echo "=== F02 experiment: netem delay on $IFACE ==="
echo "tag: $TAG"
echo "delay: $DELAY"

# 0. Clean qdisc
sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true

# 1. Confirm qdisc before
echo "[before] qdisc on $IFACE:"
tc qdisc show dev "$IFACE" | sed 's/^/  /'

# 2. Start probes in parallel (30 s each)
echo "[t=0] starting probes (30s)"
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://10.70.0.10:8080/ --duration 30 --interval 0.2 \
    --out "$EDGE_CSV" &
PID_EDGE=$!
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://10.60.0.10:8080/ --duration 30 --interval 0.2 \
    --out "$CENTRAL_CSV" &
PID_CENTRAL=$!

# 3. Baseline
sleep 6

# 4. Inject delay
T_FAULT=$(date -Is)
echo "[t=6s] INJECT: tc qdisc add dev $IFACE root netem delay $DELAY   ($T_FAULT)"
sudo tc qdisc add dev "$IFACE" root netem delay "$DELAY"
tc qdisc show dev "$IFACE" | sed 's/^/  /'

# 5. Fault window
sleep 12

# 6. Recover
T_RECOVER=$(date -Is)
echo "[t=18s] RECOVER: tc qdisc del dev $IFACE root   ($T_RECOVER)"
sudo tc qdisc del dev "$IFACE" root
tc qdisc show dev "$IFACE" | sed 's/^/  /'

# 7. Recovery window
sleep 12

# 8. Wait for probes
wait $PID_EDGE 2>/dev/null || true
wait $PID_CENTRAL 2>/dev/null || true

# 9. Final qdisc check
echo "[after] qdisc on $IFACE:"
tc qdisc show dev "$IFACE" | sed 's/^/  /'

# 10. Timeline
{
    echo "Experiment: $TAG"
    echo "Fault type: netem delay $DELAY on $IFACE (edge UPF egress)"
    echo "Target: 10.70.0.10 (edge-app)"
    echo "Control: 10.60.0.10 (central factory-app, unaffected path)"
    echo "Fault injected:   $T_FAULT"
    echo "Recovery started: $T_RECOVER"
    echo "Edge probe CSV:    $EDGE_CSV"
    echo "Central probe CSV: $CENTRAL_CSV"
} | tee "$TIMELINE"

echo
echo "=== done ==="
