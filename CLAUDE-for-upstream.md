# Building an Open Duck Mini v2 — context for an AI assistant

Drop this in the repo root as `CLAUDE.md` (or `AGENTS.md`). It encodes hardware
traps learned by breaking things on a real build, so an assistant does not
rediscover them at the user's expense.

Every number here was measured on hardware.

---

## Ground rules for this project

**This is hardware. A wrong command has physical consequences.** A servo driven
to a bad position pushes against an assembly until something strips. Before
commanding motion, know how far each joint will travel and whether anything
will stop it.

**Never state a hardware fact from recall.** Check it, or label it a guess in
the same sentence. On this build, confident-but-wrong claims about jumper
positions, mDNS names, MAC OUIs, and "the SD card is dying" each cost hours.

**Prefer read-only.** Every diagnostic that can be a `get_*` should be. Say so
explicitly in the script and in what you tell the user — "this commands no
motion" is worth writing down when someone is holding the robot.

**Test at the magnitude you will actually use.** A mechanism verified at 10°
may behave differently at 170°; on the EEPROM offset register it does, because
of a sign-encoding seam. If it has a sign, test both signs.

**Instrument before the next failure, not after.** For anything intermittent,
build the recorder first. The user's time and attention are the scarce
resource, not tokens — do not ask them to run the same one-bit check twice.

---

## Power topology — read this before diagnosing anything electrical

```
2x 18650 → BMS → switch ─┬─→ barrel jack → servo board → 14 servos   (raw 7.4V)
                         └─→ UBEC → 5V → Raspberry Pi                (regulated)
```

**Servos and the Pi are on different rails.** Almost every confusing symptom
resolves once that is clear:

- The Pi can die while the servos keep holding — they never lost power.
- **A dead Pi leaves the robot RIGID, not limp.** The servos hold their last
  goal at full torque, indefinitely. Nothing over the network can release them.
- **The only real emergency stop is the physical power switch.** A script that
  releases torque runs on the Pi — the machine that just failed. Never present
  it as the primary kill switch.
- The UBEC reading solid *after* a failure is not evidence it never faltered.
  With the Pi dead its load is ~nothing, so it looks healthy.

### Power budget (measured)

| state | pack | outcome |
|---|---:|---|
| idle, torque off | 7.0 V | stable for hours |
| holding a static pose | 7.0 V | brownout after minutes |
| walking | 7.7 V | brownout in seconds |

Calibration is heavier than it looks: every joint the user approves leaves
torque **engaged**, so draw climbs monotonically. **Tell the user to charge
fully (8.4 V) before calibrating or walking.**

### `vcgencmd get_throttled` has a blind spot

It needs the SoC still *running* at a degraded voltage to latch anything. A rail
that collapses outright leaves `0x0`. On this build it read `0x0` through every
one of three brownouts. **A clean throttle reading is not evidence power was
fine.**

### Never hot-plug the barrel jack

The servo board's bulk capacitance is empty; connecting it to a live pack is a
near short. Measured sag 6.56 V → ~3 V, which drops the UBEC out and kills the
Pi instantly. Connect with the switch **off**, then switch on.

---

## Servos (Feetech STS3215)

- Unconfigured motors **all answer to id 1**. Configure one at a time.
- EEPROM writes need `set_lock(0)` → write → `set_lock(1)`.
- **Reading a write back on the same connection proves nothing.** Reconnect and
  re-read. A dropped write on this build reported success while the register
  kept its factory value.
- An **uncommanded** servo reports `goal_position = −180.0` (raw 0). If anything
  enables torque before goals are written, every joint lurches toward −180.
  Write `goal = present` first — with torque off that moves nothing.
- Angle limits on this build were `[−180, 180]` on all 14: **no limits.** The
  firmware will not stop anything; the assembly is the only stop.
- Phase 0 sets `acceleration=0`, `max_acceleration=0`, PID `32/0/0` — no
  acceleration limiting and no damping, deliberately, so the policy has direct
  authority. Consequence: **large single commands snap.** That config is tuned
  for small 50 Hz steps, not for one 100° move.

### The offset register (address 31) — sign-encoding trap

Shifts reported *and* commanded positions, in servo firmware, persisting in
EEPROM. Ideal for a horn installed out of true — no disassembly, no runtime cost.

