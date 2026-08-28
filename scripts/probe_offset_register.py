#!/usr/bin/env python
"""Does the STS3215 offset register (addr 31) do what we need, and in what units?

Experiment on head_yaw only -- it carries no load and torque stays OFF the
whole time, so nothing can move regardless of what we write.

pypot applies a Dynamixel degree conversion to this register, but Feetech
encodes it as sign-magnitude (bit 11 = direction). So the API's units are
suspect. Measure the effect instead of trusting the label.

Restores the original value in a finally block and re-verifies on a FRESH
connection, because a write that reads back correctly on the same connection
proves nothing about EEPROM -- that is how motor 30 fooled us in Phase 0.

    python scripts/probe_offset_register.py --port /dev/ttyACM0 --test-deg 10
"""
import argparse
import time

from pypot.feetech import FeetechSTS3215IO

MID, NAME = 32, "head_yaw"

ap = argparse.ArgumentParser()
ap.add_argument("--port", required=True)
ap.add_argument("--test-deg", type=float, default=10.0)
a = ap.parse_args()


def fresh():
    time.sleep(0.3)
    return FeetechSTS3215IO(a.port, timeout=0.05)


io = fresh()
assert not io.is_torque_enabled([MID])[0], "torque is ON -- refusing to proceed"

orig_offset = io.get_offset([MID])[0]
pos_before = io.get_present_position([MID])[0]
print(f"{NAME}: offset={orig_offset}  present_position={pos_before:.2f}  torque=off")

restored = False
try:
    print(f"\nwriting offset = {a.test_deg} ...")
    io.set_lock({MID: 0})
    io.set_offset({MID: a.test_deg})
    io.set_lock({MID: 1})
    time.sleep(0.3)

    io2 = fresh()                       # fresh connection: proves EEPROM
    off_rb = io2.get_offset([MID])[0]
    pos_after = io2.get_present_position([MID])[0]
    shift = pos_after - pos_before

    print(f"  offset reads back : {off_rb}   (wrote {a.test_deg})")
    print(f"  position before   : {pos_before:.2f}")
    print(f"  position after    : {pos_after:.2f}")
    print(f"  --> reported position shifted by {shift:+.2f} deg")

    if abs(abs(shift) - abs(a.test_deg)) < 2.0:
        print(f"\n  USABLE. 1 unit of set_offset == 1 degree of reported position"
              f" (sign {'same' if shift * a.test_deg > 0 else 'INVERTED'}).")
    elif abs(shift) < 1.0:
        print("\n  NO EFFECT on present_position. This register does not do what "
              "we need, or the write did not land.")
    else:
        print(f"\n  SCALED. shift/{a.test_deg} = {shift / a.test_deg:.3f}. "
              f"Units are not 1:1 -- do not use without solving the encoding.")
finally:
    io3 = fresh()
    io3.set_lock({MID: 0})
    io3.set_offset({MID: orig_offset})
    io3.set_lock({MID: 1})
    time.sleep(0.3)
    io4 = fresh()
    back = io4.get_offset([MID])[0]
    pos = io4.get_present_position([MID])[0]
    restored = abs(back - orig_offset) < 0.5
    print(f"\nrestore: offset={back} (was {orig_offset})  position={pos:.2f}  "
          f"{'OK' if restored else '*** NOT RESTORED ***'}")
