#!/usr/bin/env python
"""Park every servo's goal_position at where it already is.

An uncommanded STS3215 reports goal_position -180.0 (raw 0). If anything
enables torque before writing goals -- and turn_on() in the runtime sets gains
a full second before it sets positions -- all fourteen joints lurch toward
-180 at once, on an assembled robot.

Writing a goal while torque is OFF moves nothing. It just makes the first
moment of torque a no-op instead of a lunge.

    python scripts/park_goals.py --port /dev/ttyACM0
"""
import argparse
import time

from pypot.feetech import FeetechSTS3215IO

JOINTS = {10: "right_hip_yaw", 11: "right_hip_roll", 12: "right_hip_pitch",
          13: "right_knee", 14: "right_ankle", 20: "left_hip_yaw",
          21: "left_hip_roll", 22: "left_hip_pitch", 23: "left_knee",
          24: "left_ankle", 30: "neck_pitch", 31: "head_pitch",
          32: "head_yaw", 33: "head_roll"}

ap = argparse.ArgumentParser()
ap.add_argument("--port", required=True)
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)

live = [m for m in JOINTS if io.is_torque_enabled([m])[0]]
if live:
    raise SystemExit(f"torque is ON for {live} — refusing. Release torque first.")

print(f"{'id':<4}{'joint':<17}{'position':>10}{'goal was':>11}{'goal now':>11}")
print("-" * 53)
for mid, name in JOINTS.items():
    pos = io.get_present_position([mid])[0]
    was = io.get_goal_position([mid])[0]
    io.set_goal_position({mid: pos})
    time.sleep(0.02)
    now = io.get_goal_position([mid])[0]
    flag = "" if abs(now - pos) < 2 else "  <-- did not take"
    print(f"{mid:<4}{name:<17}{pos:>10.1f}{was:>11.1f}{now:>11.1f}{flag}")
print("-" * 53)
print("Torque was off throughout, so nothing moved. The first moment of torque")
print("is now a no-op instead of a lunge toward -180.")
