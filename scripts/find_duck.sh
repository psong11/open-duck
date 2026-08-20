#!/usr/bin/env bash
# Locate the duck's Raspberry Pi Zero 2W on the LAN by MAC address.
#
# Why not hostname? mDNS (.local) does not resolve on this router.
# Why not a fixed IP? DHCP moves it. The MAC is the only stable identity.
#
#   ./scripts/find_duck.sh          # print the IP
#   ./scripts/find_duck.sh --ssh    # print a ready-to-paste ssh command

set -uo pipefail

DUCK_MAC="${DUCK_MAC:-88:a2:9e:58:0:d7}"   # macOS arp strips leading zeros
SUBNET="${DUCK_SUBNET:-172.20.154}"

norm() { echo "$1" | tr 'A-Z' 'a-z' | sed 's/0\([0-9a-f]\)/\1/g'; }
want=$(norm "$DUCK_MAC")

echo "sweeping ${SUBNET}.0/24 for ${DUCK_MAC} ..." >&2
for i in $(seq 1 254); do ping -c1 -W400 "${SUBNET}.$i" >/dev/null 2>&1 & done
wait 2>/dev/null

ip=$(arp -an | grep -v incomplete | while read -r _ a _ m _; do
        [ "$(norm "$m")" = "$want" ] && echo "${a//[()]/}"
     done | head -1)

if [ -z "$ip" ]; then
  echo "duck not found. powered on? joined the hidden SSID?" >&2
  exit 1
fi

# ARP entries go stale — confirm it actually answers.
if ! ping -c2 -W800 "$ip" >/dev/null 2>&1; then
  echo "stale ARP entry at $ip — not responding. duck is probably off." >&2
  exit 1
fi

if [ "${1:-}" = "--ssh" ]; then echo "ssh ${DUCK_USER:-pi}@$ip"; else echo "$ip"; fi
