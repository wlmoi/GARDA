#!/usr/bin/env bash
# Temporary Jetson address; no default route or unrelated addresses are removed.
set -euo pipefail

IFACE=${1:-}
IP_ADDR=${2:-192.168.50.1/24}
if ! command -v ip >/dev/null 2>&1; then
    echo "iproute2 is required" >&2
    exit 1
fi
if [[ -z "$IFACE" ]]; then
    if [[ -d /sys/class/net/enP8p1s0 ]]; then
        IFACE=enP8p1s0
    else
        candidates=()
        for path in /sys/class/net/*; do
            [[ -e "$path/device" && ! -d "$path/wireless" ]] || continue
            candidates+=("${path##*/}")
        done
        if [[ ${#candidates[@]} -ne 1 ]]; then
            echo "Specify the wired interface: $0 INTERFACE [ADDRESS/24]" >&2
            ip -br link
            exit 1
        fi
        IFACE=${candidates[0]}
    fi
fi
[[ "$IFACE" != -* && -d "/sys/class/net/$IFACE" ]] || {
    echo "Invalid or missing interface: $IFACE" >&2
    exit 1
}
prefix=()
if [[ $EUID -ne 0 ]]; then prefix=(sudo); fi
"${prefix[@]}" ip link set dev "$IFACE" up
"${prefix[@]}" ip address replace "$IP_ADDR" dev "$IFACE"
ip -br address show dev "$IFACE"
if [[ $(cat "/sys/class/net/$IFACE/carrier") != 1 ]]; then
    echo "Address configured, but no physical carrier. Check cable and DE10 power/boot." >&2
    exit 1
fi
echo "Carrier detected. HPS must separately use 192.168.50.2/24; this does not verify inference."
