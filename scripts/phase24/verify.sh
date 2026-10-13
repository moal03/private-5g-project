#!/usr/bin/env bash
#
# Phase 24 — Testbed verification.
#
# Checks every layer of the testbed and prints a PASS/FAIL/SKIP
# summary. Read-only: makes no configuration changes.
#
# Usage:
#   ./verify.sh           # run all checks
#   ./verify.sh -q        # quiet, print summary only
#
set -u

QUIET=0
if [ "${1:-}" = "-q" ]; then
    QUIET=1
fi

PASS=0
FAIL=0
SKIP=0
FAILED_CHECKS=()

check() {
    local name="$1"
    local cmd="$2"
    local expect="$3"
    local optional="${4:-required}"

    local result
    result=$(eval "$cmd" 2>/dev/null)

    if [ "$result" = "$expect" ]; then
        PASS=$((PASS+1))
        [ "$QUIET" -eq 0 ] && printf "  [PASS] %s\n" "$name"
    elif [ "$optional" = "optional" ]; then
        SKIP=$((SKIP+1))
        [ "$QUIET" -eq 0 ] && printf "  [SKIP] %s (optional; got: %s)\n" "$name" "$result"
    else
        FAIL=$((FAIL+1))
        FAILED_CHECKS+=("$name")
        printf "  [FAIL] %s (expected: %s, got: %s)\n" "$name" "$expect" "$result"
    fi
}

check_contains() {
    local name="$1"
    local cmd="$2"
    local pattern="$3"
    local optional="${4:-required}"

    local result
    result=$(eval "$cmd" 2>/dev/null)

    if echo "$result" | grep -q "$pattern"; then
        PASS=$((PASS+1))
        [ "$QUIET" -eq 0 ] && printf "  [PASS] %s\n" "$name"
    elif [ "$optional" = "optional" ]; then
        SKIP=$((SKIP+1))
        [ "$QUIET" -eq 0 ] && printf "  [SKIP] %s (optional)\n" "$name"
    else
        FAIL=$((FAIL+1))
        FAILED_CHECKS+=("$name")
        printf "  [FAIL] %s (pattern not found: %s)\n" "$name" "$pattern"
    fi
}

section() {
    [ "$QUIET" -eq 0 ] && printf "\n=== %s ===\n" "$1"
}

echo "=========================================================="
echo "  Testbed Verification"
echo "  $(date -Is)"
echo "  Host: $(hostname)"
echo "=========================================================="

# ---------- 1. Host ----------
section "Host"
check "Kernel 7.x present" "[ \"\$(uname -r | cut -d. -f1)\" -ge 7 ] && echo yes" "yes"
check "8 or more CPU threads" "[ \$(nproc) -ge 8 ] && echo yes" "yes"
check "At least 6 GiB RAM free" "[ \$(free -m | awk '/Mem/{print \$7}') -ge 6000 ] && echo yes" "yes"
check "At least 50 GiB disk free on /" "[ \$(df -BG / | awk 'NR==2 {print \$4}' | tr -d G) -ge 50 ] && echo yes" "yes"

# ---------- 2. Kernel prerequisites ----------
section "Kernel prerequisites"
check "/dev/net/tun exists" "[ -c /dev/net/tun ] && echo yes" "yes"
check_contains "sctp kernel module loaded" "lsmod" "^sctp "
check "ip_forward enabled" "sysctl -n net.ipv4.ip_forward" "1"

# ---------- 3. Open5GS ----------
section "Open5GS core"
check "AMF active" "systemctl is-active open5gs-amfd" "active"
check "SMF active" "systemctl is-active open5gs-smfd" "active"
check "UPF-A active" "systemctl is-active open5gs-upfd" "active"
check "UPF-B (edge) active" "systemctl is-active open5gs-upfd-edge" "active"
check "AUSF active" "systemctl is-active open5gs-ausfd" "active"
check "UDM active" "systemctl is-active open5gs-udmd" "active"
check "UDR active" "systemctl is-active open5gs-udrd" "active"

# ---------- 4. Open5GS listeners ----------
section "Open5GS listeners"
check_contains "AMF N2 listener on 38412" "sudo ss -lnp" "38412"
check_contains "SMF PFCP listener on 8805" "sudo ss -lunp" "127.0.0.4:8805"
check_contains "UPF-A GTP-U on 127.0.0.7:2152" "sudo ss -lunp" "127.0.0.7:2152"
check_contains "UPF-B GTP-U on 127.0.0.8:2152" "sudo ss -lunp" "127.0.0.8:2152"

# ---------- 5. Open5GS TUN interfaces ----------
section "Open5GS TUN interfaces"
check_contains "ogstun (UPF-A) up with 10.45.0.1" "ip addr show ogstun" "10.45.0.1/16"
check_contains "ogstun2 (UPF-B) present" "ip link show ogstun2 2>/dev/null || echo absent" "ogstun2"

