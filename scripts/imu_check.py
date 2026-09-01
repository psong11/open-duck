#!/usr/bin/env python
"""Read the IMU and check its axes point the way the policy expects.

The walk log rules out compute: the loop held 49.5 Hz with a mean of 7.1 ms
against a 20 ms budget. So a duck that wiggles and drives its face into the
floor is being told something wrong about which way is up.

Two things can do that, and they are independent:

  uncalibrated   the runtime printed "Imu is running uncalibrated" because
                 imu_calib_data.pkl does not exist. Fix with upstream's
                 calibrate_imu.py.
  wrong axes     duck_config's imu_upside_down picks between two axis remaps
                 that differ only in the SIGN of two axes. Get it wrong and
                 every correction the policy makes is backwards, which looks
                 exactly like face-planting.

The observation fed to the policy is the raw gyro and accelerometer, so at rest
the accelerometer is just gravity in body coordinates. Standing upright and
still, it should read about +9.8 on one axis and near zero on the other two.
Tilt the duck nose-down and that reading should move in a consistent direction.

    python imu_check.py               # uses duck_config's setting
    python imu_check.py --flip        # the opposite setting, same session
    python imu_check.py --secs 30

Read-only. No motor is energised.
"""
import argparse
import json
import math
import pathlib
import statistics
import time

from mini_bdx_runtime.raw_imu import Imu

ap = argparse.ArgumentParser()
ap.add_argument("--flip", action="store_true",
                help="use the opposite imu_upside_down setting")
ap.add_argument("--secs", type=float, default=0)
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

cfg = json.loads(pathlib.Path(a.config).read_text())
upside_down = bool(cfg.get("imu_upside_down", False))
if a.flip:
    upside_down = not upside_down

print("imu_upside_down = %s%s" % (upside_down, "   (FLIPPED from config)" if a.flip else ""))
imu = Imu(sampling_freq=50, upside_down=upside_down)
time.sleep(1.0)


def read(n=25):
    ax, ay, az, gs = [], [], [], []
    for _ in range(n):
        d = imu.get_data()
        acc, gyr = d["accelero"], d["gyro"]
        ax.append(acc[0]); ay.append(acc[1]); az.append(acc[2])
        gs.append(max(abs(g) for g in gyr))
        time.sleep(0.02)
    return (statistics.median(ax), statistics.median(ay),
            statistics.median(az), max(gs))


def describe(tag):
    x, y, z, gmax = read()
    mag = math.sqrt(x * x + y * y + z * z)
    axes = {"X": x, "Y": y, "Z": z}
    dom = max(axes, key=lambda k: abs(axes[k]))
    print("  %-14s accel  X %6.2f  Y %6.2f  Z %6.2f   |a| %5.2f   "
          "dominant %s %s   gyro max %.2f"
          % (tag, x, y, z, mag, dom, "+" if axes[dom] > 0 else "-", gmax))
    if gmax > 0.5:
        print("                 (it was moving -- hold it still for a clean read)")
    return x, y, z, dom, axes[dom]


print("\nHold the duck UPRIGHT and STILL, as if standing normally.")
input("Press Enter when steady... ")
_, _, _, dom1, val1 = describe("upright")

print("\nNow tilt it NOSE-DOWN about 30 degrees, and hold.")
input("Press Enter when steady... ")
x2, y2, z2, dom2, val2 = describe("nose-down")

print("\n" + "=" * 70)
if abs(val1) < 8.0:
    print("Upright reading is not close to 1 g on a single axis (%.2f)." % val1)
    print("Either it was not upright, or the axis remap is scrambling things.")
else:
    print("Upright: gravity sits on %s at %+.2f m/s^2." % (dom1, val1))
    if val1 > 0:
        print("  Positive on the vertical axis is what a policy trained in")
        print("  MuJoCo normally expects for an upright body.")
    else:
        print("  NEGATIVE on the vertical axis. If the other setting reads")
        print("  positive here, that one is very likely the correct one.")
print("Nose-down moved the dominant axis to %s (%+.2f)." % (dom2, val2))
print("""
Now run it again with --flip and compare. The correct setting is the one where
upright reads close to +1 g on the vertical axis, and tilting nose-down swings
it in a consistent, sensible direction. Whichever that is, put it in
duck_config.json as imu_upside_down.
""")
print("Read-only: nothing was energised.")
