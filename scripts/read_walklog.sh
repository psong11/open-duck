#!/usr/bin/env bash
# Pull the newest walk + power logs off the duck and say what ended the run.
#
# The question this answers is always the same one: did the walk EXIT, or did
# the Pi DIE? A run that exits writes an "### END" marker. A run that dies just
# stops. Absence of the marker is the finding -- so this script leads with it.
#
#   ./read_walklog.sh              # newest pair
#   DUCK_HOST=paul@1.2.3.4 ./read_walklog.sh
set -uo pipefail

HOST="${DUCK_HOST:-paul@172.20.154.205}"
DEST="${1:-$HOME/duck-walklogs}"

mkdir -p "$DEST"
echo "pulling from $HOST ..."
if ! scp -q "$HOST:~/walklogs/*.csv" "$DEST/" 2>/dev/null; then
  echo "no logs pulled (host down, or none recorded yet)" >&2
  exit 1
fi

walk="$(ls -t "$DEST"/walk-*.csv 2>/dev/null | head -1)"
power="$(ls -t "$DEST"/power-*.csv 2>/dev/null | head -1)"

report() {
  local f="$1" kind="$2"
  [ -z "$f" ] && { printf '\n== %s ==\n  (none)\n' "$kind"; return; }
  printf '\n== %s ==\n  %s\n' "$kind" "$(basename "$f")"

  local start end last
  start="$(grep -m1 '^### START' "$f")"
  end="$(grep -m1 '^### END' "$f")"
  last="$(grep -v '^#' "$f" | tail -1)"

  echo "  $start"
  if [ -n "$end" ]; then
    echo "  $end"
    echo "  VERDICT: exited cleanly -- the process decided to stop."
  else
    echo "  ### END: MISSING"
    echo "  VERDICT: no terminator. The process was killed with the machine."
    echo "  last durable sample: ${last:-<none>}"
    echo "  time of death: $(echo "$last" | cut -d, -f1)s after start (+/- one sample)"
  fi

  # Any explicit marks are the interesting narrative beats.
  grep '^### ' "$f" | grep -v 'START\|END' | sed 's/^/  mark: /'
}

report "$walk" "WALK LOOP"
report "$power" "POWER RAIL"

if [ -n "$power" ]; then
  printf '\n== RAIL DETAIL ==\n'
  # lcrit is the rpi_volt low-critical flag: 1 means the 5 V rail sagged past
  # the SoC's threshold. thr is the latched get_throttled word.
  awk -F, '
    /^###|^#/ { next }
    { n++; if ($4 == 1) trips++; if ($7 != "0x0" && $7 != "") thr[$7]++ ;
      if ($5+0 > maxt) maxt = $5+0; if ($6+0 > 0 && ($6+0 < minf || minf == 0)) minf = $6+0 }
    END {
      printf "  samples %d   undervoltage trips %d\n", n, trips+0
      printf "  max temp %.1f C   min cpu freq %d MHz\n", maxt, minf
      if (length(thr) == 0) printf "  throttled word: 0x0 throughout\n"
      else for (k in thr) printf "  throttled word: %s seen %d times\n", k, thr[k]
    }' "$power"
fi

printf '\n== READING IT ==\n'
cat <<'TXT'
  undervoltage trips > 0  -> the 5 V rail sagged. Pack or UBEC.
  trips 0 but walk died   -> the rail collapsed faster than the SoC could
                             latch a bit. A clean cut reads 0x0; do not read
                             that as "power was fine."
  both logs stop together -> the Pi lost power.
  walk stops, power runs  -> the walk crashed but the Pi lived. Read the
                             traceback in the terminal; it is a software fault.
TXT
