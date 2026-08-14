# NOTES — the dense reference

Everything researched 2026-08-14, before assembly. Read the section you need,
when you need it. Not meant to be read front to back.

---

## Upstream repos

Four of them. Note the non-default branches.

| Repo | Branch | Runs where | Purpose |
|---|---|---|---|
| [`Open_Duck_Mini`](https://github.com/apirrone/Open_Duck_Mini) | `v2` | anywhere | Hub: STLs, CAD, BOM, docs, **pretrained `BEST_WALK_ONNX_2.onnx`** |
| [`Open_Duck_Mini_Runtime`](https://github.com/apirrone/Open_Duck_Mini_Runtime) | **`v2`** | the Pi | Motor config, IMU, ONNX inference, gamepad, the walk |
| [`Open_Duck_Playground`](https://github.com/apirrone/Open_Duck_Playground) | `main` | Linux + NVIDIA **only** | MJX/JAX training → exports ONNX |
| [`Open_Duck_reference_motion_generator`](https://github.com/apirrone/Open_Duck_reference_motion_generator) | `main` | Linux x86_64 **only** | Placo walk engine → `polynomial_coefficients.pkl` |

`Open_Duck_Mini_Runtime` defaults to `main`, which is stale. **Always
`git checkout v2`.** Same for the hub repo (its default *is* `v2`, but confirm).

`Open_Duck_reference_motion_generator` uses **git-lfs** for its meshes. Install
git-lfs before cloning or you get pointer files and a confusing Placo error
about "mesh directory may be wrong." Recovery: `git lfs pull`.

---

## Platform reality — what runs where

### This Mac (arm64, Python 3.14 system)
- ✅ Motor configuration (Phase 0) — needs only `pypot`, not the whole runtime
- ✅ MuJoCo simulation viewing / CPU inference
- ❌ **Cannot** install the full runtime: `onnxruntime==1.18.1` has no macOS
  arm64 wheel at all
- ❌ **Cannot** train: `Open_Duck_Playground` declares `jax[cuda12]`
  unconditionally, which has no macOS build
- ❌ **Cannot** generate reference motions: pinned `placo==0.6.3` ships a
  **cp310 manylinux x86_64 wheel only** — no macOS build exists at that version

**Use Python 3.11 on the Mac**, not 3.14 and not 3.12. `rustypot==0.1.0` only
publishes a macOS arm64 wheel for cp311, and `numpy==1.26.4` tops out at cp312.
3.11 is the only version where the pinned set resolves.

### The Pi Zero 2W
- Raspberry Pi OS **Lite 64-bit**. Pre-configure wifi + SSH in the Imager
- Enable I2C: `sudo raspi-config` → Interface Options → I2C
- usb-serial latency rule, or the servo bus jitters:
  `/etc/udev/rules.d/99-usb-serial.rules` →
  `SUBSYSTEM=="usb-serial", DRIVER=="ftdi_sio", ATTR{latency_timer}="1"`
- On a Pi 5 (not our board): `pip uninstall RPi.GPIO && pip install lgpio`

### Training (Phase 3) — nothing I own can do this
Needs **Linux + NVIDIA**. The Jetson Orin Nano is the wrong tool (JAX/CUDA on
JetPack aarch64 is unsupported territory, and 8GB is tight). Plan on a rented
cloud GPU for a few hours. **Prefer a 4090 over a 50-series** — there's an open
issue where RTX 50xx hits `CUDA_ERROR_INVALID_HANDLE` with this repo's
TensorFlow pin.

---

## The version trap (will break Phase 3 on day one)

`Open_Duck_Playground/pyproject.toml` declares `playground>=0.0.3`. PyPI's
latest is **0.2.0**, and the repo does not work with it — you get:

```
ModuleNotFoundError: No module named 'mujoco_playground._src.collision'
```

Community-confirmed fix ([issue #25](https://github.com/apirrone/Open_Duck_Playground/issues/25)),
pin in the fork:

```toml
playground==0.0.5
jax[cuda12]==0.8.0
```

Also worth applying [PR #23](https://github.com/apirrone/Open_Duck_Playground/issues/23)'s
platform marker so the repo at least installs on a Mac:

```toml
"jax[cuda12]>=0.5.0; sys_platform == 'linux'",
```

> `uv` is the package manager all four repos use. It writes a `uv.lock` file
> recording the exact version of every dependency it resolved. Commit that file
> — it's the difference between "works today" and "works in six months."

---

## Upstream is effectively frozen

| Repo | Last push |
|---|---|
| `Open_Duck_Mini_Runtime` | Jul 2026 |
| `Open_Duck_Mini` | Jan 2026 |
| `Open_Duck_Playground` | **Aug 2025** |

Antoine Pirrone's active 2026 work is a successor called **microduck** —
Dynamixel XL330 motors, Rust runtime, PWA companion app, on-device pet-detection
audio classifier. Pushed within the last day as of 2026-08-14.

This is not abandonment; Open Duck Mini v2 is mature and heavily forked (441
forks, 3.4k stars, active Discord). But treat upstream as **frozen**: fork
everything, pin commit SHAs, don't wait on fixes.

Discord: https://discord.gg/UtJZsgfQGe

---

## Hardware facts

- 14× Feetech STS3215 **7.4V** serial-bus servos
- Raspberry Pi Zero 2W (512MB), BNO055 9-DOF IMU, Waveshare servo bus board
- 2× 18650 in 2S with BMS; get high-discharge cells (30A)
- ~42cm tall legs extended

### Motor IDs
```
left_hip_yaw   20     right_hip_yaw   10     neck_pitch  30
left_hip_roll  21     right_hip_roll  11     head_pitch  31
left_hip_pitch 22     right_hip_pitch 12     head_yaw    32
left_knee      23     right_knee      13     head_roll   33
left_ankle     24     right_ankle     14
```
A brand-new motor ships as **ID 1**. `configure_motor.py` scans if it can't find
ID 1, so it handles already-configured motors too.

### Assembly traps
- **Configure every motor before assembling.** The motor drives to zero during
  config and that's when the horn goes on. Doing this inside a closed body is
  miserable.
- Blue Loctite 243 on every metal-to-metal screw. **Never** on plastic screws.
- Left/right leg parts are true mirrors — not interchangeable.
- `foot_bottom_tpu.stl` in TPU at 40% infill for grip. Everything else PLA 15%.

### Calibration — back this up
`duck_config.json` lives in `$HOME` on the Pi, generated with help from
`scripts/find_soft_offsets.py`. It holds your duck's specific joint offsets.
**Copy it into `config/` in this repo.** If the SD card dies without a backup,
you re-calibrate 14 joints by hand.

---

## Commands worth remembering

```bash
# Phase 0 — one motor at a time, before assembly
python configure_motor.py --id 20 --port /dev/tty.usbmodem*   # macOS
                                   # /dev/ttyACM0 on Linux/Pi

# Phase 1 — verify after assembly
python scripts/check_motors.py
python mini_bdx_runtime/mini_bdx_runtime/raw_imu.py

# Phase 2 — walk on the borrowed brain
python scripts/v2_rl_walk_mujoco.py --onnx_model_path <path>.onnx
```

Gamepad while walking: A = pause/unpause · X = projector · B = sound ·
LB (hold) = sprint · Y = head control (*known to break heads, avoid*)

---

## Sources

- Hub / docs: https://github.com/apirrone/Open_Duck_Mini
- sim2real writeup: https://github.com/apirrone/Open_Duck_Mini/blob/v2/docs/sim2real.md
- TNKR build guide (43 steps, 3D viewer): https://tnkr.ai/explore/docs/open-duck-mini/open-duck-mini-v2
- BOM: https://docs.google.com/spreadsheets/d/1gq4iWWHEJVgAA_eemkTEsshXqrYlFxXAPwO515KpCJc
- CAD (Onshape): https://cad.onshape.com/documents/64074dfcfa379b37d8a47762
