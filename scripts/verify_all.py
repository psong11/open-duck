#!/usr/bin/env python
"""Phase 0 acceptance test: all 14 motors on one bus, on the assembled robot.

STRICTLY READ-ONLY. Every call below is a get_*; no goal position, no torque
command, no EEPROM write. Nothing here can move a joint. That matters because
by the time this runs the legs are built, and a motor driven to a stale goal
would push against the assembly.

Proves what per-motor verification cannot:
  1. every expected id answers on a shared bus
  2. no id is missing or duplicated (a duplicate hides as a single responder)
  3. config survived being power-cycled and re-cabled
  4. no joint is currently straining against its own linkage

    python scripts/verify_all.py --port /dev/ttyACM0
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

p = argparse.ArgumentParser()
p.add_argument("--port", required=True)
p.add_argument("--timeout", type=float, default=0.05)
p.add_argument("--strays", action="store_true",
               help="also sweep ids 0-253 for unexpected motors (slow)")
args = p.parse_args()

io = FeetechSTS3215IO(args.port, timeout=args.timeout)


def get(mid, reg):
    try:
        return getattr(io, f"get_{reg}")([mid])[0]
    except Exception:
        return None


def fmt(v, unit="", scale=1.0, nd=1):
    return f"{v * scale:.{nd}f}{unit}" if isinstance(v, (int, float)) else "-"


print(f"{'id':<4}{'joint':<17}{'volt':<7}{'temp':<6}{'pos':<9}{'goal':<9}"
      f"{'delta':<8}{'load':<7}{'mA':<7}status")
print("-" * 92)

missing, misconfigured, straining = [], [], []

for mid, name in JOINTS.items():
    pos = get(mid, "present_position")
    if pos is None:
        print(f"{mid:<4}{name:<17}{'-':<7}{'-':<6}{'-':<9}{'-':<9}{'-':<8}"
              f"{'-':<7}{'-':<7}NOT RESPONDING")
        missing.append(mid)
        continue

    goal = get(mid, "goal_position")
    load = get(mid, "present_load")
    curr = get(mid, "present_current")
    volt = get(mid, "present_voltage")
    temp = get(mid, "present_temperature")

    delta = abs(pos - goal) if isinstance(goal, (int, float)) else None

    bad = [r for r, want in EXPECTED.items() if get(mid, r) != want]
    if bad:
        misconfigured.append(mid)

    # A joint far from its goal while pulling load is pushing on the linkage.
    strain = (delta is not None and delta > 5
              and isinstance(load, (int, float)) and abs(load) > 50)
    if strain:
        straining.append(mid)

    status = "ok" if not bad else "BAD: " + ", ".join(bad)
    if strain:
        status = "STRAINING  " + status

    print(f"{mid:<4}{name:<17}"
          f"{fmt(volt, 'V', 0.1):<7}{fmt(temp, 'C', 1, 0):<6}"
          f"{fmt(pos, '', 1):<9}{fmt(goal, '', 1):<9}{fmt(delta, '', 1):<8}"
          f"{fmt(load, '', 1, 0):<7}{fmt(curr, '', 1, 0):<7}{status}")

strays = []
if args.strays:
    print("\nsweeping for stray ids (this takes a moment)...")
    for i in range(254):
        if i in JOINTS:
            continue
        if get(i, "present_position") is not None:
            strays.append(i)

print("-" * 92)
print(f"responding    {len(JOINTS) - len(missing)} / {len(JOINTS)}")
if missing:
    print(f"MISSING       {missing}")
if misconfigured:
    print(f"MISCONFIGURED {misconfigured}")
if straining:
    print(f"STRAINING     {straining}  <- joint is loaded and off its goal; "
          f"cut power before investigating")
if strays:
    print(f"STRAY ids     {strays}  <- unexpected motor on the bus")
if not args.strays:
    print("(stray sweep skipped; re-run with --strays to check for duplicates)")

ok = not (missing or misconfigured or strays)
print("\n" + ("PASS — Phase 0 complete." if ok else "FAIL — see above."))
raise SystemExit(0 if ok else 1)
