#!/usr/bin/env python
"""Measure a joint's real mechanical range by hand, with the motors switched off.

Why: during the crouch, both hip pitches move one to three degrees and then
stop dead while the commanded position keeps sweeping away from them. Error
climbs linearly, proportional torque climbs with it, current climbs with that,
and the pack sags — so the voltage collapse is a *symptom* of two servos
grinding against something, not the cause of anything.

Torque starvation and a hard stop look identical in a voltage log. They differ
in one way: a starved joint settles wherever torque balances load, which moves
with the pose and the pack, while a blocked joint stops at the same absolute
angle every time. Ours stopped at 16.3 and -19.5 on two different days from two
different starting positions, which is the signature of a wall.

This finds the wall. Torque is released, you sweep the joint by hand, and it
records the extremes — so the answer comes from the linkage itself rather than
from something the firmware believes.

    python find_range.py                       # hip pitches, 30 s
    python find_range.py --ids 12 --secs 20
    python find_range.py --ids 13 23           # a pair that works, for contrast

The legs go limp the moment this starts. Support them.
"""
import argparse
import json
import math
import pathlib
import sys
import time

from pypot.feetech import FeetechSTS3215IO

NAMES = {10: "right_hip_yaw", 11: "right_hip_roll", 12: "right_hip_pitch",
         13: "right_knee", 14: "right_ankle", 20: "left_hip_yaw",
         21: "left_hip_roll", 22: "left_hip_pitch", 23: "left_knee",
         24: "left_ankle", 30: "neck_pitch", 31: "head_pitch",
         32: "head_yaw", 33: "head_roll"}

# radians, from the runtime's HWI.init_pos
INIT = {"right_hip_pitch": 0.635, "left_hip_pitch": -0.63,
        "right_knee": 1.379, "left_knee": 1.368,
        "right_ankle": -0.796, "left_ankle": -0.784,
        "right_hip_yaw": -0.003, "left_hip_yaw": 0.002,
        "right_hip_roll": -0.065, "left_hip_roll": 0.053,
        "neck_pitch": 0.0, "head_pitch": 0.0, "head_yaw": 0.0, "head_roll": 0.0}

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="/dev/ttyACM0")
ap.add_argument("--ids", type=int, nargs="+", default=[12, 22])
ap.add_argument("--secs", type=float, default=30.0)
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)
cfg = json.loads(pathlib.Path(a.config).read_text())
offsets = cfg["joints_offsets" if "joints_offsets" in cfg else "joints_offset"]

targets = {}
for mid in a.ids:
    name = NAMES[mid]
    targets[mid] = math.degrees(INIT.get(name, 0.0)) + math.degrees(offsets.get(name, 0.0))

print("Releasing torque on: " + ", ".join("%s (%d)" % (NAMES[m], m) for m in a.ids))
print("The legs will go limp. Support them.")
if not input("Ready? (y/N) ").lower().startswith("y"):
    raise SystemExit("aborted; nothing changed")

io.disable_torque(a.ids)
time.sleep(0.3)

lo = {m: None for m in a.ids}
hi = {m: None for m in a.ids}
print("\nSweep each joint slowly to BOTH of its stops. %.0f seconds.\n" % a.secs)

t0 = time.time()
try:
    while time.time() - t0 < a.secs:
        for m in a.ids:
            try:
                p = io.get_present_position([m])[0]
            except Exception:
                continue
            lo[m] = p if lo[m] is None else min(lo[m], p)
            hi[m] = p if hi[m] is None else max(hi[m], p)
        left = a.secs - (time.time() - t0)
        cells = "  ".join(
            "%s %7.1f .. %6.1f" % (m, lo[m] if lo[m] is not None else 0,
                                   hi[m] if hi[m] is not None else 0)
            for m in a.ids
        )
        print("\r%4.0fs left   %s" % (left, cells), end="", flush=True)
        time.sleep(0.05)
except KeyboardInterrupt:
    print()

print("\n\n%-18s %9s %9s %9s %9s   %s" % ("joint", "min", "max", "span", "needs", "verdict"))
print("-" * 74)
for m in a.ids:
    if lo[m] is None:
        print("%-18s   no readings" % NAMES[m])
        continue
    want = targets[m]
    inside = lo[m] - 1.0 <= want <= hi[m] + 1.0
    verdict = "reachable" if inside else "OUT OF RANGE by %.1f deg" % (
        want - hi[m] if want > hi[m] else lo[m] - want
    )
    print("%-18s %9.1f %9.1f %9.1f %9.1f   %s"
          % (NAMES[m], lo[m], hi[m], hi[m] - lo[m], want, verdict))
print("-" * 74)
print("'needs' is where the runtime's init pose commands this joint, offsets applied.")
print("Anything OUT OF RANGE cannot be reached at any gain, on any battery.")
print("\nTorque is still off. These joints are limp.")
