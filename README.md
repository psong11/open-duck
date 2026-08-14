# open-duck

My Open Duck Mini v2 — a knee-high BDX droid that learns to walk in simulation,
then walks in my apartment.

Started 2026-08-14. Kit in hand.

---

## The mental model

Three things, and one file that connects them.

**The body** — printed shell, 14 Feetech STS3215 servo motors, a tilt sensor.
Assembled by hand.

**The brain** — a Raspberry Pi Zero 2W in its chest. Many times a second it asks
*"where are my joints, which way am I tilted?"* and answers *"put the joints
here."* It does not plan. It reacts.

**The school** — a GPU machine where the brain gets made. A simulated duck
attempts to walk a few million times and gets scored on staying upright.

The school produces **one file** (a `.onnx` policy). Copy it onto the brain.
The duck walks.

> Everything in this project is either *making that file* or *running that file*.
> When lost, figure out which one you're doing.

---

## The arc

| Phase | What happens | Status |
|---|---|---|
| **0. Wake the motors** | Each of the 14 servos gets a numbered identity before anything is assembled | ← here |
| **1. Give it a body** | Assembly. Wiring, Loctite, calibration | |
| **2. Borrowed brain** | Drop in the community's pretrained policy. It walks | |
| **3. Its own brain** | Build the school. Train a policy myself. Sim-to-real | |
| **4. Personality** | Eyes, speaker, mic, camera, antennas | |

Phase 2 is the checkpoint that matters most. A duck walking on a borrowed brain
proves the soldering, motor IDs, offsets, and wiring are all correct — *before*
any reinforcement learning is in the picture. Debugging both at once is how
people lose months.

---

## Layout

```
config/     duck_config.json — joint offsets + hardware flags.
            Backed up here because it lives in $HOME on the Pi and
            dies with the SD card.
policies/   .onnx brains, named by where they came from.
vendor/     upstream repos, cloned and pinned. Not my code.
NOTES.md    the dense technical reference. Versions, platform traps,
            the ways people lose a weekend.
```

---

## Build log

### 2026-08-14 — day zero
Repo created. Kit in hand, nothing assembled yet.

Phase 0 toolchain up on the Mac:
- `uv` installed (`~/.local/bin`), fetched CPython **3.11.16** into `.venv`
- `vendor/Open_Duck_Mini_Runtime` cloned at branch `v2`, commit `3203734`
- `pypot` 5.0.2 (pollen-robotics `support-feetech-sts3215` branch) installed;
  `from pypot.feetech import FeetechSTS3215IO` imports clean on Apple Silicon

Only `pypot` is installed, not the full runtime — the runtime pins
`onnxruntime==1.18.1`, which has no macOS arm64 wheel. Motor config doesn't
need it. Full runtime install happens on the Pi.

**Hardware confirmed:** servo board is a WCH CH343 (VID `0x1A86`), enumerates
natively on macOS — no vendor driver. Port is `/dev/cu.usbmodem5B901489761`.
Use the `cu.` path, never `tty.`: on macOS `tty.` blocks on open waiting for a
carrier signal a servo board never sends.

**Motor config** — one motor on the bus at a time (unconfigured motors all
answer to id 1, so two at once talk over each other):

```bash
./scripts/name_motor.sh right_hip_yaw   # joint name -> id, then configure
./scripts/name_motor.sh --list          # show all 14
./scripts/probe_bus.py                  # read-only: who's on the bus, at what voltage
```

#### First-light debugging (worth remembering)
Motor was silent at every baud rate and every address. Cause: **one 18650 not
seated against its contact.** The servo bus is 3 wires — V+, GND, signal — with
no separate logic supply, so an unpowered bus means a dead MCU and total
silence, not a degraded response.

The board's USB-C carries **data only**. Servo power comes from the separate
7.4V DC input, fed from the pack through the BMS and the inline power switch.
See `docs/wiring_diagram_v2.png`. Debug outward from the battery, not inward
from the software.

#### Motor progress — 5 / 14
- [x] **right leg** — `10` hip_yaw · `11` hip_roll · `12` hip_pitch · `13` knee · `14` ankle
- [ ] **left leg** — `20` hip_yaw · `21` hip_roll · `22` hip_pitch · `23` knee · `24` ankle
- [ ] **neck + head** — `30` neck_pitch · `31` head_pitch · `32` head_yaw · `33` head_roll

Every motor probed clean at id 1 with factory defaults before its write. Pack
held 7.2–7.3V throughout (floor is 4.0V).

