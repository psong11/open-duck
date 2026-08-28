#!/usr/bin/env python
"""Gentlest possible end-to-end check that the Pi can actually DRIVE a servo.

Design constraints, in order of importance:
  * touches exactly ONE joint: head_yaw. It carries no weight, has no linkage
    to the body, and a few degrees of rotation cannot reach anything.
  * lowers that motor's P gain from 32 to 6 before enabling torque, so even a
    fully blocked joint is pushed feebly.
  * moves +/- 4 degrees. Not a sweep. Not a return to "zero".
  * returns to the exact starting position, restores P, and disables torque in
    a finally block, so an exception or Ctrl-C still leaves the motor limp.

Also reports what each joint's offset would be if the duck's current standing
pose is its intended zero -- computed purely from reads.

    python scripts/soft_check.py --port /dev/ttyACM0            # read-only
    python scripts/soft_check.py --port /dev/ttyACM0 --move     # + motion test
"""
import argparse
import math
import time

from pypot.feetech import FeetechSTS3215IO

JOINTS = {
    10: "right_hip_yaw", 11: "right_hip_roll", 12: "right_hip_pitch",
    13: "right_knee", 14: "right_ankle",
    20: "left_hip_yaw", 21: "left_hip_roll", 22: "left_hip_pitch",
    23: "left_knee", 24: "left_ankle",
    30: "neck_pitch", 31: "head_pitch", 32: "head_yaw", 33: "head_roll",
}
TEST_ID, TEST_NAME = 32, "head_yaw"
SAFE_P, NORMAL_P, STEP_DEG = 6, 32, 4.0

ap = argparse.ArgumentParser()
ap.add_argument("--port", required=True)
ap.add_argument("--move", action="store_true", help="also run the motion test")
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)
read = lambda mid, reg: getattr(io, f"get_{reg}")([mid])[0]

# ---------------------------------------------------------------- part 1
print("=== standing pose, and the offsets it implies ===")
print(f"{'id':<4}{'joint':<17}{'now (deg)':>11}{'offset (rad)':>14}{'torque':>9}")
print("-" * 55)
poses = {}
for mid, name in JOINTS.items():
    try:
        pos = read(mid, "present_position")
        tq = io.is_torque_enabled([mid])[0]
    except Exception:
        print(f"{mid:<4}{name:<17}{'NOT RESPONDING':>34}")
        continue
    poses[name] = pos
    print(f"{mid:<4}{name:<17}{pos:>11.1f}{math.radians(pos):>14.4f}"
          f"{('ON' if tq else 'off'):>9}")
print("-" * 55)
print("If this pose is the intended zero, the rad column is duck_config.json's")
print("joints_offset. Confirm against find_soft_offsets.py before trusting it.")

if not a.move:
    print("\nRead-only. Nothing was commanded. Re-run with --move for the motion test.")
    raise SystemExit(0)

# ---------------------------------------------------------------- part 2
print(f"\n=== motion test: {TEST_NAME} only, P={SAFE_P}, +/-{STEP_DEG:.0f} deg ===")
start = read(TEST_ID, "present_position")
old_p = read(TEST_ID, "P_coefficient")
print(f"start position {start:.1f} deg   (P was {old_p})")

moved = []
try:
    io.set_P_coefficient({TEST_ID: SAFE_P})
    io.enable_torque([TEST_ID])
    time.sleep(0.2)

    for label, target in (("+", start + STEP_DEG),
                          ("-", start - STEP_DEG),
                          ("home", start)):
        io.set_goal_position({TEST_ID: target})
        time.sleep(0.8)
        got = read(TEST_ID, "present_position")
        load = read(TEST_ID, "present_load")
        print(f"  {label:<5} commanded {target:7.1f} -> reached {got:7.1f} "
              f"(err {abs(got - target):4.1f}, load {load})")
        moved.append(abs(got - target))
finally:
    io.disable_torque([TEST_ID])
    io.set_P_coefficient({TEST_ID: old_p if old_p else NORMAL_P})
    time.sleep(0.1)
    still_on = io.is_torque_enabled([TEST_ID])[0]
    end = read(TEST_ID, "present_position")
    print(f"\ntorque now: {'ON  <-- PROBLEM' if still_on else 'off'}   "
          f"P restored to {read(TEST_ID, 'P_coefficient')}")
    print(f"ended at {end:.1f} deg (started {start:.1f}, drift {abs(end-start):.1f})")

ok = moved and max(moved) < 3.0
print("\n" + ("PASS — the Pi can command a servo and it obeys."
              if ok else "CHECK — the joint did not track its target closely."))
