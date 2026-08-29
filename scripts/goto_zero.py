#!/usr/bin/env python
"""Drive the duck to its zero pose, with duck_config.json's offsets applied.

Gentler than the runtime's turn_on(): it parks every goal at the joint's
present position BEFORE enabling torque, so the moment of engagement is a
no-op rather than a lurch, and it holds at a reduced P gain to keep current
draw down -- sustained torque on all 14 is what browned out the Pi.

    python scripts/goto_zero.py --port /dev/ttyACM0            # Kp 8
    python scripts/goto_zero.py --port /dev/ttyACM0 --kp 32    # full stiffness
    python scripts/goto_zero.py --port /dev/ttyACM0 --release  # let go, no motion
"""
import argparse
import json
import math
import pathlib
import time

from pypot.feetech import FeetechSTS3215IO

JOINTS = {"right_hip_yaw": 10, "right_hip_roll": 11, "right_hip_pitch": 12,
          "right_knee": 13, "right_ankle": 14, "left_hip_yaw": 20,
          "left_hip_roll": 21, "left_hip_pitch": 22, "left_knee": 23,
          "left_ankle": 24, "neck_pitch": 30, "head_pitch": 31,
          "head_yaw": 32, "head_roll": 33}

ap = argparse.ArgumentParser()
ap.add_argument("--port", required=True)
ap.add_argument("--kp", type=int, default=8)
ap.add_argument("--release", action="store_true")
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)
ids = list(JOINTS.values())

if a.release:
    io.disable_torque(ids)
    print("torque released on all 14 — the duck is limp. Support it.")
    raise SystemExit(0)

cfg = json.loads(pathlib.Path(a.config).read_text())
key = "joints_offsets" if "joints_offsets" in cfg else "joints_offset"
offsets = cfg[key]

print(f"{'joint':<17}{'now':>8}{'offset':>9}{'target':>9}{'travel':>9}")
print("-" * 52)
plan = {}
for name, mid in JOINTS.items():
    pos = io.get_present_position([mid])[0]
    off_deg = math.degrees(offsets.get(name, 0.0))
    target = 0.0 + off_deg
    plan[mid] = (name, pos, target)
    print(f"{name:<17}{pos:>8.1f}{off_deg:>9.2f}{target:>9.2f}{abs(target-pos):>9.1f}")
print("-" * 52)
biggest = max(abs(t - p) for _, p, t in plan.values())
print(f"largest single movement: {biggest:.0f} degrees")
print(f"holding gain: Kp={a.kp}  (runtime default is 32)")

if not input("\nHold the duck firmly. Proceed? (y/N) ").lower().startswith("y"):
    raise SystemExit("aborted; nothing moved")

# Park first: goal = present, so enabling torque cannot lurch.
for mid, (_, pos, _) in plan.items():
    io.set_goal_position({mid: pos})
io.set_P_coefficient({mid: a.kp for mid in ids})
io.enable_torque(ids)
time.sleep(0.4)
print("torque engaged at the current pose (no movement yet)")

io.set_goal_position({mid: t for mid, (_, _, t) in plan.items()})
time.sleep(2.5)

print(f"\n{'joint':<17}{'target':>9}{'reached':>10}{'err':>8}")
print("-" * 45)
for mid, (name, _, target) in plan.items():
    got = io.get_present_position([mid])[0]
    print(f"{name:<17}{target:>9.2f}{got:>10.2f}{abs(got-target):>8.2f}")
print("-" * 45)
print(f"pack: {io.get_present_voltage([10])[0] / 10:.1f} V   torque is ON and holding.")
print("Release with:  --release")
