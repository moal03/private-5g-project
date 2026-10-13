#!/usr/bin/env bash
#
# Phase 7 — Central vs Edge measurement harness.
#
# Runs N sequential trials of:
#   1. ping to central (10.60.0.10)  via oaitun_ue1
#   2. ping to edge    (10.70.0.10)  via oaitun_ue1p2
#   3. iperf3 to central (60 s)
#   4. iperf3 to edge    (60 s)
#
# Saves all raw outputs under results/phase7/.

set -u

REPO="/home/mohammad/projects/private-5g"
RESULTS="${REPO}/results/phase7"
mkdir -p "$RESULTS"

CENTRAL="10.60.0.10"
EDGE="10.70.0.10"
UE_NS="ue1"

PING_COUNT=200
IPERF_DURATION=60

# Warmup (no load)
echo "[warmup] Pinging central once..."
sudo ip netns exec "$UE_NS" ping -c 1 -I oaitun_ue1 "$CENTRAL" >/dev/null 2>&1
echo "[warmup] Pinging edge once..."
sudo ip netns exec "$UE_NS" ping -c 1 -I oaitun_ue1p2 "$EDGE" >/dev/null 2>&1

# --- Ping central ---
echo
echo "=================================================="
echo "PING CENTRAL (${CENTRAL}) via oaitun_ue1 (UPF-A)"
echo "=================================================="
sudo ip netns exec "$UE_NS" ping -c "$PING_COUNT" -i 0.05 -I oaitun_ue1 "$CENTRAL" \
  | tee "$RESULTS/ping-central.txt"

# --- Ping edge ---
echo
echo "=================================================="
echo "PING EDGE (${EDGE}) via oaitun_ue1p2 (UPF-B)"
echo "=================================================="
sudo ip netns exec "$UE_NS" ping -c "$PING_COUNT" -i 0.05 -I oaitun_ue1p2 "$EDGE" \
  | tee "$RESULTS/ping-edge.txt"

# --- iperf3 central ---
echo
echo "=================================================="
echo "IPERF3 CENTRAL (${IPERF_DURATION}s TCP)"
echo "=================================================="
sudo ip netns exec "$UE_NS" iperf3 -c "$CENTRAL" -t "$IPERF_DURATION" -i 5 \
  | tee "$RESULTS/iperf3-central.txt"

# --- iperf3 edge ---
echo
echo "=================================================="
echo "IPERF3 EDGE (${IPERF_DURATION}s TCP)"
echo "=================================================="
sudo ip netns exec "$UE_NS" iperf3 -c "$EDGE" -t "$IPERF_DURATION" -i 5 \
  | tee "$RESULTS/iperf3-edge.txt"

echo
echo "[done] Raw results saved under $RESULTS"
