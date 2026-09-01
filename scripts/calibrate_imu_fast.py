#!/usr/bin/env python
"""Calibrate the BNO055's gyro and accelerometer, and stop waiting for the rest.

Upstream's calibrate_imu.py blocks on `imu.calibrated`, which is true only when
all four BNO055 status values reach 3: system, gyro, accelerometer, magnetometer.
Two things make that a trap on this robot.

The magnetometer sits inside a shell full of servos and current-carrying wire,
so it may never converge -- and nothing downstream wants it. raw_imu.py saves
exactly two things, offsets_accelerometer and offsets_gyroscope, and the policy's
observation is raw gyro and accelerometer. The magnetometer is waited on and then
discarded.

The other half is that accelerometer calibration needs the sensor held in
several distinct orientations, which upstream never says. Left on the bench it
reads 0 forever, which looks like a hang rather than a missing instruction.

So: wait for gyro and accel only, prompt for the poses that actually move the
number, and write the same pickle the runtime reads.

    python calibrate_imu_fast.py
    python calibrate_imu_fast.py --timeout 180

Read-only as far as the motors are concerned. Nothing is energised.
"""
import argparse
import json
import os
import pathlib
import pickle
import time

import adafruit_bno055
import board
import busio

ap = argparse.ArgumentParser()
ap.add_argument("--timeout", type=float, default=240.0)
ap.add_argument("--out", default=None)
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

out = a.out or os.path.join(
    os.path.expanduser("~/Open_Duck_Mini_Runtime/scripts"), "imu_calib_data.pkl")

try:
    upside_down = bool(json.loads(pathlib.Path(a.config).read_text())
                       .get("imu_upside_down", False))
except Exception:
    upside_down = False

i2c = busio.I2C(board.SCL, board.SDA)
imu = adafruit_bno055.BNO055_I2C(i2c)
imu.mode = adafruit_bno055.NDOF_MODE
time.sleep(0.5)

POSES = [
    "upright, standing normally",
    "on its BACK, face up",
    "on its FACE, front down",
    "on its LEFT side",
    "on its RIGHT side",
    "upside down, feet in the air",
]

print("""
The accelerometer only calibrates when it sees several distinct orientations.
Hold the duck STILL in each pose below for a few seconds -- still matters more
than exact. The magnetometer is ignored: nothing downstream uses it.
""")
print("Watching (sys, gyro, accel, mag) -- we need gyro=3 and accel=3.\n")

t0 = time.time()
pose_i = 0
last_print = 0.0
prompted = -1
while time.time() - t0 < a.timeout:
    sys_, gyro, accel, mag = imu.calibration_status
    if gyro == 3 and accel == 3:
        print("\n\nGyro and accelerometer are both calibrated.")
        break
    if pose_i != prompted:
        print("\n>>> Pose %d/%d: %s" % (pose_i + 1, len(POSES), POSES[pose_i]))
        prompted = pose_i
    now = time.time()
    if now - last_print > 0.5:
        print("\r    sys %d  gyro %d  accel %d  mag %d   (%.0fs)"
              % (sys_, gyro, accel, mag, a.timeout - (now - t0)), end="", flush=True)
        last_print = now
    # Move on to the next pose every few seconds; accel needs variety, not
    # perfection in any one orientation.
    if (now - t0) > (pose_i + 1) * 12 and pose_i < len(POSES) - 1:
        pose_i += 1
    time.sleep(0.1)
else:
    sys_, gyro, accel, mag = imu.calibration_status
    print("\n\nTimed out at sys %d gyro %d accel %d mag %d." % (sys_, gyro, accel, mag))
    if gyro < 3:
        print("Gyro needs the duck to sit completely still for a few seconds.")
    if accel < 3:
        print("Accel needs several distinct still orientations -- try again, "
              "holding each pose longer.")
    raise SystemExit(1)

data = {
    "offsets_accelerometer": imu.offsets_accelerometer,
    "offsets_gyroscope": imu.offsets_gyroscope,
}
print("accel offsets:", data["offsets_accelerometer"])
print("gyro  offsets:", data["offsets_gyroscope"])
with open(out, "wb") as f:
    pickle.dump(data, f)
    f.flush()
    os.fsync(f.fileno())
print("\nwrote %s" % out)
print("The runtime loads this by a relative path, so it must sit in the")
print("scripts directory -- which is where it just went.")
