#!/bin/bash
# Per-boot forensic snapshot -> /boot/firmware/blackbox/boot-NNN.txt
#
# The most valuable thing in here is the PREVIOUS boot's journal. When the Pi
# fails to come back, the evidence for why lives in the boot that died, and
# that evidence only survives if journald is persistent (enabled at install).
set -u

BB=/boot/firmware/blackbox
mkdir -p "$BB" 2>/dev/null

# Monotonic boot counter kept on the FAT partition so it survives anything.
CNT="$BB/.bootcount"
n=$(cat "$CNT" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$CNT"
OUT=$(printf '%s/boot-%03d.txt' "$BB" "$n")

# Let the network finish trying and failing before we take the picture.
sleep "${SNAP_DELAY:-75}"

section() { printf '\n\n===== %s =====\n' "$1" >> "$OUT"; }
run() { section "$1"; shift; "$@" >> "$OUT" 2>&1 || echo "(command failed: $*)" >> "$OUT"; }

{
  echo "boot #$n   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "kernel     $(uname -a)"
  echo "os         $(. /etc/os-release; echo "$PRETTY_NAME")"
  echo "python     $(python3 -V 2>&1)"
} > "$OUT"

# --- why the last boot ended -------------------------------------------------
run "PREVIOUS BOOT: errors and warnings" journalctl -b -1 -p warning --no-pager -n 250
run "PREVIOUS BOOT: NetworkManager"      journalctl -b -1 -u NetworkManager --no-pager -n 200
run "PREVIOUS BOOT: last 60 lines"       journalctl -b -1 --no-pager -n 60

# --- state of this boot ------------------------------------------------------
run "failed units"          systemctl --failed --no-pager
run "this boot: errors"     journalctl -b 0 -p err --no-pager -n 200
run "this boot: NetworkManager" journalctl -b 0 -u NetworkManager --no-pager -n 200
run "this boot: wpa_supplicant" journalctl -b 0 -u wpa_supplicant --no-pager -n 100
run "cloud-init status"     cloud-init status --long

# --- networking --------------------------------------------------------------
run "ip addr"               ip -d addr
run "ip route"              ip route
run "nmcli devices"         nmcli -f DEVICE,TYPE,STATE,CONNECTION device status
run "nmcli wlan0 detail"    nmcli device show wlan0
run "iw link"               iw dev wlan0 link
run "iw scan (SSIDs seen)"  timeout 30 iw dev wlan0 scan ap-force
run "rfkill"                rfkill list
run "regulatory domain"     iw reg get

section "netplan config"
cat /etc/netplan/* >> "$OUT" 2>&1

section "NetworkManager system-connections"
for f in /etc/NetworkManager/system-connections/*; do
  echo "--- $f"; sed 's/^psk=.*/psk=<redacted>/' "$f"
done >> "$OUT" 2>&1

# --- hardware / storage ------------------------------------------------------
run "wifi driver messages"  sh -c "dmesg | grep -iE 'brcmfmac|cfg80211|mmc|sdhci|EXT4|I/O error' | tail -120"
run "throttling"            vcgencmd get_throttled
run "filesystem check"      systemctl status systemd-fsck-root.service --no-pager
run "disk usage"            df -h
run "full dmesg"            dmesg

# Keep the last 6 boots so the partition never fills.
ls -1 "$BB"/boot-*.txt 2>/dev/null | sort | head -n -6 | xargs -r rm -f
sync
