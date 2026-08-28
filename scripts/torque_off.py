#!/usr/bin/env python
"""EMERGENCY STOP. Releases torque on all 14 joints, immediately.

find_soft_offsets.py only catches KeyboardInterrupt. Any other failure -- a USB
re-enumeration, an unhandled exception -- exits with torque still ENGAGED, and
the servos will hold their last goal indefinitely, pushing against whatever is
in the way.

Run this from a second terminal if that happens.

    python scripts/torque_off.py --port /dev/ttyACM0
"""
import argparse
from pypot.feetech import FeetechSTS3215IO

IDS = [10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 30, 31, 32, 33]
ap = argparse.ArgumentParser()
ap.add_argument("--port", default="/dev/ttyACM0")
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)
io.disable_torque(IDS)
still = [i for i in IDS if io.is_torque_enabled([i])[0]]
print("torque released on all 14." if not still else f"STILL ENGAGED: {still} — retry")
