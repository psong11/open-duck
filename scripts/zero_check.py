#!/usr/bin/env python
"""Ask the leg where its own zero is, and decide whether the fix is software.

The hip pitches stop about twenty degrees short of the init crouch. Two
explanations fit that equally well and they need opposite fixes:

  labels shifted   the arc contains the pose, but the servo reports the wrong
                   number for it -- correctable by changing the EEPROM offset,
                   reversible, no disassembly
  arc too small    the leg physically cannot reach the pose, and no relabelling
                   helps, because neither an offset nor a horn reseat moves a
                   mechanical stop

Relabelling cannot move a stop. So the deciding question is where the pose sits
relative to the arc, and that needs a reference the firmware cannot fake.

Hip pitch zero has a physical definition: the thigh in line with the torso, the
pose the duck stands in with a straight leg. Hold it there, read what the servo
claims, and the discrepancy is the label error -- measured against the robot
instead of against its own configuration.

    python zero_check.py                 # uses the arc from the last find_range
    python zero_check.py --arc12 -136.0 15.1 --arc22 -18.0 138.1

Torque is released on the hip pitches. Support the legs.
"""
import argparse
import json
import math
import pathlib
import statistics
import time

from pypot.feetech import FeetechSTS3215IO

NAMES = {12: "right_hip_pitch", 22: "left_hip_pitch"}
INIT = {"right_hip_pitch": 0.635, "left_hip_pitch": -0.63}

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="/dev/ttyACM0")
ap.add_argument("--arc12", type=float, nargs=2, default=[-136.0, 15.1],
                metavar=("MIN", "MAX"), help="measured range for id 12")
ap.add_argument("--arc22", type=float, nargs=2, default=[-18.0, 138.1],
                metavar=("MIN", "MAX"), help="measured range for id 22")
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)
cfg = json.loads(pathlib.Path(a.config).read_text())
offsets = cfg["joints_offsets" if "joints_offsets" in cfg else "joints_offset"]
ARCS = {12: a.arc12, 22: a.arc22}

print(__doc__.strip().split("\n\n")[0])
print("\nReleasing torque on both hip pitches. The legs will drop -- hold them.")
if not input("Ready? (y/N) ").lower().startswith("y"):
    raise SystemExit("aborted; nothing changed")

io.disable_torque([12, 22])
time.sleep(0.3)

readings = {}
for mid in (12, 22):
    name = NAMES[mid]
    side = name.split("_")[0]
    print("\n--- %s (id %d) ---" % (name, mid))
    print("Hold the %s thigh IN LINE WITH THE TORSO -- straight leg, as if the" % side)
    print("duck were standing bolt upright. Steady, not forced against anything.")
    input("Press Enter while holding it there... ")
    samples = []
    for _ in range(20):
        try:
            samples.append(io.get_present_position([mid])[0])
        except Exception:
            pass
        time.sleep(0.02)
    if not samples:
        print("  no readings from id %d" % mid)
        continue
    med = statistics.median(samples)
    spread = max(samples) - min(samples)
    readings[mid] = med
    print("  reads %.1f deg   (spread %.1f over 20 samples)" % (med, spread))
    if spread > 3:
        print("  NOTE: it moved while reading; hold steadier and re-run for a tighter number.")

print("\n" + "=" * 72)
print("%-18s %8s %8s %10s %10s   %s"
      % ("joint", "reads", "should", "label err", "target", "after correction"))
print("-" * 72)
verdicts = []
for mid, med in readings.items():
    name = NAMES[mid]
    should = math.degrees(offsets.get(name, 0.0))   # zero pose, offsets applied
    err = should - med                               # add this to every reading
    target = math.degrees(INIT[name]) + should
    lo, hi = ARCS[mid]
    lo_c, hi_c = lo + err, hi + err
    inside = lo_c <= target <= hi_c
    margin = min(target - lo_c, hi_c - target)
    verdicts.append((name, inside, err, margin))
    print("%-18s %8.1f %8.1f %10.1f %10.1f   %s"
          % (name, med, should, err, target,
             "inside, %.0f deg to spare" % margin if inside
             else "STILL OUT by %.1f" % (target - hi_c if target > hi_c else lo_c - target)))
print("=" * 72)

soft = [v for v in verdicts if v[1]]
hard = [v for v in verdicts if not v[1]]
if hard:
    print("""
VERDICT: at least one joint stays out of range even after correcting the label.
A stop cannot be relabelled away, so this one is mechanical -- check bracket
orientation, whether the leg is fitted the right way round, and whether the
harness is binding, before touching the horn splines.""")
if soft and not hard:
    worst = min(v[3] for v in soft)
    print("""
VERDICT: correcting the label brings the pose inside the arc. This is a
SOFTWARE fix -- adjust the EEPROM offsets by the 'label err' column above.
No disassembly. Reversible, and finer than a spline tooth.""")
    if worst < 12:
        print("""
CAUTION: the tightest margin is %.0f deg. That clears the stop but leaves the
joint close to it, and walking swings either side of the init pose. Treat this
as 'reachable' rather than 'comfortable'.""" % worst)

print("\nTorque is still off. Both hip pitches are limp.")
