#!/usr/bin/env python
"""Write the STS3215 offset register (addr 31) — for a horn installed out of true.

The correction is applied inside the servo's firmware and lives in EEPROM, so
it persists across power cycles and costs the control loop nothing at runtime.

    python scripts/write_offset.py --port /dev/ttyACM0 --set 12:180 --set 22:180
    python scripts/write_offset.py --port /dev/ttyACM0 --restore 12 --restore 22

Only accepts 0..180. pypot maps this register linearly like a Dynamixel, but
Feetech encodes it as sign-magnitude around raw 2048, so the negative half
folds: writing -170 yields -10, not -170. The +-180 wrap reaches every angle
from the positive half anyway, so the broken half is simply refused.
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
ap.add_argument("--set", action="append", default=[], metavar="ID:DEG")
ap.add_argument("--restore", action="append", type=int, default=[], metavar="ID")
a = ap.parse_args()

writes = []
for spec in a.set:
    i, d = spec.split(":")
    i, d = int(i), float(d)
    if not (0.0 <= d <= 180.0):
        raise SystemExit(f"refusing {d}: only 0..180 is trustworthy on this "
                         f"register (see the docstring). Use the wrap instead.")
    writes.append((i, d))
for i in a.restore:
    writes.append((i, None))          # None => raw 0, i.e. no correction

port = a.port
fresh = lambda: (time.sleep(0.35), FeetechSTS3215IO(port, timeout=0.05))[1]

io = fresh()
for mid, _ in writes:
    if io.is_torque_enabled([mid])[0]:
        raise SystemExit(f"id {mid} has torque ON — refusing to write EEPROM.")
print("torque confirmed off on every target motor.\n")

for mid, deg in writes:
    name = JOINTS.get(mid, f"id{mid}")
    io = fresh()
    before_off = io.get_offset([mid])[0]
    before_pos = io.get_present_position([mid])[0]
    target = -180.0 if deg is None else deg          # -180.0 reads back as raw 0

    print(f"=== {name} (id {mid}) ===")
    print(f"  before : offset={before_off:<8.1f} position={before_pos:+8.2f}")

    io.set_lock({mid: 0})
    io.set_offset({mid: target})
    io.set_lock({mid: 1})
    time.sleep(0.35)

    v = fresh()                                       # fresh: proves EEPROM
    after_off = v.get_offset([mid])[0]
    after_pos = v.get_present_position([mid])[0]
    shift = after_pos - before_pos
    if shift > 180:
        shift -= 360
    elif shift < -180:
        shift += 360

    ok = abs(after_off - target) < 1.0
    print(f"  after  : offset={after_off:<8.1f} position={after_pos:+8.2f}"
          f"   shift {shift:+.1f} deg")
    print(f"  verify : {'OK — landed in EEPROM' if ok else '*** WRITE DID NOT LAND ***'}\n")
