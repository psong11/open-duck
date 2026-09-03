"""Fall detection from the gravity vector. Ships disarmed.

The IMU already knows which way is down -- it is columns 3-5 of the policy's
own observation -- so a fall needs no camera, no network and no second
machine. The angle between gravity now and gravity when she was standing is
the whole detector.

    tilt = angle(accelero, reference)     0 = as tared, 90 = on her side

TWO THINGS KEEP THIS FROM KILLING GOOD RUNS

1. Gravity has to dominate. A walking robot accelerates itself, and during a
   hard footfall the measured vector does not point at the floor. Samples
   outside a band around 9.81 are discarded rather than believed.

2. It has to persist. One bad sample is noise; a fall lasts. The tilt must
   stay over the threshold for FALL_TICKS consecutive *valid* samples before
   anything fires, and the latch resets only after it comes back under a
   lower release angle, so a duck hovering at the threshold reports once.

DISARMED BY DEFAULT
    poll() returns a message for the flight log and nothing else. Only with
    DUCK_FALL_ARM=1 does the caller stop the walk. Run it in shadow first,
    compare its marks against what actually happened, and arm it once it has
    never fired on a run that was upright.

REQUIRES A TARE
    Without ~/fall_reference.json there is no reference pose, and a guessed
    one is worse than none: on this robot the resting pose sits 32.7 deg away
    from a naive "+Z is up" assumption, so a 45 deg threshold against +Z
    would trip on a duck standing perfectly still. Missing file = disabled,
    loudly, and the walk runs exactly as it did before.

        python fall_check.py --tare      # hold her standing, once

ENV
    DUCK_FALL_DEG    trigger angle, default 50
    DUCK_FALL_REL    release angle for the latch, default 35
    DUCK_FALL_TICKS  consecutive valid samples required, default 8 (~0.16 s)
    DUCK_FALL_ARM    1 to actually stop the walk, default 0 (shadow)
"""

import json
import os

import numpy as np

REF_PATH = os.path.expanduser("~/fall_reference.json")

# Outside this band the duck is accelerating hard enough that the vector is
# not gravity any more and the angle means nothing.
G_LO, G_HI = 7.5, 12.0


class FallWatch:
    def __init__(self):
        self.deg = float(os.environ.get("DUCK_FALL_DEG", 50.0))
        self.rel = float(os.environ.get("DUCK_FALL_REL", 35.0))
        self.ticks = int(os.environ.get("DUCK_FALL_TICKS", 8))
        self.armed = os.environ.get("DUCK_FALL_ARM", "0") == "1"

        self.ref = None
        if os.path.exists(REF_PATH):
            try:
                with open(REF_PATH) as f:
                    v = np.array(json.load(f)["reference"], dtype=float)
                n = float(np.linalg.norm(v))
                if n > 1e-6:
                    self.ref = v / n
            except Exception as e:
                print("[FALL] could not read %s: %s" % (REF_PATH, e))

        if self.ref is None:
            print("[FALL] no %s -- fall detection DISABLED." % REF_PATH)
            print("[FALL] run: python fall_check.py --tare")
        else:
            print("[FALL] %s at %.0f deg for %d ticks (release %.0f)"
                  % ("ARMED" if self.armed else "shadow",
                     self.deg, self.ticks, self.rel))

        self.tilt = 0.0        # last valid tilt, degrees
        self._over = 0         # consecutive valid samples over threshold
        self._latched = False  # reported this crossing already
        self._max = 0.0        # peak since the last take_max()
        self._pending = None   # message waiting for poll()

    def update(self, accel):
        """Called once per control tick with the raw accelerometer vector."""
        if self.ref is None:
            return
        a = np.asarray(accel, dtype=float)
        n = float(np.linalg.norm(a))
        if not (G_LO < n < G_HI):
            return  # self-acceleration; this sample says nothing about down
        self.tilt = float(
            np.degrees(np.arccos(np.clip(np.dot(a / n, self.ref), -1.0, 1.0)))
        )
        self._max = max(self._max, self.tilt)

        if self.tilt >= self.deg:
            self._over += 1
        else:
            self._over = 0
            if self.tilt < self.rel:
                self._latched = False  # back upright; allow the next report

        if self._over >= self.ticks and not self._latched:
            self._latched = True
            self._pending = "fall tilt=%.0fdeg%s" % (
                self.tilt, "" if self.armed else " (shadow)"
            )

    def poll(self):
        """Return a one-shot message if a fall just crossed, else None."""
        m, self._pending = self._pending, None
        return m

    def take_max(self):
        """Peak tilt since the last call. For the flight log."""
        m, self._max = self._max, self.tilt
        return round(m, 1)
