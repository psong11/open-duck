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
import os
import pathlib
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~"))
from duck_flightlog import FlightLog  # noqa: E402

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
ap.add_argument("--teeth", type=int, default=None,
                help="splines on the horn; count them and pass it to get teeth instead of degrees")
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

# Record the whole sweep, not just the extremes. A min/max pair cannot tell a
# firm push into a hard stop from a tentative wiggle that stopped early, and
# everything downstream rests on which of those happened.
fl = FlightLog(
    "~/walklogs/range-%s.csv" % time.strftime("%Y%m%d-%H%M%S"),
    fields=tuple("id%d" % m for m in a.ids),
).start()
fl.mark("sweep ids " + ",".join(str(m) for m in a.ids))
print("trace -> %s" % fl.path)

lo = {m: None for m in a.ids}
hi = {m: None for m in a.ids}
first = {m: None for m in a.ids}
dwell_lo = {m: 0 for m in a.ids}
dwell_hi = {m: 0 for m in a.ids}
n = 0
print("\nSweep each joint slowly to BOTH of its stops. %.0f seconds.\n" % a.secs)

t0 = time.time()
try:
    while time.time() - t0 < a.secs:
        seen = {}
        for m in a.ids:
            try:
                p = io.get_present_position([m])[0]
            except Exception:
                continue
            seen["id%d" % m] = round(p, 2)
            if first[m] is None:
                first[m] = p
            lo[m] = p if lo[m] is None else min(lo[m], p)
            hi[m] = p if hi[m] is None else max(hi[m], p)
            # Time spent parked against an extreme. A real stop gets leaned on;
            # a turnaround in mid-air does not.
            if abs(p - lo[m]) < 1.0:
                dwell_lo[m] += 1
            if abs(p - hi[m]) < 1.0:
                dwell_hi[m] += 1
        n += 1
        fl.sample(n, **seen)
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
finally:
    fl.close("swept")

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

# An extreme that never moved off the starting position is not a measurement.
# The sweep simply never went that way, and reporting it as a limit would
# invent a wall out of where the leg happened to be resting.
unmeasured = []
for m in a.ids:
    if first[m] is None:
        continue
    for side, val, dwell in (("max", hi[m], dwell_hi[m]), ("min", lo[m], dwell_lo[m])):
        # The encoder resolves about 0.09 deg. A joint resting against its stop
        # STARTS at that stop, so "extreme == first sample" is the normal case,
        # not a missed sweep -- pressing on it yields a few tenths of elastic
        # give and then nothing. Only a value that never moved by even a few
        # counts means the sweep genuinely never went that way.
        if abs(val - first[m]) < 0.3:
            unmeasured.append((m, side, val))
        elif dwell < 10 and abs(val - first[m]) > 5.0:
            # Brief contact far from where it started: possibly a turnaround in
            # mid-air rather than a stop. Near the start it is just the resting
            # position, which needs no warning.
            print("  note: %s %s (%.1f) was touched briefly, not leaned on -- "
                  "it may not be the real stop." % (NAMES[m], side, val))

if unmeasured:
    print("\n" + "!" * 74)
    print("INCOMPLETE SWEEP -- these ends were never explored:")
    for m, side, val in unmeasured:
        print("  %-18s %s = %.1f is just where it started. You did not move it that way."
              % (NAMES[m], side, val))
    print("Re-sweep and push BOTH directions to a firm stop before trusting any")
    print("verdict above. Make sure nothing the duck is resting on is in the way.")
    print("!" * 74)

# Reseating the horn slides this whole window along the reported axis. Which
# way to turn it depends on bracket handedness, which this script cannot see --
# but how far, and which way the NUMBERS must move, it can state exactly.
todo = []
for m in a.ids:
    if lo[m] is None:
        continue
    want = targets[m]
    if want > hi[m]:
        need, direction = want - hi[m], "UP (more positive)"
    elif want < lo[m]:
        need, direction = lo[m] - want, "DOWN (more negative)"
    else:
        continue
    todo.append((m, need, direction))

if todo:
    print("\nTo fix, the reported range must move:")
    for m, need, direction in todo:
        margin = need + 15.0  # bare-pass puts the target on the stop; leave room to walk
        line = "  %-18s %s by at least %.1f deg  (aim for ~%.0f, so it is not sitting on the stop)" % (
            NAMES[m], direction, need, margin)
        if a.teeth:
            per = 360.0 / a.teeth
            line += "\n  %-18s = %.1f deg/tooth -> %d teeth minimum, %d preferred" % (
                "", per, math.ceil(need / per), max(1, round(margin / per)))
        print(line)
    if not a.teeth:
        print("\n  Count the splines on the horn and re-run with --teeth N for a tooth count.")
    print("""
  Which way to turn the horn is bracket handedness, which this cannot see.
  Resolve it in one trial: move ONE tooth, re-run this, and read whether the
  numbers went toward the target or away. That single test gives you the
  direction AND confirms the degrees-per-tooth.""")

print("\nTorque is still off. These joints are limp.")
