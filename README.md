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

**Motor config command** (one motor on the bus at a time):
```bash
cd ~/Documents/personal_projects/open-duck
.venv/bin/python vendor/Open_Duck_Mini_Runtime/scripts/configure_motor.py \
    --id <id> --port <port>
```

