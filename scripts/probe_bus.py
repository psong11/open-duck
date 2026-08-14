#!/usr/bin/env python
"""Read-only probe of the servo bus. Writes nothing, changes nothing.

Finds whatever motors are on the bus and reports their vitals — most usefully
the voltage each motor actually sees, which answers "is my power adequate?"
without guessing.

    .venv/bin/python scripts/probe_bus.py --port /dev/cu.usbmodem5B901489761
"""

import argparse

from pypot.feetech import FeetechSTS3215IO

parser = argparse.ArgumentParser()
parser.add_argument("--port", required=True)
parser.add_argument(
    "--range", default="0-40",
    help="ID range to scan, e.g. '0-40' or '0-254'. Default 0-40 covers the "
         "factory default (1) and all 14 duck IDs (10-14, 20-24, 30-33).",
)
args = parser.parse_args()

lo, hi = (int(x) for x in args.range.split("-"))

io = FeetechSTS3215IO(args.port)
print(f"port open: {args.port}")
print(f"scanning ids {lo}..{hi} (read-only)\n")

found = []
for i in range(lo, hi + 1):
    try:
        io.get_present_position([i])
        found.append(i)
        print(f"  ✓ motor responding at id {i}")
    except Exception:
        pass

if not found:
    print("  no motors responded.")
    print("\nMeans one of: bus not powered, motor not seated, or wrong port.")
    raise SystemExit(1)

print(f"\n{len(found)} motor(s) found: {found}\n")

for i in found:
    def safe(fn):
        try:
            return fn([i])[0]
        except Exception as e:
            return f"<err: {type(e).__name__}>"

    def volts(fn):
        # Feetech voltage registers are in tenths of a volt, and pypot does
        # not convert them. 73 means 7.3V.
        v = safe(fn)
        return f"{v / 10:.1f} V" if isinstance(v, (int, float)) else v

    print(f"--- id {i} ---")
    print(f"  model            {safe(io.get_model)}")
    print(f"  present voltage  {volts(io.get_present_voltage)}   <-- power check")
    print(f"  min voltage lim  {volts(io.get_min_voltage_limit)}")
    print(f"  max voltage lim  {volts(io.get_max_voltage_limit)}")
    print(f"  temperature      {safe(io.get_present_temperature)} C")
    print(f"  position         {safe(io.get_present_position)}")
    print(f"  mode             {safe(io.get_mode)}")
    print(f"  PID              {safe(io.get_P_coefficient)}, "
          f"{safe(io.get_I_coefficient)}, {safe(io.get_D_coefficient)}")
    print(f"  accel / max      {safe(io.get_acceleration)} / "
          f"{safe(io.get_maximum_acceleration)}")
