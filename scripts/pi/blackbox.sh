#!/bin/bash
# Black box recorder. Appends one line of machine state every INTERVAL seconds
# to the FAT32 boot partition, which any computer can read with the card in a
# reader. No network required, which is the whole point: the failures we care
# about are exactly the ones where the network is gone.
#
# Append is the safest FAT operation under sudden power loss, and every write
# is followed by sync, because the Pi dies without warning when the UBEC hiccups.
set -u

BB=/boot/firmware/blackbox
LOG="$BB/state.log"
INTERVAL=15
MAXLINES=8000

mkdir -p "$BB" 2>/dev/null

emit() { printf '%s\n' "$1" >> "$LOG"; sync; }

field() { # field <name> <value-or-empty>
  local v="${2:-}"
  [ -z "$v" ] && v="-"
  printf '%s=%s ' "$1" "${v// /_}"
}

sample() {
  local out=""
  out+=$(field ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)")
  out+=$(field up "$(cut -d. -f1 /proc/uptime 2>/dev/null)")

  # Undervoltage / throttling. Bit 0 = undervoltage NOW, bit 16 = since boot.
  # This is the single most important field given the UBEC history.
  out+=$(field thr "$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)")
  out+=$(field temp "$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null)")

  # Is the wifi driver even bound?
  out+=$(field wlan "$(cat /sys/class/net/wlan0/operstate 2>/dev/null)")
  out+=$(field ip4 "$(ip -4 -o addr show wlan0 2>/dev/null | awk '{print $4}' | head -1)")

  # Association state, independent of DHCP. Distinguishes "never joined the
  # network" from "joined but got no lease" -- two very different bugs.
  local link
  link=$(iw dev wlan0 link 2>/dev/null)
  if printf '%s' "$link" | grep -q "Not connected"; then
    out+=$(field assoc "no")
  else
    out+=$(field assoc "yes")
    out+=$(field ssid "$(printf '%s' "$link" | awk -F': ' '/SSID/{print $2; exit}')")
    out+=$(field rssi "$(printf '%s' "$link" | awk '/signal/{print $2; exit}')")
  fi

  # NetworkManager is the renderer on Pi OS Bookworm and later; netplan only
  # generates config for it. Its own opinion of wlan0 is worth recording.
  out+=$(field nm "$(nmcli -t -f DEVICE,STATE device status 2>/dev/null | awk -F: '$1=="wlan0"{print $2; exit}')")
  out+=$(field rfkill "$(rfkill list wlan 2>/dev/null | awk '/Soft/{print $3; exit}')")
  out+=$(field load "$(cut -d' ' -f1 /proc/loadavg 2>/dev/null)")
  out+=$(field rw "$(awk '$2=="/"{print ($4 ~ /^ro/) ? "ro" : "rw"; exit}' /proc/mounts)")

  emit "$out"
}

trim() {
  local n
  n=$(wc -l < "$LOG" 2>/dev/null || echo 0)
  if [ "$n" -gt "$MAXLINES" ]; then
    tail -n $((MAXLINES / 2)) "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG" && sync
  fi
}

case "${1:-run}" in
  run)
    emit "### boot mark $(date -u +%Y-%m-%dT%H:%M:%SZ) kernel=$(uname -r)"
    while true; do sample; trim; sleep "$INTERVAL"; done
    ;;
  stop)
    # Only reached on an orderly shutdown. If a boot section has no CLEAN
    # STOP at its end, that boot was killed by a power cut -- which is the
    # difference between a software bug and an electrical one.
    emit "### CLEAN STOP $(date -u +%Y-%m-%dT%H:%M:%SZ) up=$(cut -d. -f1 /proc/uptime)"
    ;;
esac
