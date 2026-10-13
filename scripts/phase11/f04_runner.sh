#!/usr/bin/env bash
set -u

RESULTS=~/projects/private-5g/results/phase11
SCRIPTS=~/projects/private-5g/scripts/phase11
TAG=F04_$(date +%H%M%S)
EDGE_CSV="$RESULTS/${TAG}_edge_probe.csv"
CENTRAL_CSV="$RESULTS/${TAG}_central_probe.csv"
IPERF_OUT="$RESULTS/${TAG}_iperf_during_fault.txt"
TIMELINE="$RESULTS/${TAG}_timeline.txt"

IFACE="ogstun2"
RATE="2mbit"
BURST="32kb"
LATENCY="400ms"

echo "=== F04 experiment: bandwidth limit tbf on $IFACE ==="
echo "tag: $TAG"
echo "rate: $RATE  burst: $BURST  latency: $LATENCY"

# 0. Clean
sudo tc qdisc del dev "$IFACE" root 2>/dev/null || true
sudo pkill -9 iperf3 2>/dev/null || true
sleep 1

# 1. Confirm qdisc
echo "[before] qdisc on $IFACE:"
tc qdisc show dev "$IFACE" | sed 's/^/  /'

# 2. Start iperf3 server for later throughput test
sudo ip netns exec edge-app iperf3 -s -B 10.70.0.10 >/dev/null 2>&1 &
sleep 1

# 3. Start HTTP probes (40s to allow iperf3 inside)
echo "[t=0] starting probes (40s)"
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://10.70.0.10:8080/ --duration 40 --interval 0.3 \
    --out "$EDGE_CSV" &
PID_EDGE=$!
sudo ip netns exec ue1 python3 "$SCRIPTS/f01_probe.py" \
    --url http://10.60.0.10:8080/ --duration 40 --interval 0.3 \
    --out "$CENTRAL_CSV" &
PID_CENTRAL=$!

# 4. Baseline
sleep 6

# 5. Inject bandwidth limit
T_FAULT=$(date -Is)
echo "[t=6s] INJECT: tc qdisc add dev $IFACE root tbf rate $RATE burst $BURST latency $LATENCY   ($T_FAULT)"
sudo tc qdisc add dev "$IFACE" root tbf rate "$RATE" burst "$BURST" latency "$LATENCY"
tc -s qdisc show dev "$IFACE" | sed 's/^/  /'

# 6. Throughput test during fault (TCP through edge DNN)
echo "[t=8s] running iperf3 TCP test to edge-app (10s)"
sudo ip netns exec ue1 timeout 15 iperf3 -c 10.70.0.10 -t 10 -i 5 \
    > "$IPERF_OUT" 2>&1 || true
tail -5 "$IPERF_OUT" | sed 's/^/    /'

# 7. Recovery
T_RECOVER=$(date -Is)
echo "[t=25s] RECOVER: tc qdisc del dev $IFACE root   ($T_RECOVER)"
sudo tc qdisc del dev "$IFACE" root
tc qdisc show dev "$IFACE" | sed 's/^/  /'

# 8. Recovery window
sleep 15

# 9. Wait for probes
wait $PID_EDGE 2>/dev/null || true
wait $PID_CENTRAL 2>/dev/null || true

# 10. Final check
echo "[after] qdisc on $IFACE:"
tc qdisc show dev "$IFACE" | sed 's/^/  /'

# 11. Timeline
{
    echo "Experiment: $TAG"
    echo "Fault type: tbf rate limit $RATE on $IFACE (edge UPF egress)"
    echo "Parameters: rate=$RATE burst=$BURST latency=$LATENCY"
    echo "Target: 10.70.0.10 (edge-app)"
    echo "Control: 10.60.0.10 (central factory-app, unaffected path)"
    echo "Fault injected:   $T_FAULT"
    echo "Recovery started: $T_RECOVER"
    echo "Edge probe CSV:    $EDGE_CSV"
    echo "Central probe CSV: $CENTRAL_CSV"
    echo "iperf3 during fault: $IPERF_OUT"
} | tee "$TIMELINE"

echo
echo "=== done ==="
