#!/usr/bin/env python
"""Crouch into the runtime's init pose slowly, logging the pack the whole way.

turn_on() commands all fourteen servos to the init pose in a single write and
then waits a second. That pose is a crouch -- knees bend about 78 degrees,
hips 36, ankles 45 -- so six leg joints slew hard at the same instant and then
hold the robot's weight there. That single write is the last thing the Pi did
before it died at 4.8 seconds, and a gain ramp against zero position error
sailed to full stiffness without noticing anything, which points here.

This does the same move as a ramp instead of a step: interpolate from wherever
the joints are to the init pose over several seconds, at low gain, sampling the
pack at every increment and fsyncing as it goes. If the pack gives out, the
last durable line says how far into the move it got and what the voltage was
doing beforehand -- a sag curve rather than a silence.

    python slew_to_init.py --port /dev/ttyACM0                # 8 s, Kp 8
    python slew_to_init.py --port /dev/ttyACM0 --secs 20      # slower still
    python slew_to_init.py --port /dev/ttyACM0 --groups       # one leg at a time
    python slew_to_init.py --port /dev/ttyACM0 --release      # let go now

Support the duck. It ends up standing in a crouch with torque ON, and it will
fall if you let go. Keep a hand on the power switch: Ctrl-C only works while
the Pi is alive.
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

from pypot.feetech import FeetechSTS3215IO  # noqa: E402

# Radians, straight out of rustypot_position_hwi.HWI.init_pos.
INIT_POS = {
    "left_hip_yaw": 0.002, "left_hip_roll": 0.053, "left_hip_pitch": -0.63,
    "left_knee": 1.368, "left_ankle": -0.784,
    "neck_pitch": 0.0, "head_pitch": 0.0, "head_yaw": 0.0, "head_roll": 0.0,
    "right_hip_yaw": -0.003, "right_hip_roll": -0.065, "right_hip_pitch": 0.635,
    "right_knee": 1.379, "right_ankle": -0.796,
}
JOINTS = {"right_hip_yaw": 10, "right_hip_roll": 11, "right_hip_pitch": 12,
          "right_knee": 13, "right_ankle": 14, "left_hip_yaw": 20,
          "left_hip_roll": 21, "left_hip_pitch": 22, "left_knee": 23,
          "left_ankle": 24, "neck_pitch": 30, "head_pitch": 31,
          "head_yaw": 32, "head_roll": 33}
GROUPS = [
    ("right leg", ["right_hip_yaw", "right_hip_roll", "right_hip_pitch",
                   "right_knee", "right_ankle"]),
    ("left leg", ["left_hip_yaw", "left_hip_roll", "left_hip_pitch",
                  "left_knee", "left_ankle"]),
    ("head", ["neck_pitch", "head_pitch", "head_yaw", "head_roll"]),
]

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="/dev/ttyACM0")
ap.add_argument("--kp", type=int, default=8, help="runtime uses 32")
ap.add_argument("--secs", type=float, default=8.0, help="duration of the move")
ap.add_argument("--hz", type=float, default=20.0)
ap.add_argument("--groups", action="store_true", help="one group at a time")
ap.add_argument("--release", action="store_true")
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)
ids = list(JOINTS.values())

if a.release:
    io.disable_torque(ids)
    print("torque released on all 14 - the duck is limp. Support it.")
    raise SystemExit(0)

cfg = json.loads(pathlib.Path(a.config).read_text())
offsets = cfg["joints_offsets" if "joints_offsets" in cfg else "joints_offset"]


def pack_v():
    try:
        v = io.get_present_voltage([10, 20, 30])
        return sorted(v)[len(v) // 2] / 10.0
    except Exception:
        return None


# pypot speaks degrees; init_pos and the config offsets are both radians.
start_deg, target_deg = {}, {}
for name, mid in JOINTS.items():
    start_deg[name] = io.get_present_position([mid])[0]
    target_deg[name] = math.degrees(INIT_POS[name]) + math.degrees(offsets.get(name, 0.0))

print("%-17s%9s%9s%9s" % ("joint", "now", "target", "travel"))
print("-" * 44)
for name in JOINTS:
    print("%-17s%9.1f%9.1f%9.1f"
          % (name, start_deg[name], target_deg[name],
             abs(target_deg[name] - start_deg[name])))
print("-" * 44)
biggest = max(abs(target_deg[n] - start_deg[n]) for n in JOINTS)
print("largest single movement: %.0f degrees" % biggest)
print("pack at rest: %s V   Kp %d   %.1fs   %s"
      % (pack_v(), a.kp, a.secs, "grouped" if a.groups else "all at once"))
if not input("\nSupport the duck. Proceed? (y/N) ").lower().startswith("y"):
    raise SystemExit("aborted; nothing moved")

fl = FlightLog(
    "~/walklogs/slew-%s.csv" % time.strftime("%Y%m%d-%H%M%S"),
    fields=("group", "frac", "v", "v_min", "max_travel_deg"),
).start()
fl.mark("kp=%d secs=%.1f hz=%.1f groups=%s biggest=%.0fdeg"
        % (a.kp, a.secs, a.hz, a.groups, biggest))
print("log -> %s" % fl.path)

# Park before engaging, so switching torque on is a no-op rather than a lurch.
for name, mid in JOINTS.items():
    io.set_goal_position({mid: start_deg[name]})
io.set_P_coefficient({mid: a.kp for mid in ids})
io.enable_torque(ids)
time.sleep(0.3)
print("torque on at the present pose. Beginning the move.")

plan = GROUPS if a.groups else [("all", list(JOINTS.keys()))]
reason = "completed"
n = 0
try:
    for gname, members in plan:
        secs = a.secs / (len(plan) if a.groups else 1)
        steps = max(1, int(secs * a.hz))
        travel = max(abs(target_deg[m] - start_deg[m]) for m in members)
        fl.mark("group %s travel=%.0fdeg steps=%d" % (gname, travel, steps))
        print("  %-10s travel %5.0f deg" % (gname, travel), flush=True)
        vmin = None
        for s in range(1, steps + 1):
            f = s / steps
            for m in members:
                mid = JOINTS[m]
                pos = start_deg[m] + (target_deg[m] - start_deg[m]) * f
                io.set_goal_position({mid: pos})
            v = pack_v()
            if v is not None and (vmin is None or v < vmin):
                vmin = v
            n += 1
            fl.sample(n, group=gname, frac=round(f, 3), v=v, v_min=vmin,
                      max_travel_deg=round(travel, 1))
            time.sleep(max(0.0, 1.0 / a.hz))
        print("  %-10s done   min %sV" % (gname, vmin), flush=True)

    time.sleep(0.5)
    print("\nreached init pose. pack: %s V" % pack_v())
    print("%-17s%9s%9s%8s" % ("joint", "target", "reached", "err"))
    print("-" * 43)
    for name, mid in JOINTS.items():
        got = io.get_present_position([mid])[0]
        print("%-17s%9.1f%9.1f%8.1f"
              % (name, target_deg[name], got, abs(got - target_deg[name])))

except KeyboardInterrupt:
    reason = "KeyboardInterrupt"
except BaseException as e:
    reason = "%s: %s" % (type(e).__name__, e)
    raise
finally:
    fl.close(reason)
    print("\nreason: %s   torque is still ON and holding." % reason)
    print("Release with:  python slew_to_init.py --release")
