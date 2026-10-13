#!/usr/bin/env bash
#
# Phase 6 trial runner.
# Usage: run_trial.sh CONDITION LOAD_MBPS TRIAL_NUM
#   CONDITION = baseline | treatment
#   LOAD_MBPS = 0 | 10 | 25 | 50
#   TRIAL_NUM = 1 | 2 | 3
#
set -u

CONDITION="${1:?Condition required: baseline|treatment}"
LOAD_MBPS="${2:?Load Mbps required: 0|15|35}"
TRIAL_NUM="${3:?Trial number required: 1|2|3}"

# --- Paths ---
REPO="/home/mohammad/projects/private-5g"
RESULTS_DIR="${REPO}/results/phase6/raw"
mkdir -p "$RESULTS_DIR"

URLLC_SCRIPT="${REPO}/scripts/phase6/urllc_client.py"
URLLC_OUT="${RESULTS_DIR}/${CONDITION}_load${LOAD_MBPS}_trial${TRIAL_NUM}_urllc.csv"
IPERF_OUT="${RESULTS_DIR}/${CONDITION}_load${LOAD_MBPS}_trial${TRIAL_NUM}_embb.txt"
META_OUT="${RESULTS_DIR}/${CONDITION}_load${LOAD_MBPS}_trial${TRIAL_NUM}_meta.txt"

# --- Parameters ---
UE_NS="ue1"
URLLC_SERVER="10.60.0.10"
URLLC_PORT=9200
URLLC_BIND="10.46.0.6"     # UE factory slice IP
URLLC_RATE=50              # 50 pps
URLLC_DURATION=90          # 90 seconds total
WARMUP=30                  # 30s warmup before load
EMBB_DURATION=30           # 30s load window

# --- Metadata ---
{
  echo "Condition:  ${CONDITION}"
  echo "Load:       ${LOAD_MBPS} Mbps"
  echo "Trial:      ${TRIAL_NUM}"
  echo "Start time: $(date -Is)"
  echo "URLLC rate: ${URLLC_RATE} pps"
  echo "URLLC dur:  ${URLLC_DURATION} s"
  echo "Load dur:   ${EMBB_DURATION} s"
} > "$META_OUT"

echo "=========================================="
echo "Trial: ${CONDITION} / ${LOAD_MBPS} Mbps / Trial ${TRIAL_NUM}"
echo "=========================================="
echo "URLLC CSV:  $URLLC_OUT"
echo "eMBB  log:  $IPERF_OUT"

# --- Start URLLC client in background ---
echo "[t=0] Starting URLLC client..."
sudo ip netns exec "$UE_NS" python3 "$URLLC_SCRIPT" \
  --server "$URLLC_SERVER" \
  --port "$URLLC_PORT" \
  --bind "$URLLC_BIND" \
  --rate "$URLLC_RATE" \
  --duration "$URLLC_DURATION" \
  --out "$URLLC_OUT" \
  > /tmp/urllc-stdout.log 2>&1 &
URLLC_PID=$!

# --- Warmup ---
echo "[t=0] Warmup for ${WARMUP}s..."
sleep "$WARMUP"

# --- Start eMBB load (only if LOAD_MBPS > 0) ---
if [ "$LOAD_MBPS" -gt 0 ]; then
  echo "[t=$WARMUP] Starting eMBB load: ${LOAD_MBPS} Mbps for ${EMBB_DURATION}s..."
  sudo ip netns exec "$UE_NS" iperf3 \
    -c 10.45.0.1 -u -b "${LOAD_MBPS}M" -t "$EMBB_DURATION" \
    > "$IPERF_OUT" 2>&1 &
  IPERF_PID=$!

  # Wait for iperf to finish
  wait "$IPERF_PID"
  echo "[t=$((WARMUP+EMBB_DURATION))] eMBB load finished."
else
  echo "[t=$WARMUP] No load (LOAD_MBPS=0). Running URLLC-only for remaining time..."
  echo "(no load)" > "$IPERF_OUT"
fi

# --- Wait for URLLC client to finish ---
echo "[t=$WARMUP] Waiting for URLLC client to finish..."
wait "$URLLC_PID"

echo "[t=done] URLLC client finished."
echo "[t=done] Trial complete."

{
  echo "End time:   $(date -Is)"
  echo "URLLC CSV:  $URLLC_OUT"
  echo "eMBB log:   $IPERF_OUT"
  echo "URLLC stdout:"
  cat /tmp/urllc-stdout.log 2>/dev/null | tail -5
} >> "$META_OUT"

echo
echo "=== Trial summary ==="
cat "$META_OUT"
