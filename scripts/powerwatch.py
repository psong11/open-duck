#!/usr/bin/env python3
"""Watch the Pi's power rail at 10 Hz while something else drives the servos.

Why this exists: the walk dies in seconds and the Pi dies with it. The servo
bus can't help -- rustypot exposes no voltage register, and a second process
opening /dev/ttyACM0 would interleave packets with the walk. But the Pi can
watch its own 5 V rail without touching the bus at all.

The decisive reading is /sys/class/hwmon/hwmon*/in0_lcrit_alarm, the rpi_volt
driver's low-critical flag. It trips at the same threshold that sets the
under-voltage bit in get_throttled, but it is a sysfs read -- no fork, no
mailbox round trip -- so it can be sampled fast enough to catch the approach
to a collapse rather than just the aftermath.

That matters because of a blind spot we hit before: get_throttled needs the
SoC alive at degraded voltage to latch a bit. A clean collapse reads 0x0 and
looks, wrongly, like the power was fine.

Every sample is fsynced. When the Pi dies, the last durable line is the time
of death to within 100 ms, and the absence of the "### END" marker is what
tells you it was a death and not an exit.

    ./powerwatch.py &          # start before the walk
    ...run the walk...
    kill %1                    # clean stop writes the END marker
"""

import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from duck_flightlog import FlightLog  # noqa: E402

HZ = 10.0
THR_EVERY = 10  # get_throttled forks; 1 Hz is enough for a latched bit

LCRIT = "/sys/class/hwmon/hwmon1/in0_lcrit_alarm"
TEMP = "/sys/class/thermal/thermal_zone0/temp"
FREQ = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def find_lcrit():
    if os.path.exists(LCRIT):
        return LCRIT
    import glob

    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(os.path.join(h, "name")) == "rpi_volt":
            p = os.path.join(h, "in0_lcrit_alarm")
            if os.path.exists(p):
                return p
    return None


def throttled():
    try:
        out = subprocess.run(
            ["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2
        ).stdout
        return out.strip().split("=", 1)[1]
    except Exception:
        return None


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "walk"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.expanduser("~/walklogs/power-%s-%s.csv" % (label, stamp))

    lcrit_path = find_lcrit()
    if lcrit_path is None:
        print("no rpi_volt hwmon; falling back to get_throttled only", file=sys.stderr)

    fl = FlightLog(path, fields=("up", "lcrit", "temp_c", "freq_mhz", "thr", "load1"))
    fl.start()
    fl.mark("lcrit_path=%s hz=%s" % (lcrit_path, HZ))
    print("recording -> %s" % path, flush=True)

    # kill(1) sends SIGTERM, whose default action would leave no END marker
    # and make a clean stop indistinguishable from a brownout.
    def _term(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _term)

    reason = "clean"
    i = 0
    last_lcrit = None
    thr = throttled()
    try:
        period = 1.0 / HZ
        nxt = time.time()
        while True:
            i += 1
            lc = read(lcrit_path) if lcrit_path else None
            if lc is not None and lc != last_lcrit:
                # The transition is the event. Record it the instant it happens,
                # not on the next scheduled sample.
                fl.mark("LCRIT %s -> %s" % (last_lcrit, lc))
                last_lcrit = lc

            if i % THR_EVERY == 1:
                thr = throttled()

            t = read(TEMP)
            f = read(FREQ)
            fl.sample(
                i,
                up=read("/proc/uptime").split()[0] if read("/proc/uptime") else None,
                lcrit=lc,
                temp_c=round(int(t) / 1000.0, 1) if t else None,
                freq_mhz=int(f) // 1000 if f else None,
                thr=thr,
                load1=os.getloadavg()[0],
            )

            nxt += period
            time.sleep(max(0.0, nxt - time.time()))
    except KeyboardInterrupt:
        reason = "interrupt"
    except Exception as e:
        reason = "%s: %s" % (type(e).__name__, e)
        raise
    finally:
        fl.close(reason)
        print("\nstopped (%s) -> %s" % (reason, path), flush=True)


if __name__ == "__main__":
    main()
