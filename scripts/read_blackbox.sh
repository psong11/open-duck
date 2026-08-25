#!/usr/bin/env bash
# Run on the Mac with the Pi's card in a reader, after any failure.
#   ./scripts/read_blackbox.sh          # summary
#   ./scripts/read_blackbox.sh --dump   # copy everything into ./blackbox-<ts>/
set -euo pipefail

BOOT=${BOOT:-/Volumes/bootfs}
BB="$BOOT/blackbox"

[ -d "$BB" ] || { echo "!! no $BB — this card was never instrumented, or never booted after instrumenting."; exit 1; }

if [ "${1:-}" = "--dump" ]; then
  dest="blackbox-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dest" && cp -R "$BB"/* "$dest"/ && echo "copied to $dest/" && exit 0
fi

echo "=============== INSTALL ==============="
cat "$BB/installed.txt" 2>/dev/null || echo "(no install marker)"

echo
echo "=============== BOOTS ==============="
printf '%-14s %-22s %s\n' FILE SIZE MODIFIED
for f in "$BB"/boot-*.txt; do
  [ -e "$f" ] || { echo "(no boot snapshots yet)"; break; }
  printf '%-14s %-22s %s\n' "$(basename "$f")" "$(wc -c < "$f") bytes" "$(date -r "$f" '+%F %T')"
done

echo
echo "=============== POWER / THROTTLING ==============="
# thr bit 0 = undervoltage now, bit 16 = undervoltage has occurred since boot.
awk '/thr=/{for(i=1;i<=NF;i++) if($i ~ /^thr=/){split($i,a,"="); if(a[2]!="0x0" && a[2]!="-") print $1, $i}}' \
  "$BB/state.log" 2>/dev/null | sort -u -k2 | head -20 || true
grep -qE 'thr=0x[^0]' "$BB/state.log" 2>/dev/null && echo "  ^^ UNDERVOLTAGE DETECTED" || echo "  no throttling recorded — power was clean"

echo
echo "=============== UNCLEAN SHUTDOWNS ==============="
# A boot mark not followed by a CLEAN STOP means the Pi was killed, not shut down.
awk '/^### boot mark/{if(pending) print "  HARD POWER CUT before: " $0; pending=1; last=$0}
     /^### CLEAN STOP/{pending=0}
     /^### recorder restarted/{pending=0}
     END{if(pending) print "  (current boot still running or died: " last ")"}' \
  "$BB/state.log" 2>/dev/null || true

echo
echo "=============== READ-ONLY ROOT (ext4 corruption signature) ==============="
if grep -q 'rw=ro' "$BB/state.log" 2>/dev/null; then
  echo "  ROOT WENT READ-ONLY — the filesystem hit an error and ext4 protected itself."
  grep -m5 'rw=ro' "$BB/state.log" | awk '{print "   ", $1}'
else
  echo "  root stayed writable"
fi

echo
echo "=============== WIFI TIMELINE (state changes only) ==============="
awk '/^### /{print; prev=""; next}
     {a="";i4="";nm="";
      for(i=1;i<=NF;i++){if($i~/^assoc=/)a=$i; if($i~/^ip4=/)i4=$i; if($i~/^nm=/)nm=$i}
      up=""; for(i=1;i<=NF;i++) if($i~/^up=/) up=$i
      k=a" "i4" "nm; if(k!=prev){sub(/^ts=/,"",$1); printf "  %-22s %-8s %s\n", $1, up, k; prev=k}}' \
  "$BB/state.log" 2>/dev/null | tail -40 || true

echo
echo "=============== LAST 10 SAMPLES ==============="
tail -10 "$BB/state.log" 2>/dev/null || true

latest=$(ls -1 "$BB"/boot-*.txt 2>/dev/null | sort | tail -1)
if [ -n "$latest" ]; then
  echo
  echo "=============== $(basename "$latest"): FAILED UNITS + PREVIOUS BOOT ERRORS ==============="
  awk '/^===== failed units/,/^===== this boot: errors/' "$latest" | head -40
  awk '/^===== PREVIOUS BOOT: errors/,/^===== PREVIOUS BOOT: NetworkManager/' "$latest" | head -60
  echo
  echo "(full detail: $latest)"
fi