# ---------- 6. RAN (CU + DU) ----------
section "RAN (OCUDU)"
check "CU process running" "pgrep -f 'apps/cu/ocu' | wc -l" "1"
check "DU process running" "pgrep -f 'apps/du/odu' | wc -l" "1"
check_contains "CU F1-C listener on 38472" "sudo ss -lnp" "38472"
check_contains "DU ZMQ port 4556 listening" "sudo ss -lntp" ":4556"
# Locate the DU log: read from config, fall back to known paths
DU_LOG=""
for candidate in \
    "$(grep -A2 '^log:' configs/ocudu/du_zmq_e2.yml 2>/dev/null | grep -oE '/[^ ]+\.log' | head -1)" \
    "$HOME/projects/private-5g/logs/phase12/ocudu/du.log" \
    "/tmp/ocudu-du.log"
do
    if [ -n "$candidate" ] && [ -f "$candidate" ]; then
        DU_LOG="$candidate"
        break
    fi
done

# Re-resolve inside the caller's environment, without quoting the path
DU_LOG_RESOLVED=""
for candidate in \
    "$(grep -A2 '^log:' configs/ocudu/du_zmq_e2.yml 2>/dev/null | grep -oE '/[^ ]+\.log' | head -1)" \
    "$HOME/projects/private-5g/logs/phase12/ocudu/du.log" \
    "/tmp/ocudu-du.log"
do
    if [ -n "$candidate" ] && [ -f "$candidate" ]; then
        DU_LOG_RESOLVED="$candidate"
        break
    fi
done

if [ -n "$DU_LOG_RESOLVED" ]; then
    check_contains "DU F1 Setup completed" \
      "sudo grep -m 1 'F1 Setup: Procedure completed successfully' $DU_LOG_RESOLVED 2>/dev/null || echo ''" \
      "F1 Setup: Procedure completed successfully" \
      "optional"
    check_contains "DU cell scheduling active" \
      "sudo grep -m 1 'Cell scheduling was activated' $DU_LOG_RESOLVED 2>/dev/null || echo ''" \
      "Cell scheduling was activated" \
      "optional"
else
    printf "  [SKIP] DU log not found\n"
fi

# ---------- 7. UE ----------
section "UE"
check "UE process running" "pgrep -f nr-uesoftmodem | wc -l" "2"
check_contains "UE namespace exists" "sudo ip netns list" "ue1"
check_contains "oaitun_ue1 present (internet)" \
  "sudo ip netns exec ue1 ip -br addr 2>/dev/null || echo ''" \
  "oaitun_ue1"
check_contains "oaitun_ue1p2 present (factory)" \
  "sudo ip netns exec ue1 ip -br addr 2>/dev/null || echo ''" \
  "oaitun_ue1p2"

# ---------- 8. Data path ----------
section "Data path"
check "UE -> central (10.60.0.10) reachable" \
  "sudo ip netns exec ue1 ping -c 1 -W 2 -I oaitun_ue1 10.60.0.10 >/dev/null 2>&1 && echo ok" \
  "ok" \
  "optional"
check "UE -> edge (10.70.0.10) reachable" \
  "sudo ip netns exec ue1 ping -c 1 -W 2 -I oaitun_ue1p2 10.70.0.10 >/dev/null 2>&1 && echo ok" \
  "ok" \
  "optional"

# ---------- 9. Monitoring ----------
section "Monitoring"
check "Prometheus active" "systemctl is-active prometheus" "active"
check "node-exporter active" "systemctl is-active prometheus-node-exporter" "active"
check "Grafana active" "systemctl is-active grafana-server" "active"
check_contains "Prometheus on 9095" "sudo ss -lntp" ":9095"
check_contains "node-exporter on 9100" "sudo ss -lntp" ":9100"
check_contains "Grafana on 3000" "sudo ss -lntp" ":3000"

# ---------- 10. RIC (optional) ----------
section "RIC (optional)"
check "FlexRIC nearRT-RIC running" "pgrep -f nearRT-RIC | wc -l" "1" "optional"
check_contains "RIC E2 listener on 36421" "sudo ss -lnp 2>/dev/null || echo ''" \
  ":36421" "optional"

# ---------- Summary ----------
echo
echo "=========================================================="
echo "  SUMMARY"
echo "=========================================================="
TOTAL=$((PASS+FAIL+SKIP))
printf "  Total : %d\n" "$TOTAL"
printf "  PASS  : %d\n" "$PASS"
printf "  FAIL  : %d\n" "$FAIL"
printf "  SKIP  : %d (optional checks)\n" "$SKIP"
echo

if [ "$FAIL" -eq 0 ]; then
    echo "  RESULT: Verification passed."
    echo "          All required components are operational."
else
    echo "  RESULT: $FAIL check(s) failed."
    echo "  Failed checks:"
    for c in "${FAILED_CHECKS[@]}"; do
        echo "    - $c"
    done
fi

exit $FAIL
