#!/usr/bin/env python
"""Drive the whole robot to its init pose through the HWI, gently, and report.

This is turn_on() with the jump taken out and the numbers left in. The runtime
writes the init pose to all fourteen servos in one command at Kp 32; here the
same pose is approached over several seconds at Kp 8, and every joint's final
error is printed. A joint that cannot reach its target shows up as a large
error, which is what the hip pitches did before the direction fix.

It exercises the real path -- DuckConfig, HWI, joints_directions, offsets -- so
a clean result here means the runtime should start rather than stall.

    python hwi_init_check.py              # 6 s slew at Kp 8
    python hwi_init_check.py --kp 16
    python hwi_init_check.py --release

Support the duck. Torque is left ON at the end so the pose can be inspected.
"""
import argparse
import math
import time

import numpy as np

from mini_bdx_runtime.duck_config import DuckConfig
from mini_bdx_runtime.rustypot_position_hwi import HWI

ap = argparse.ArgumentParser()
ap.add_argument("--kp", type=int, default=8)
ap.add_argument("--secs", type=float, default=6.0)
ap.add_argument("--hz", type=float, default=20.0)
ap.add_argument("--release", action="store_true")
a = ap.parse_args()

hwi = HWI(DuckConfig())
names = list(hwi.joints.keys())

if a.release:
    hwi.turn_off()
    print("torque released on all joints - the duck is limp. Support it.")
    raise SystemExit(0)

mirrored = {k: v for k, v in hwi.joints_directions.items() if v != 1.0}
print("mirrored joints:", mirrored or "none")

start = hwi.get_present_positions()
if start is None:
    raise SystemExit("could not read positions")
target = np.array([hwi.init_pos[n] for n in names])

print("\n%-18s %9s %9s %9s" % ("joint", "now", "target", "travel"))
print("-" * 48)
for i, n in enumerate(names):
    print("%-18s %9.1f %9.1f %9.1f"
          % (n, math.degrees(start[i]), math.degrees(target[i]),
             abs(math.degrees(target[i] - start[i]))))
print("-" * 48)
print("slewing over %.1f s at Kp %d" % (a.secs, a.kp))
if not input("\nSupport the duck. Proceed? (y/N) ").lower().startswith("y"):
    raise SystemExit("aborted; nothing moved")

# Park at the present pose before energising, so engagement is a no-op.
hwi.set_position_all({n: float(start[i]) for i, n in enumerate(names)})
hwi.set_kps([a.kp] * len(names))
hwi.set_kds([0] * len(names))
hwi.io.enable_torque(list(hwi.joints.values()))
time.sleep(0.4)
print("torque on at the present pose.")

steps = max(1, int(a.secs * a.hz))
try:
    for s in range(1, steps + 1):
        f = s / steps
        pose = start + (target - start) * f
        hwi.set_position_all({n: float(pose[i]) for i, n in enumerate(names)})
        time.sleep(1.0 / a.hz)
    time.sleep(0.6)

    now = hwi.get_present_positions()
    print("\n%-18s %9s %9s %8s   %s" % ("joint", "target", "reached", "err", ""))
    print("-" * 56)
    worst = 0.0
    for i, n in enumerate(names):
        e = abs(math.degrees(target[i] - now[i]))
        worst = max(worst, e)
        print("%-18s %9.1f %9.1f %8.1f%s"
              % (n, math.degrees(target[i]), math.degrees(now[i]), e,
                 "   <-- not reaching" if e > 5 else ""))
    print("-" * 56)
    print("worst error: %.1f deg" % worst)
    print("PASS - every joint reached its target." if worst < 5
          else "FAIL - something still cannot get where it is told.")
except KeyboardInterrupt:
    print("\ninterrupted")
finally:
    print("\nTorque is still ON and holding. Release with: --release")
