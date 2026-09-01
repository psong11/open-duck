#!/usr/bin/env python
"""Walk one joint toward its target in small steps and find where it stops.

The open question: is the current spike a mechanical stop, or does the joint
stall in free air? Those look identical in a voltage log -- both show load and
sag climbing together -- but they differ in one visible way. Against a stop,
position flatlines at the SAME angle every run while load keeps climbing. Stalled
in free air, position keeps creeping and the angle where it gives up moves with
the pack.

So: step the goal a couple of degrees at a time, and after each step record
where the joint actually went, what it cost, and what the pack did. Watch the
thigh while it runs. The step where position stops following is the answer, and
you can see with your own eyes whether anything is touching at that moment.

Aborts on its own before it can brown the Pi out -- there is nothing to learn
from another death, and the abort threshold is itself a data point.

    python hip_probe.py                    # right hip pitch, 0 -> 40 deg
    python hip_probe.py --id 22            # left  (target is negative)
    python hip_probe.py --kp 16            # push harder
    python hip_probe.py --release

Support the duck. Torque comes on at low gain and steps in 2 degree increments.
"""
import argparse
import json
import math
import pathlib
import sys
import time

sys.path.insert(0, "/home/paul")
from duck_flightlog import FlightLog  # noqa: E402

from pypot.feetech import FeetechSTS3215IO  # noqa: E402

NAMES = {12: "right_hip_pitch", 22: "left_hip_pitch"}
INIT = {"right_hip_pitch": 0.635, "left_hip_pitch": -0.63}

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="/dev/ttyACM0")
ap.add_argument("--id", type=int, default=12, choices=[12, 22])
ap.add_argument("--kp", type=int, default=8)
ap.add_argument("--step", type=float, default=2.0)
ap.add_argument("--settle", type=float, default=1.2, help="seconds per step")
ap.add_argument("--past", type=float, default=4.0, help="degrees to try beyond target")
ap.add_argument("--max-load", type=int, default=550, help="abort above this")
ap.add_argument("--min-volts", type=float, default=6.4, help="abort below this")
ap.add_argument("--release", action="store_true")
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)
mid = a.id
name = NAMES[mid]

if a.release:
    io.disable_torque([mid])
    print("torque released on %s." % name)
    raise SystemExit(0)

cfg = json.loads(pathlib.Path(a.config).read_text())
offsets = cfg["joints_offsets" if "joints_offsets" in cfg else "joints_offset"]
target = math.degrees(INIT[name]) + math.degrees(offsets.get(name, 0.0))


def volts():
    try:
        v = io.get_present_voltage([10, 20, 30])
        return sorted(v)[1] / 10.0
    except Exception:
        return None


def load_of():
    try:
        return int(io.get_present_load([mid])[0]) & 0x3FF  # sign-magnitude
    except Exception:
        return None


start = io.get_present_position([mid])[0]
direction = 1.0 if target > start else -1.0
end = target + direction * a.past

print("%s (id %d)" % (name, mid))
print("  now %.1f   target %.1f   probing to %.1f in %.1f deg steps at Kp %d"
      % (start, target, end, a.step, a.kp))
print("  aborts if load > %d or pack < %.1f V" % (a.max_load, a.min_volts))
print("\n  WATCH THE THIGH. If it stops following, look at what is touching it.")
if not input("\nSupport the duck. Proceed? (y/N) ").lower().startswith("y"):
    raise SystemExit("aborted; nothing moved")

fl = FlightLog("~/walklogs/hipprobe-%s-%d.csv" % (time.strftime("%Y%m%d-%H%M%S"), mid),
               fields=("goal", "pos", "err", "load", "v")).start()
fl.mark("%s start=%.1f target=%.1f kp=%d" % (name, start, target, a.kp))

io.set_goal_position({mid: start})
io.set_P_coefficient({mid: a.kp})
io.enable_torque([mid])
time.sleep(0.4)

print("\n%8s %8s %8s %7s %7s   %s" % ("goal", "reached", "err", "load", "volts", ""))
print("-" * 58)
reason = "completed"
goal = start
n = 0
try:
    while (goal - end) * direction < 0:
        goal += direction * a.step
        io.set_goal_position({mid: goal})
        time.sleep(a.settle)
        pos = io.get_present_position([mid])[0]
        ld = load_of()
        v = volts()
        err = goal - pos
        n += 1
        fl.sample(n, goal=round(goal, 1), pos=round(pos, 1), err=round(err, 1),
                  load=ld, v=v)
        flag = ""
        if abs(err) > 3:
            flag = "  <-- not following"
        print("%8.1f %8.1f %8.1f %7s %7s%s" % (goal, pos, err, ld, v, flag), flush=True)

        if ld is not None and ld > a.max_load:
            reason = "load %d over limit" % ld
            break
        if v is not None and v < a.min_volts:
            reason = "pack %.1f V under limit" % v
            break
except KeyboardInterrupt:
    reason = "KeyboardInterrupt"
finally:
    fl.close(reason)
    io.disable_torque([mid])
    print("-" * 58)
    print("stopped: %s" % reason)
    print("torque released on %s." % name)
    print("""
Reading it: the last row where 'reached' still tracked 'goal' is how far the
joint can actually go. If that angle is the same on a re-run at a different Kp,
it is a mechanical stop. If it moves further with more gain, it is torque.""")