**`pypot` reads it with a Dynamixel linear map; Feetech encodes it as
sign-magnitude around raw 2048.** The halves diverge:

| written | actual shift |
|---:|---:|
| `+10` / `+90` / `+170` | matches, 1:1 |
| `+180` | clean ±180 wrap |
| **`−170`** | **`−10`** |

Negative `X` gives `−(180 + X)`. **Stay in the positive half**; the wrap reaches
everything. A resting `get_offset()` of `−180.0` means raw 0 — *no offset*.

---

## Software environment

- Pi OS **trixie ships Python 3.13 and no pip**. Runtime pins
  `onnxruntime==1.18.1` / `numpy==1.26.4`, which have **no cp313 aarch64
  wheels**. Use Miniforge with Python **3.11**.
- `pypot` pulls a **58 MB OpenCV** the servo path never uses. It imports only
  `cv2`, `numpy`, `serial`. Install **`opencv-contrib-python-headless`** — the
  normal build needs GTK/X11 that Pi OS Lite lacks, and fails as a confusing
  `ModuleNotFoundError: cv2`.
- **`/tmp` is a ~208 MB RAM disk.** pip unpacks there and hits `No space left on
  device` while `df -h /` shows tens of gigabytes free. Set `TMPDIR`.
- A wheel must keep its canonical filename. Renaming it gets
  `Invalid wheel filename (wrong number of parts)`.

## Networking / Bluetooth

- The Pi Zero 2W has **no RTC**: `ts=` in logs is wrong until NTP syncs, and a
  new boot's entries can appear to *precede* the previous boot's. Reason with
  uptime, not wall clock. Never index boot sections positionally.
- **Wifi associates at ~43 s** after boot on this hardware. A check that gives
  up sooner is measuring its own impatience.
- Bluetooth on a fresh image is **rfkill soft-blocked**; `bluetoothctl power on`
  fails with the useless `org.bluez.Error.Failed` while the hardware is fine.
- **Game controllers use Bluetooth Classic.** `bluetoothctl scan on` shows BLE
  only; use `hcitool scan`.
- Xbox-protocol pads need **ERTM disabled**.
- **Bonding needs a pairing agent.** `bluetoothctl` fed from a pipe fails to
  register one, which presents as `AuthenticationFailed` — connects but never
  bonds, so no `/dev/input/js*`. Use `bt-agent -c NoInputNoOutput`.
- BlueZ only treats a device as available **while a scan is live**. Discover and
  pair in one continuous window.
- The Pi Zero 2W shares **one antenna** between wifi and Bluetooth. Range is
  genuinely poor with SSH active.

## Runtime quirks

- `--commands` is `store_true` with `default=True` — it can never be false, so
  the runtime always demands a physical gamepad. Change the default to `False`
  and the policy runs on a zero velocity command: **the duck balances in place**,
  which is the better first test.
- `HWI.joints` is ordered **left leg → head → right leg**, and
  `get_present_positions()` returns that order. Comparing it against an
  id-ordered list by index produces a screenful of false disagreements.
- The walk's `KeyboardInterrupt` handler **does not release torque**.
- `find_soft_offsets.py` saves nothing; it prints offsets for manual copying.
  Its first action drives every joint to zero — check the travel first.

---

## Debugging posture

**Debug outward from power.** The first total failure on this build — a
completely silent servo bus, every baud rate, every address — was one 18650 not
touching its contact.

**Give the robot a black box.** The boot partition is FAT32 and readable by any
computer. Have the Pi record its own state there: undervoltage, wifi
*association* separately from *DHCP lease*, read-only-root, and a clean-shutdown
marker. When the Pi stops answering the network, the network is the last thing
you can ask.

**Distinguish states that look identical from outside.** "Never joined the
network" and "joined but got no lease" are different bugs; `ping` cannot tell
them apart.

**Absence of an artifact is evidence.** A log file missing after a crash bounds
the run: ext4 commits every 5 s, so a file that never appeared means the process
died inside that window.

**Recovery must not destroy the record of the failure.** A per-boot log that
overwrites itself will be clobbered by the boot that comes asking what went
wrong. Preserve the previous one first.
