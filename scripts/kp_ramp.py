#!/usr/bin/env python
"""Find the stiffness at which the pack gives out.

The runtime's turn_on() goes from limp to full stiffness on all 14 servos in
about four seconds, and the Pi has been dying inside that window -- before the
walk loop ever starts. That makes "walking browns out" the wrong description.
Holding a pose is what browns out; walking never got a turn.

So ramp the gain instead of jumping to it, and record every step to an fsynced
file. If the Pi dies, the last durable line names the gain that killed it, and
the pack voltage on the way there shows how much margin was left. One run, one
number, and the failure is the measurement rather than a wasted charge.

Nothing moves: every goal is parked at the joint's present position before
torque is enabled, so engagement is a no-op. Put the duck in the pose you
actually care about FIRST -- standing, or held in the air -- because the
current a servo draws is the current that pose demands of it.

    python kp_ramp.py --port /dev/ttyACM0                 # 4 -> 32 by 4
    python kp_ramp.py --port /dev/ttyACM0 --max 16        # stop early
    python kp_ramp.py --port /dev/ttyACM0 --release       # let go now

Keep a hand on the power switch. Ctrl-C reaches this only if the Pi is alive.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~"))
from duck_flightlog import FlightLog  # noqa: E402

from pypot.feetech import FeetechSTS3215IO  # noqa: E402

IDS = [10, 11, 12, 13, 14, 20, 21, 22, 23, 24, 30, 31, 32, 33]

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="/dev/ttyACM0")
ap.add_argument("--start", type=int, default=4)
ap.add_argument("--max", type=int, default=32, help="runtime default is 32")
ap.add_argument("--step", type=int, default=4)
ap.add_argument("--hold", type=float, default=3.0, help="seconds per step")
ap.add_argument("--release", action="store_true")
a = ap.parse_args()

io = FeetechSTS3215IO(a.port, timeout=0.05)

if a.release:
    io.disable_torque(IDS)
    print("torque released on all 14 - the duck is limp. Support it.")
    raise SystemExit(0)


def pack_v():
    try:
        v = io.get_present_voltage([10, 20, 30])
        return sorted(v)[len(v) // 2] / 10.0
    except Exception:
        return None


rest = pack_v()
print("pack at rest: %s V" % rest)
print("ramping Kp %d -> %d by %d, %.1fs per step" % (a.start, a.max, a.step, a.hold))
print("Every goal is parked at its present position. Nothing will move.")
if not input("Duck in the pose you want to test. Proceed? (y/N) ").lower().startswith("y"):
    raise SystemExit("aborted; nothing moved")

fl = FlightLog(
    "~/walklogs/kpramp-%s.csv" % time.strftime("%Y%m%d-%H%M%S"),
    fields=("kp", "v_min", "v_end", "held_s"),
).start()
fl.mark("rest_v=%s start=%d max=%d step=%d" % (rest, a.start, a.max, a.step))
print("log -> %s" % fl.path)

# Park before engaging: goal = present means torque-on is a no-op, not a lurch.
present = {mid: io.get_present_position([mid])[0] for mid in IDS}
for mid, pos in present.items():
    io.set_goal_position({mid: pos})

reason = "completed"
kp = a.start
last_ok = None
try:
    io.set_P_coefficient({mid: a.start for mid in IDS})
    io.enable_torque(IDS)
    fl.mark("torque enabled at kp=%d" % a.start)
    time.sleep(0.3)

    while kp <= a.max:
        io.set_P_coefficient({mid: kp for mid in IDS})
        t0 = time.time()
        vmin = None
        # Sample through the whole hold: the sag that matters is the dip right
        # after the gain lands, not the settled value a second later.
        while time.time() - t0 < a.hold:
            v = pack_v()
            if v is not None and (vmin is None or v < vmin):
                vmin = v
            time.sleep(0.05)
        vend = pack_v()
        fl.sample(kp, kp=kp, v_min=vmin, v_end=vend, held_s=round(time.time() - t0, 2))
        print("  kp %3d   min %sV   end %sV   survived" % (kp, vmin, vend), flush=True)
        last_ok = kp
        kp += a.step

except KeyboardInterrupt:
    reason = "KeyboardInterrupt"
except BaseException as e:
    reason = "%s: %s" % (type(e).__name__, e)
    raise
finally:
    fl.close(reason)
    try:
        io.disable_torque(IDS)
        print("\ntorque released.")
    except Exception:
        print("\ncould not release torque - bus is gone.")
    # Report the gain that actually held. Printing the loop counter would
    # name a step that was never attempted.
    print("reason: %s   highest Kp survived: %s" % (reason, last_ok))
