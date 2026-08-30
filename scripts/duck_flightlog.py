"""Flight recorder for the walk control loop.

The walk browns out in seconds and takes the Pi down with it, so anything
still sitting in a buffer at the moment of death is gone. Two rules follow:

  * the control loop must never block on the disk, and
  * every sample that reaches the disk must be durable immediately.

The loop hands samples to a queue and a writer thread fsyncs each one.
Worst case we lose the single sample in flight, and the timestamps say
exactly where the record stops.

Deliberately knows nothing about the servo bus. The rustypot binding the
runtime uses exposes only position and velocity -- no voltage, no load --
and a second process opening /dev/ttyACM0 to get them would interleave
packets with the walk. Rail voltage is somebody else's job (powerwatch.sh);
this records what the loop itself can see, which turns out to be the more
useful half: tracking error blows up before the Pi dies.

The last line of a healthy run is "### END". If the file just stops, the
Pi died mid-stride -- absence of the terminator is the finding.

    with FlightLog("~/walklogs/walk.csv", fields=("dt_ms", "err", "verr")) as fl:
        while True:
            ...
            fl.sample(i, dt_ms=took * 1e3, err=tracking_err, verr=vel_err)
"""

import os
import queue
import threading
import time


class FlightLog:
    def __init__(self, path, fields=("dt_ms",), maxq=8192):
        self.path = os.path.expanduser(path)
        self.fields = tuple(fields)
        self.q = queue.Queue(maxsize=maxq)
        self.t0 = time.time()
        self.n = 0
        self.dropped = 0
        self._stop = threading.Event()
        self._thread = None
        self._closed = False

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        self._thread = threading.Thread(target=self._writer, daemon=True)
        self._thread.start()
        self._put(
            "### START wall=%s up=%s pid=%d"
            % (time.strftime("%Y-%m-%dT%H:%M:%S"), _uptime(), os.getpid())
        )
        self._put("# t_s,i," + ",".join(self.fields))
        return self

    def close(self, reason="clean"):
        if self._closed:
            return
        self._closed = True
        self._put(
            "### END reason=%s samples=%d dropped=%d elapsed=%.2f"
            % (reason, self.n, self.dropped, time.time() - self.t0)
        )
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.close("clean" if exc_type is None else exc_type.__name__)
        return False

    # -- recording ---------------------------------------------------------

    def sample(self, i, **vals):
        self.n += 1
        cells = []
        for f in self.fields:
            v = vals.get(f)
            cells.append("" if v is None else _fmt(v))
        self._put("%.3f,%d,%s" % (time.time() - self.t0, i, ",".join(cells)))

    def mark(self, text):
        self._put("### %s t=%.3f" % (text, time.time() - self.t0))

    # -- internals ---------------------------------------------------------

    def _put(self, line):
        try:
            self.q.put_nowait(line)
        except queue.Full:
            # Dropping a sample beats stalling the control loop.
            self.dropped += 1

    def _writer(self):
        with open(self.path, "a", buffering=1) as f:
            fd = f.fileno()
            while True:
                try:
                    line = self.q.get(timeout=0.2)
                except queue.Empty:
                    if self._stop.is_set():
                        return
                    continue
                f.write(line + "\n")
                f.flush()
                os.fsync(fd)


def _fmt(v):
    if isinstance(v, float):
        return "%.4f" % v
    return str(v)


def _uptime():
    try:
        with open("/proc/uptime") as f:
            return f.read().split()[0]
    except OSError:
        return "?"
