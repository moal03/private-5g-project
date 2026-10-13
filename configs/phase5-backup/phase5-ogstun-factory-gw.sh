#!/bin/bash
# Ensure ogstun has the factory gateway 10.46.0.1/16
# Runs after open5gs-upfd creates ogstun
set -e
IFACE="ogstun"
ADDR="10.46.0.1/16"
MAX_WAIT=30
WAITED=0
while ! ip link show "$IFACE" &>/dev/null; do
    sleep 1
    WAITED=$((WAITED + 1))
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "Timeout waiting for $IFACE"
        exit 1
    fi
done
if ! ip addr show "$IFACE" | grep -q "10.46.0.1"; then
    ip addr add "$ADDR" dev "$IFACE"
    echo "Added $ADDR to $IFACE"
else
    echo "$ADDR already present on $IFACE"
fi
