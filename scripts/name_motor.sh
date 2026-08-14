#!/usr/bin/env bash
# Assign a duck joint identity to the ONE motor currently on the bus.
#
#   ./scripts/name_motor.sh right_hip_yaw
#   ./scripts/name_motor.sh --list
#
# Wraps upstream's configure_motor.py so you type a joint name instead of
# remembering a number, and so the port isn't retyped 14 times.
#
# ONE motor on the bus at a time — unconfigured motors all answer to id 1.

set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${DUCK_PORT:-/dev/cu.usbmodem5B901489761}"

# Joint -> id, per docs/configure_motors.md upstream.
ids=(
  "right_hip_yaw:10" "right_hip_roll:11" "right_hip_pitch:12"
  "right_knee:13"    "right_ankle:14"
  "left_hip_yaw:20"  "left_hip_roll:21"  "left_hip_pitch:22"
  "left_knee:23"     "left_ankle:24"
  "neck_pitch:30"    "head_pitch:31"     "head_yaw:32" "head_roll:33"
)

if [[ "${1:-}" == "--list" || $# -ne 1 ]]; then
  echo "Joint identities (14 total):"
  for e in "${ids[@]}"; do printf "  %-16s %s\n" "${e%%:*}" "${e##*:}"; done
  echo
  echo "usage: $0 <joint_name>     port: $PORT"
  [[ "${1:-}" == "--list" ]] && exit 0 || exit 1
fi

want="$1"; id=""
for e in "${ids[@]}"; do [[ "${e%%:*}" == "$want" ]] && id="${e##*:}"; done

if [[ -z "$id" ]]; then
  echo "unknown joint '$want'. run '$0 --list' to see valid names." >&2
  exit 1
fi

echo "==> $want  ->  id $id   (port $PORT)"
.venv/bin/python vendor/Open_Duck_Mini_Runtime/scripts/configure_motor.py \
    --id "$id" --port "$PORT"

# Verify over a fresh connection. configure_motor.py's own readback happens in
# the same session and has been observed to pass while a write was silently
# dropped (id 30, max_acceleration stuck at 50).
echo
echo "--- verifying (fresh connection) ---"
if ! .venv/bin/python scripts/verify_motor.py --id "$id" --port "$PORT"; then
  echo
  echo "!! NOT configured correctly. Re-run:  $0 $want"
  exit 1
fi

echo
echo "Motor is holding zero under torque."
echo "  1. install the horn now, while powered"
echo "  2. label it '$id' ($want)"
echo "  3. disconnect it, connect the next motor"
