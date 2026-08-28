#!/usr/bin/env python
"""Read-only pre-flight before find_soft_offsets.py.

That script's first act is to drive all 14 joints to zero at once. This one
answers, without moving anything: how far is each joint from zero, and will
the servo's own angle limits stop it before it gets there?

    python scripts/preflight_offsets.py --port /dev/ttyACM0
"""
import argparse
from pypot.feetech import FeetechSTS3215IO

JOINTS = {
    10: "right_hip_yaw", 11: "right_hip_roll", 12: "right_hip_pitch",
    13: "right_knee", 14: "right_ankle",
    20: "left_hip_yaw", 21: "left_hip_roll", 22: "left_hip_pitch",
    23: "left_knee", 24: "left_ankle",
    30: "neck_pitch", 31: "head_pitch", 32: "head_yaw", 33: "head_roll",
}

ap = argparse.ArgumentParser()
ap.add_argument("--port", required=True)
a = ap.parse_args()
io = FeetechSTS3215IO(a.port, timeout=0.05)


def g(mid, reg):
    try:
        return getattr(io, f"get_{reg}")([mid])[0]
    except Exception:
        return None


print(f"{'id':<4}{'joint':<17}{'now':>9}{'target':>8}{'travel':>9}"
      f"{'limits':>18}  verdict")
print("-" * 78)

big, unlimited = [], []
for mid, name in JOINTS.items():
    pos = g(mid, "present_position")
    if pos is None:
        print(f"{mid:<4}{name:<17}{'NOT RESPONDING':>44}")
        continue
    lo, hi = g(mid, "min_angle_limit"), g(mid, "max_angle_limit")
    travel = abs(pos - 0.0)

    # Limits equal (or both zero) means the servo is in free-turn mode: its
    # firmware will not stop it anywhere.
    limited = isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo != hi
    lim = f"[{lo:.0f}, {hi:.0f}]" if limited else "NONE (free turn)"
    if not limited:
        unlimited.append(name)

    verdict = "ok"
    if travel > 90:
        verdict = "LARGE SWING"
        big.append((name, travel))
    if limited and not (lo <= 0.0 <= hi):
        verdict = "TARGET OUTSIDE LIMITS"

    print(f"{mid:<4}{name:<17}{pos:>9.1f}{0.0:>8.1f}{travel:>9.1f}{lim:>18}  {verdict}")

print("-" * 78)
if big:
    print("Joints moving more than 90 degrees when the script starts:")
    for n, t in sorted(big, key=lambda x: -x[1]):
        print(f"   {n:<18} {t:6.1f} deg")
else:
    print("No joint moves more than 90 degrees.")
if unlimited:
    print(f"\nNo firmware angle limit on: {', '.join(unlimited)}")
    print("   -> the servo will not stop itself; the assembly is the only stop.")
print("\nThis script moved nothing. Every call above is a get_*.")
