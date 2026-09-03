#!/usr/bin/env python3
"""Measure ezer's tilt from the IMU. Read-only: no servo bus, no torque.

This is the bench tool for phase 0 of the test rig. It answers one question:
*what tilt number actually separates "standing" from "fallen" on this robot?*
Guessing that number and wiring it straight into the walk loop is how you get a
detector that kills good runs, so we measure first and arm later.

Nothing here opens /dev/ttyACM0. The servos are untouched and unpowered by this
script, so it is safe to run with the duck limp in your hands. Tilt her around.

    python fall_check.py                 # live readout
    python fall_check.py --tare          # capture the upright reference first
    python fall_check.py --log t.csv     # also record every sample

HOW TILT IS DEFINED
    The accelerometer at rest measures gravity. The angle between the gravity
    vector *now* and the gravity vector when she is standing correctly is the
    tilt. 0 = as she stands, 90 = on her side, 180 = upside down.

    By default the reference is +Z, because with imu_upside_down=true the board
    reads about +9.8 on Z when she is upright. That default is only a fallback
    for reading raw numbers -- it is NOT good enough to detect a fall with. The
    IMU sits in the torso, it is not mounted square, and her torso is pitched
    forward on purpose because the gait is built around that lean. --tare
    measures the real thing and writes fall_reference.json; after that, "0"
    means "exactly the attitude she walks at", which is what we want.

    TARE HER IN THE INIT CROUCH, WITH TORQUE ON:

        python slew_to_init.py       # moves to the crouch, exits still holding
        python fall_check.py --tare  # then this
        python slew_to_init.py --release

    A limp duck slumped on the bench is a different torso angle entirely --
    measured on 2026-09-02: hips 50 deg off init, knees 22 deg off. Taring
    that pose bakes the error into every reading afterwards.

WHY |a| IS ON THE SCREEN
    This trick only works while gravity dominates the reading. A walking robot
    also produces its own acceleration, and during a hard footfall the vector
    points somewhere gravity does not. Those samples are marked stale and must
    not be trusted -- that is the main source of false positives, and the
    reason the real detector debounces over several ticks instead of firing on
    one bad sample.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.expanduser("~/Open_Duck_Mini_Runtime/mini_bdx_runtime"))
from mini_bdx_runtime.raw_imu import Imu  # noqa: E402

REF_PATH = os.path.expanduser("~/fall_reference.json")

# Gravity is 9.81. Outside this band the duck is accelerating hard enough that
# the vector is not pointing at the floor any more, so the angle is meaningless.
G_LO, G_HI = 7.5, 12.0


def tilt_deg(accel, ref):
    """Angle in degrees between the current gravity vector and the reference."""
    n = np.linalg.norm(accel)
    if n < 1e-6:
        return None
    return float(np.degrees(np.arccos(np.clip(np.dot(accel / n, ref), -1.0, 1.0))))


def load_ref():
    if os.path.exists(REF_PATH):
        with open(REF_PATH) as f:
            v = np.array(json.load(f)["reference"], dtype=float)
        return v / np.linalg.norm(v), REF_PATH
    return np.array([0.0, 0.0, 1.0]), "default +Z (no tare yet)"


def read_config_upside_down():
    """Match the walk script: the axis remap must be the one the robot runs."""
    p = os.path.expanduser("~/duck_config.json")
    try:
        with open(p) as f:
            return bool(json.load(f).get("imu_upside_down", True))
    except Exception:
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tare", action="store_true",
                    help="hold her in her standing pose, capture the reference")
    ap.add_argument("--seconds", type=float, default=3.0,
                    help="averaging window for --tare")
    ap.add_argument("--hz", type=float, default=20.0)
    ap.add_argument("--log", type=str, default=None)
    args = ap.parse_args()

    upside_down = read_config_upside_down()
    print(f"imu_upside_down={upside_down} (from duck_config.json)")
    imu = Imu(50, upside_down=upside_down)
    time.sleep(0.5)  # let the worker thread land a sample

    if args.tare:
        print(f"\nShe must be HOLDING THE INIT CROUCH (torque on), not limp.")
        print(f"Averaging {args.seconds}s...")
        acc = []
        t0 = time.time()
        while time.time() - t0 < args.seconds:
            d = imu.get_data()
            a = np.array(d["accelero"], dtype=float)
            if G_LO < np.linalg.norm(a) < G_HI:
                acc.append(a)
            time.sleep(1.0 / args.hz)
        if len(acc) < 5:
            print("Not enough still samples. Is the IMU reading? Try again.")
            return 1
        mean = np.mean(acc, axis=0)
        with open(REF_PATH, "w") as f:
            json.dump({"reference": mean.tolist(),
                       "n": len(acc),
                       "upside_down": upside_down}, f, indent=2)
        off = tilt_deg(mean, np.array([0.0, 0.0, 1.0]))
        print(f"reference = {np.around(mean, 3)}  (n={len(acc)})")
        print(f"that is {off:.1f} deg away from a naive +Z assumption")
        print(f"saved -> {REF_PATH}")
        return 0

    ref, src = load_ref()
    print(f"reference: {np.around(ref, 3)}  <- {src}")
    print("\nTilt her by hand. Ctrl-C when done.\n")
    print(f"{'tilt':>7} {'|a|':>6}  {'ax':>7} {'ay':>7} {'az':>7}  {'max':>6}  state")

    log = open(args.log, "w", buffering=1) if args.log else None
    if log:
        log.write("t_s,tilt_deg,a_norm,ax,ay,az,gravity_ok\n")

    peak = 0.0
    t0 = time.time()
    tty = sys.stdout.isatty()
    seen_real = False
    try:
        while True:
            d = imu.get_data()
            a = np.array(d["accelero"], dtype=float)
            n = float(np.linalg.norm(a))
            t = tilt_deg(a, ref)
            ok = G_LO < n < G_HI
            # The worker seeds last_imu_data with zeros; ignore until it lands one.
            if n < 1e-6 and not seen_real:
                time.sleep(1.0 / args.hz)
                continue
            seen_real = True
            if t is not None and ok:
                peak = max(peak, t)
            state = "" if ok else "STALE (accelerating)"
            shown = f"{t:6.1f}d" if t is not None else "   --  "
            line = (f"{shown} {n:6.2f}  {a[0]:7.2f} {a[1]:7.2f} {a[2]:7.2f}"
                    f"  {peak:5.1f}  {state}")
            print(line, end="\r" if tty else "\n", flush=True)
            if log and t is not None:
                log.write(f"{time.time()-t0:.3f},{t:.2f},{n:.3f},"
                          f"{a[0]:.3f},{a[1]:.3f},{a[2]:.3f},{int(ok)}\n")
            time.sleep(1.0 / args.hz)
    except KeyboardInterrupt:
        print(f"\n\npeak tilt while gravity-dominated: {peak:.1f} deg")
        if log:
            log.close()
            print(f"log -> {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
