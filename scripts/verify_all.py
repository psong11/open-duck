#!/usr/bin/env python
"""Phase 0 acceptance test: all 14 motors on the bus at once.

Proves three things that per-motor verification cannot:
  1. every expected id answers
  2. no id is missing or duplicated (a duplicate hides as a single responder)
  3. every motor's config survived being power-cycled and re-cabled

    .venv/bin/python scripts/verify_all.py --port <port>
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

EXPECTED = {
    "P_coefficient": 32, "I_coefficient": 0, "D_coefficient": 0,
    "acceleration": 0, "maximum_acceleration": 0, "mode": 0,
}

parser = argparse.ArgumentParser()
parser.add_argument("--port", required=True)
args = parser.parse_args()

io = FeetechSTS3215IO(args.port)

# Anything still at a factory or unexpected address is a problem too.
strays = []
for i in range(254):
    if i in JOINTS:
        continue
    try:
        io.get_present_position([i])
        strays.append(i)
    except Exception:
        pass

print(f"{'id':<5}{'joint':<18}{'volts':<8}{'temp':<7}{'pos':<10}status")
print("-" * 62)

missing, misconfigured = [], []
for mid, name in JOINTS.items():
    try:
        pos = io.get_present_position([mid])[0]
    except Exception:
        print(f"{mid:<5}{name:<18}{'-':<8}{'-':<7}{'-':<10}NOT RESPONDING")
        missing.append(mid)
        continue

    def get(reg):
        try:
            return getattr(io, f"get_{reg}")([mid])[0]
        except Exception:
            return None

    bad = [r for r, want in EXPECTED.items() if get(r) != want]
    v = get("present_voltage")
    t = get("present_temperature")
    status = "ok" if not bad else f"BAD: {', '.join(bad)}"
    if bad:
        misconfigured.append(mid)
    volts = f"{v / 10:.1f}V" if isinstance(v, (int, float)) else "?"
    print(f"{mid:<5}{name:<18}{volts:<8}{str(t) + 'C':<7}{pos:<10.1f}{status}")

print("-" * 62)
print(f"responding    {len(JOINTS) - len(missing)} / {len(JOINTS)}")
if missing:
    print(f"MISSING       {missing}")
if misconfigured:
    print(f"MISCONFIGURED {misconfigured}")
if strays:
    print(f"STRAY ids     {strays}  <- unexpected motor on the bus")

ok = not (missing or misconfigured or strays)
print("\n" + ("PASS — Phase 0 complete." if ok else "FAIL — see above."))
raise SystemExit(0 if ok else 1)
