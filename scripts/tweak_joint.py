#!/usr/bin/env python
"""Set ONE joint's offset, on your terms. The targeted alternative to
find_soft_offsets.py's fourteen-joint gauntlet.

Leaves every other joint alone. Commands no motion at all -- it releases torque
on the one joint you name, waits while you position it by hand, and records
where you put it.

The offset for a joint is simply its position when the robot is posed at the
model's zero, because an uncorrected servo's zero reads 0.

    python scripts/tweak_joint.py --port /dev/ttyACM0 --show
    python scripts/tweak_joint.py --port /dev/ttyACM0 --joint left_knee
    python scripts/tweak_joint.py --port /dev/ttyACM0 --joint left_knee --reset
"""
import argparse
import json
import math
import pathlib

from pypot.feetech import FeetechSTS3215IO

JOINTS = {"right_hip_yaw": 10, "right_hip_roll": 11, "right_hip_pitch": 12,
          "right_knee": 13, "right_ankle": 14, "left_hip_yaw": 20,
          "left_hip_roll": 21, "left_hip_pitch": 22, "left_knee": 23,
          "left_ankle": 24, "neck_pitch": 30, "head_pitch": 31,
          "head_yaw": 32, "head_roll": 33}

ap = argparse.ArgumentParser()
ap.add_argument("--port", required=True)
ap.add_argument("--joint", choices=sorted(JOINTS))
ap.add_argument("--reset", action="store_true", help="set this joint's offset to 0")
ap.add_argument("--show", action="store_true", help="print all offsets and exit")
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

cfg_path = pathlib.Path(a.config)
cfg = json.loads(cfg_path.read_text())
key = "joints_offsets" if "joints_offsets" in cfg else "joints_offset"
io = FeetechSTS3215IO(a.port, timeout=0.05)


def show():
    print(f"{'joint':<17}{'offset (rad)':>13}{'= deg':>8}{'position now':>14}")
    print("-" * 52)
    for name, mid in JOINTS.items():
        o = cfg[key].get(name, 0.0)
        pos = io.get_present_position([mid])[0]
        mark = "" if abs(o) < 1e-9 else "  <- set"
        print(f"{name:<17}{o:>13.4f}{math.degrees(o):>8.2f}{pos:>14.2f}{mark}")
    print("-" * 52)


if a.show or not a.joint:
    show()
    raise SystemExit(0)

name, mid = a.joint, JOINTS[a.joint]

if a.reset:
    cfg[key][name] = 0.0
    cfg_path.write_text(json.dumps(cfg, indent=4))
    print(f"{name}: offset reset to 0.0")
    raise SystemExit(0)

print(f"=== {name} (id {mid}) ===")
print(f"current offset : {cfg[key].get(name, 0.0):.4f} rad")
print(f"position now   : {io.get_present_position([mid])[0]:.2f} deg")
print()
io.disable_torque([mid])
print(f"{name} is now LIMP. Every other joint is untouched.")
input("Move it to where zero should be, then press Enter (Ctrl-C to abort)... ")

pos = io.get_present_position([mid])[0]
rad = math.radians(pos)
print(f"\n  measured {pos:+.2f} deg  ->  offset {rad:+.4f} rad")
if abs(pos) < 2.0:
    print("  (that is essentially zero — this joint was assembled true, "
          "which is the ideal result)")

if input("\nWrite this offset? (y/N) ").lower().startswith("y"):
    cfg[key][name] = round(rad, 4)
    cfg_path.write_text(json.dumps(cfg, indent=4))
    print(f"wrote {name} = {rad:.4f} rad to {cfg_path}")
else:
    print("not written; offset unchanged")

print(f"\n{name} is still limp. Torque was never re-enabled by this script.")
