#!/usr/bin/env bash
# Run the walk with the rail watcher already going. One command, one touch.
#
# The watcher has to be running BEFORE the walk starts or the interesting part
# is missed, and it has to be stopped after or its log has no END marker and
# every run looks like a death. Forgetting either is a wasted battery, so this
# owns both ends and the walk stays in the foreground where Ctrl-C reaches it.
#
#   ./run_walk.sh                 # no controller
#   ./run_walk.sh --commands      # gamepad; anything here is passed through
#
# Note well: Ctrl-C is not an emergency stop. It reaches this script only if
# the Pi is still alive, and in a brownout it is not. The power switch is the
# only stop that always works. Keep a hand on it.
set -uo pipefail

PY="${PY:-$HOME/miniforge3/envs/duck/bin/python}"
ONNX="${ONNX:-$HOME/BEST_WALK_ONNX_2.onnx}"
WALK_DIR="$HOME/Open_Duck_Mini_Runtime/scripts"
WALK="$WALK_DIR/v2_rl_walk_mujoco.py"
LABEL="${LABEL:-walk}"

[ -x "$PY" ]    || { echo "no python at $PY" >&2; exit 1; }
[ -f "$ONNX" ]  || { echo "no policy at $ONNX" >&2; exit 1; }
[ -f "$WALK" ]  || { echo "no walk script at $WALK" >&2; exit 1; }
# The runtime loads ./polynomial_coefficients.pkl by a RELATIVE path, so it
# only works from its own directory. Running it from anywhere else gets you
# through torque-on and the init pose before it dies on a missing file.
[ -f "$WALK_DIR/polynomial_coefficients.pkl" ] || {
  echo "no polynomial_coefficients.pkl in $WALK_DIR" >&2; exit 1; }
cd "$WALK_DIR" || exit 1

echo "== pack voltage before =="
"$PY" - <<'PY'
from pypot.feetech import FeetechSTS3215IO
io = FeetechSTS3215IO("/dev/ttyACM0", baudrate=1000000, use_sync_read=True)
v = io.get_present_voltage([10, 20, 30])
print("  %.1f V" % (sorted(v)[len(v) // 2] / 10.0))
PY

"$PY" "$HOME/powerwatch.py" "$LABEL" &
WATCHER=$!
# Kill by pid. Matching on the name would also match this script's own command
# line and take down the shell with it -- that has bitten us twice.
cleanup() {
  kill -TERM "$WATCHER" 2>/dev/null
  wait "$WATCHER" 2>/dev/null
}
trap cleanup EXIT INT TERM

sleep 1  # let the watcher land a few baseline samples before torque comes on

echo "== walking =="
# cwd is $WALK_DIR, set above, because of that relative path
"$PY" -u "$WALK" --onnx_model_path "$ONNX" "$@"
rc=$?

cleanup
trap - EXIT INT TERM

echo
echo "== pack voltage after =="
"$PY" - <<'PY' || echo "  bus did not answer -- servos may be unpowered"
from pypot.feetech import FeetechSTS3215IO
io = FeetechSTS3215IO("/dev/ttyACM0", baudrate=1000000, use_sync_read=True)
v = io.get_present_voltage([10, 20, 30])
print("  %.1f V" % (sorted(v)[len(v) // 2] / 10.0))
PY

echo
echo "walk exited rc=$rc. From the Mac: scripts/read_walklog.sh"
exit $rc
