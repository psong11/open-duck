# Contributions back to Open Duck Mini

Findings from one full build of an Open Duck Mini v2 (TNKR kit, Raspberry Pi
Zero 2W, Pi OS trixie), written up so they are useful to
[`apirrone/Open_Duck_Mini_Runtime`](https://github.com/apirrone/Open_Duck_Mini_Runtime)
rather than only to me.

Every claim below was measured on hardware, not inferred. Where a number
appears, it came off this robot.

---

## 1. Flashing joint offsets to servo EEPROM — the open TODO

`TODO.md` says:

> `[] Make the offsets flashing work. This will be in the motor configuration script`

and `README.md` says:

> *This procedure won't be necessary in the future as we will be flashing the
> offsets directly in each motor's eeprom.*

**This works today, and there is a trap in it worth documenting before anyone
else implements it.**

The STS3215 exposes a position-correction register at **address 31**, 2 bytes,
in the EEPROM range. Writing it shifts both reported *and* commanded positions —
verified: with a `+90` offset applied, commanding `97.00` reached `96.22`, so
goal and present share one frame. The correction is applied in servo firmware,
so the control loop pays nothing per timestep.

Write pattern matches the existing config scripts: `set_lock(0)` → write →
`set_lock(1)`.

### The trap

`pypot` applies a **Dynamixel** linear conversion to this register, but Feetech
encodes it as **sign-magnitude around raw 2048**. The two agree on the positive
half and diverge on the negative half. Measured on `head_yaw`:

| written | actual shift |
|---:|---:|
| `+10` | `+9.94` |
| `+90` | `+90.02` |
| `+170` | `+169.93` |
| `+180` | `−180.13` (same rotation, clean wrap) |
| **`−170`** | **`−10.03`** ← not `−170` |

For negative `X` the real shift is `−(180 + X)`. So `−171°` requires writing
`−9`.

**Recommendation:** stay in the positive half and let the ±180 wrap reach
everything else. A helper should refuse negative values outright rather than
silently writing a wrong correction into EEPROM.

Also note: a resting `get_offset()` reads **`−180.0`**, which is raw 0 — *no
offset*. It is easy to misread as "a 180° correction is already applied."

### Real-world use

Both hip pitch horns on this build went on half a turn out, leaving those joints
against the ±180 wraparound. `+180` written to ids 12 and 22 moved them to
`+3.56°` and `−6.73°`. Verified across a full power cycle. No disassembly.

Reference implementation: `scripts/write_offset.py`.

---

## 2. Bugs with one-line fixes

### `--commands` can never be false

`scripts/v2_rl_walk_mujoco.py`:

```python
parser.add_argument("--commands", action="store_true", default=True, ...)
```

`store_true` with `default=True` means the flag can only set it to what it
already is. There is no way to disable command input, so the runtime always
constructs an `XBoxController` and always calls `pygame.joystick.Joystick(0)` —
which raises if no pad is attached.

```diff
-        default=True,
+        default=False,
```

With that, omitting the flag leaves `last_commands` at `[0.0] * 7` and the
policy runs on a zero velocity command: **the duck balances in place.** That is
a much better first bring-up test than requiring a gamepad, because it separates
*can it stand* from *can it travel*.

### The walk's `KeyboardInterrupt` handler does not release torque

`v2_rl_walk_mujoco.py` catches `KeyboardInterrupt`, stops antennas/eyes/
projector/feet_contacts, and falls through. `hwi.turn_off()` is never called, so
Ctrl-C leaves the robot **rigid at full torque**, still drawing current.

Suggest `finally: self.hwi.turn_off()`.

### `find_soft_offsets.py` has no `finally`

Same class of problem: it catches `KeyboardInterrupt` only. Any other exit — an
unhandled exception, a USB re-enumeration — leaves torque engaged on an
assembled robot.

It also **saves nothing**; it prints offsets and asks the user to copy fourteen
decimal numbers into JSON by hand. Writing them directly (with a backup) removes
a transcription step where one wrong digit produces a limp nobody can explain.

### The usbserial latency rule targets the wrong driver

`README.md`:

```
SUBSYSTEM=="usb-serial", DRIVER=="ftdi_sio", ATTR{latency_timer}="1"
```

The TNKR servo board is a **WCH CH343** (`1a86:55d3`) and binds to **`cdc_acm`**,
not `ftdi_sio`. This rule never matches. Confirmed in `dmesg`:

```
cdc_acm 1-1:1.0: ttyACM0: USB ACM device
```

Either the rule needs a `cdc_acm` variant or the README should note it applies
only to FTDI-based boards.

### `README.md` references a file that does not exist

The `--commands` help text says *"Launch control_server.py on host computer."*
There is no `control_server.py` in this repository. Anyone without a gamepad
will go looking for it.

### `configure_motor.py` cannot detect a dropped EEPROM write

It reads its own writes back **within the same connection**, which proves
nothing about whether they landed in EEPROM. On this build, motor `30`
(`neck_pitch`) reported success while `max_acceleration` silently stayed at the
factory `50`. It surfaced only because a human noticed one number looked
different from the ten before it.

Reconnecting before verifying catches this. Reference:
`scripts/verify_motor.py`.

---

## 3. Documentation gaps that cost real hours

None of these are code bugs; all of them are walls a builder hits with no
signpost.

### Pi OS trixie ships Python 3.13 and no pip

The runtime pins `onnxruntime==1.18.1` and `numpy==1.26.4`. Checked against
PyPI's file lists: **neither has a cp313 aarch64 wheel** (both stop at cp312).
`onnxruntime` gains cp313 aarch64 wheels at **1.20.0**. trixie has no
`python3.11` package and the image ships no `pip` (only `venv`).

Working recipe:

```bash
wget -O /tmp/Miniforge3.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh
bash /tmp/Miniforge3.sh -b -p ~/miniforge3
~/miniforge3/bin/conda create -y -n duck python=3.11
```

### `pypot` drags in a 58 MB OpenCV the servo path never uses

Watching `sys.modules`, `FeetechSTS3215IO` imports only `cv2`, `numpy`, and
`serial`. Not `scipy`, not `ikpy`.

Worse: the **non-headless** OpenCV wheel links against GTK/X11, which Pi OS Lite
does not have — so even a successful download dies at `import cv2`, and the
error looks like a pypot bug rather than a missing system library.

```bash
pip install opencv-contrib-python-headless
pip install --no-deps "pypot @ git+..."
```

### `/tmp` is a 208 MB RAM disk

`pip` unpacks into `/tmp`. Installing numpy + onnxruntime hit
`[Errno 28] No space left on device` while `df -h /` reported **24 GB free** —
because the constraint was a different mount. Set `TMPDIR` somewhere real.

### Bluetooth: four separate walls, none documented

The README's controller section assumes pairing just works. On a fresh image it
does not:

1. **rfkill soft-blocks the adapter.** `bluetoothctl power on` fails with the
   uninformative `org.bluez.Error.Failed` while `hciconfig` shows `hci0` healthy
   with firmware loaded. The block is at `/sys/class/rfkill/*/soft`, and the
   `rfkill` CLI is not installed.
2. **Game controllers use Bluetooth Classic.** `bluetoothctl scan on` surfaces a
   screenful of BLE lightbulbs and never the pad. `hcitool scan` does a classic
   inquiry.
3. **Xbox-protocol pads need ERTM disabled** on Linux:
   `echo Y > /sys/module/bluetooth/parameters/disable_ertm`.
4. **Bonding requires a registered pairing agent.** `bluetoothctl` driven from a
   pipe fails to register one (`Failed to register agent object`), which
   presents as `org.bluez.Error.AuthenticationFailed` — the device *connects*
   but never bonds, so the HID profile never attaches and no `/dev/input/js*`
   appears. `bt-agent -c NoInputNoOutput` works.

Also: BlueZ only treats a device as available **while a scan is live**, and
evicts unpaired devices it stops hearing. Discovery and pairing must happen in
one continuous window, not as separate commands.

And the Pi Zero 2W shares **one antenna** between wifi and Bluetooth. With an
SSH session active, the controller had to be held against the duck's head to be
seen at all.

Reference: `scripts/pair_controller.sh`.

### There is no stated power budget

Measured on this build, two 18650s through a BMS and a UBEC:

| state | pack voltage | outcome |
|---|---:|---|
| idle, torque off | 7.0 V | stable for hours |
| holding a static pose | 7.0 V | browned out after minutes |
| **walking** | **7.7 V** | **browned out in seconds** |

Every joint approved in `find_soft_offsets.py` leaves torque *engaged*, so draw
climbs monotonically through calibration — it is a far heavier operation than it
looks.

A "charge fully before calibrating or walking" line in the README would save
people a confusing evening.

### Two safety facts that belong in the README

**The servos are on the raw battery rail; only the Pi is behind the regulator.**
So when the Pi browns out, the servos keep their last goal at full torque,
indefinitely. **A dead Pi leaves the robot rigid, not limp**, and nothing over
the network can release it. The physical power switch is the only real emergency
stop.

**Do not hot-plug the barrel jack.** The servo board's bulk capacitance is
empty; connecting it to a live pack is a near short. Measured sag: 6.56 V → ~3 V,
which drops the UBEC out and kills the Pi instantly. Connect with the switch
**off**, then switch on. Note that `vcgencmd get_throttled` reads `0x0` straight
through this — the rail collapses faster than the SoC can latch an undervoltage
flag, so a clean throttle reading is *not* evidence power was fine.

---

## 4. Scripts offered

All read-only unless stated. All were written and used during this build.

| script | what it does |
|---|---|
| `verify_all.py` | 14-motor acceptance test on the assembled robot. Strictly `get_*`; commands no motion. Flags missing ids, duplicates, wrong config, and joints straining against their own linkage (goal-vs-present delta with load). |
| `write_offset.py` | Writes the EEPROM position-correction register. Refuses the negative half where pypot's conversion is wrong. Verifies on a fresh connection. |
| `park_goals.py` | Writes `goal = present` on every joint. An uncommanded STS3215 reports `goal_position = −180.0`; the runtime's `turn_on()` raises gains a full second before it writes positions, so that window can lurch all fourteen joints toward −180 on an assembled robot. |
| `preflight_offsets.py` | Before `find_soft_offsets.py`: how far will each joint travel to zero, and will the servo's own angle limits stop it? (On this build every joint reported `[−180, 180]` — no limits at all. The assembly is the only stop.) |
| `torque_off.py` | Releases torque on all 14. Useful — but see rule above: it runs on the Pi, so it is not an emergency stop. |
| `goto_zero.py` | Drives to the zero pose more gently than `turn_on()`: parks goals at present *before* enabling torque, and holds at a reduced gain. |
| `pair_controller.sh` | Scan-and-pair in one continuous window, with `bt-agent` running. |
| `probe_gamepad.py` | Reports how a pad actually enumerates versus the indices the runtime hardcodes. |
| `blackbox.sh` / `bootsnap.sh` | Flight recorder writing to the **FAT boot partition**, readable from any computer with a card reader. Records undervoltage, wifi association vs. DHCP separately, read-only-root, and whether each boot ended cleanly or was killed. Diagnoses a Pi that has stopped answering the network — which is exactly when you cannot ask it anything. |

---

## 5. Suggested `CLAUDE.md` for the repository

See [`CLAUDE-for-upstream.md`](CLAUDE-for-upstream.md) — a context file for
people building this with an AI assistant, encoding the traps above so nobody's
assistant has to rediscover them by breaking hardware.
