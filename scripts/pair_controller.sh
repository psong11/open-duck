#!/usr/bin/env bash
# Pair the gamepad, with a real pairing agent running.
#
# Two things make this fiddly and both bit us:
#   1. BlueZ only treats a device as "available" while a scan is LIVE, and it
#      evicts unpaired devices it stops hearing. Discovery and pairing must
#      happen in one continuous window.
#   2. Bonding needs a registered pairing agent. bluetoothctl fed from a pipe
#      fails to register one ("Failed to register agent object"), which
#      surfaces as org.bluez.Error.AuthenticationFailed -- the device connects
#      but never bonds, so the HID profile never attaches and no
#      /dev/input/js* appears. bt-agent is a standalone agent that works.
#
# Controller in pairing mode (fast blink), held AGAINST the duck's head --
# the Pi Zero 2W shares one antenna between wifi and bluetooth.
#
#   ./pair_controller.sh [MAC]
set -u
MAC="${1:-68:16:51:71:8A:6F}"

cleanup() { sudo pkill -f "bt-agent" 2>/dev/null; kill "${SCAN:-}" 2>/dev/null; }
trap cleanup EXIT

sudo pkill -f "bt-agent" 2>/dev/null; sleep 1
sudo bt-agent -c NoInputNoOutput >/dev/null 2>&1 &
sleep 1
pgrep -x bt-agent >/dev/null && echo "pairing agent: running" || echo "pairing agent: FAILED TO START"

# Forget any half-bonded state; a failed pair leaves residue that blocks retries.
bluetoothctl remove "$MAC" >/dev/null 2>&1

echo "scanning for $MAC (up to 90s)..."
bluetoothctl --timeout 90 scan on >/dev/null 2>&1 &
SCAN=$!

for i in $(seq 1 28); do
  if bluetoothctl info "$MAC" 2>/dev/null | grep -q "Name:"; then
    echo "seen after ~$((i * 3))s — pairing"
    echo "  pair   : $(timeout 30 bluetoothctl pair "$MAC" 2>&1 | tail -1)"
    sleep 2
    echo "  trust  : $(timeout 10 bluetoothctl trust "$MAC" 2>&1 | tail -1)"
    sleep 1
    echo "  connect: $(timeout 30 bluetoothctl connect "$MAC" 2>&1 | tail -1)"
    sleep 5
    echo
    bluetoothctl info "$MAC" 2>&1 | grep -E "Name|Paired|Bonded|Trusted|Connected" | sed 's/^/  /'
    echo
    if ls /dev/input/js* >/dev/null 2>&1; then
      echo "SUCCESS — joystick present: $(ls /dev/input/js*)"
      echo "next:  ~/miniforge3/envs/duck/bin/python ~/probe_gamepad.py"
    else
      echo "Connected but no /dev/input/js* — bonding did not complete."
      echo "Put it back in pairing mode (fast blink) and run this again."
    fi
    exit 0
  fi
  sleep 3
done
echo "never appeared. Re-enter pairing mode and hold it against the duck's head."
