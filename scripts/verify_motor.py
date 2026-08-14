#!/usr/bin/env python
"""Verify one configured motor, over a FRESH connection.

configure_motor.py reads its own writes back in the same session, which does
not prove the values reached EEPROM. This reconnects and checks. Caught a real
dropped write on id 30 (max_acceleration stuck at the factory 50).

    .venv/bin/python scripts/verify_motor.py --id 30 --port <port>

Exit 0 = all expected values present. Exit 1 = mismatch.
"""

import argparse

from pypot.feetech import FeetechSTS3215IO

# What configure_motor.py is supposed to leave behind.
EXPECTED = {
    "P_coefficient": 32,
    "I_coefficient": 0,
    "D_coefficient": 0,
    "acceleration": 0,
    "maximum_acceleration": 0,
    "mode": 0,
}

parser = argparse.ArgumentParser()
parser.add_argument("--id", type=int, required=True)
parser.add_argument("--port", required=True)
args = parser.parse_args()

io = FeetechSTS3215IO(args.port)

try:
    io.get_present_position([args.id])
except Exception:
    print(f"FAIL: no motor responding at id {args.id}")
    raise SystemExit(1)

bad = []
for reg, want in EXPECTED.items():
    try:
        got = getattr(io, f"get_{reg}")([args.id])[0]
    except Exception as e:
        got = f"<err {type(e).__name__}>"
    ok = got == want
    if not ok:
        bad.append((reg, want, got))
    print(f"  {'ok  ' if ok else 'BAD '} {reg:<22} want {want:<4} got {got}")

if bad:
    print(f"\nFAIL: {len(bad)} register(s) wrong on id {args.id}. Re-run the "
          f"configure step for this motor.")
    raise SystemExit(1)

print(f"\nPASS: id {args.id} fully configured.")
