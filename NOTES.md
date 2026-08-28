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

### Servo board (Waveshare Bus Servo Adapter A) — verified facts

**It has NO 5V output.** Waveshare's wiring docs: *"The Raspberry Pi must be
powered separately... the adapter acts as a power pass-through rather than a
voltage regulator."* It passes the 7.4V input straight to the servo bus.

> ⚠️ TNKR's assembly Step 3 table says "Servo driver board 5V → Raspberry Pi
> 5V". **That pin does not exist.** Power the Pi from the UBEC (the "5V
> Regulator" in the BOM) fed off the 7.4V rail, per
> `docs/wiring_diagram_v2.png`. When TNKR and the upstream diagram disagree,
> trust the diagram.

**Control mode jumper — leave it on B (USB).**

> ⚠️ An earlier version of this note said to move it to A (UART) for the Pi
> Zero. **That was wrong.** Waveshare's docs list "RPi Zero" under UART mode,
> but this build does not follow that advice.

Evidence this build is USB: the runtime hardcodes **`/dev/ttyACM0`** — a USB
CDC-ACM device (the CH343) — in `rustypot_position_hwi.py`,
`v2_rl_walk_mujoco.py`, `configure_motor.py` and every script. A UART path
would be `/dev/serial0` or `/dev/ttyAMA0`. The wiring diagram also draws a
line from a Pi micro-USB to the board's usb-c.

**The Pi Zero 2W has two micro-USB ports and they are not interchangeable:**

| Port | Purpose |
|---|---|
| `USB` (nearer the mini-HDMI) | **data / OTG — the servo board goes here** |
| `PWR IN` (outer end) | power only, no data lines |

Plugging the servo board into `PWR IN` gives no data path *and* creates a
supply conflict with the UBEC feeding 5V on the GPIO header. Observed
2026-08-18: with USB connected the Pi would not boot at all (ACT LED rock
steady); unplugging it let the Pi boot.

Rows 1–6 of TNKR's Step 3 table (cells → BMS → switch → board V+/GND) are
correct and were proven working on 2026-08-14.

### Battery pack wiring

`BM` is the **midpoint tap** — a wire to the metal junction where cell 1's `+`
meets cell 2's `−`. Without it the BMS sees only the 7.4V pack total and cannot
distinguish a healthy `3.7+3.7` from a dangerous `4.2+3.2`. With it:
`cell2 = B+ − BM`, `cell1 = BM − B−`. That per-cell visibility is the whole
safety function, plus it enables balancing.

`B+/B−/BM` = raw cells, always live. `P+/P−` = protected output; the BMS opens
it on a fault. Everything downstream hangs off `P`.

**The actual BMS in this build is an HW-391 2S 20A.** It labels pads by
expected voltage, not by `B±`/`BM`. See `docs/bms_pinout_annotated.png`.

| Diagram | HW-391 pad | Connect to |
|---|---|---|
| `B−` | `0V` | cell 1 negative |
| `BM` | `4.2V` | **between the two cells** |
| `B+` | `8.4V` | cell 2 positive |
| `P+` | `(+)` round pad | 7.4V out → robot |
| `P−` | `(−)` round pad | → power switch |

Pad mapping confirmed by two independent sources (HW-391 troubleshooting guide
+ product docs), not just by reading the silkscreen.

Solder the taps `0V` → `4.2V` → `8.4V`. **Caveat: no datasheet I found
specifies a required order** — this is hobby convention, not a verified spec.
It costs nothing, so do it, but don't repeat it as fact.

`FD`/`CD`: **unknown.** No source describes them. Unused here.

Verify each cell reads 3.6–4.2V and the pair are within ~0.1V before connecting
the output.

> ⚠️ **0V at `(+)`/`(−)` is a real fault signature, not a quirk.** Documented
> cause: a cell inserted backwards in the holder makes the BMS shut down
> entirely. Check cell orientation first. (Some BMS designs do latch off until
> first charge — no evidence that applies to this board.)

**Switch polarity — unresolved.** Reading the upstream diagram, the power
switch sits on the **`P−` (negative)** leg. TNKR's table puts it on `P+`. The
sources genuinely disagree and it's not clear which the designer intended.
Functionally either works — breaking either leg opens the circuit.

One real consequence if it is on `P−`: low-side switching means *switch-off
does not fully isolate if another ground path exists* — and the servo board's
USB cable to the Mac is exactly such a path. Unplug USB when you want the robot
truly dead.

### Claims in this file that are inference, not verification
- Trunk's "middle motor" identified as `30` neck_pitch — read off a CAD render,
  never confirmed. Check: its axis should be horizontal, left-to-right.
- Thigh `hip_pitch` mount orientation — **not determined.** Use the Onshape CAD.
  Physical invariant: at motor zero the whole leg stands dead straight.

### The Pi (brain)

| | |
|---|---|
| MAC | `88:a2:9e:58:00:d7` (OUI `88:A2:9E` = Raspberry Pi Trading) |
| OS | Debian 13 trixie — `OpenSSH_10.0p2 Debian-7+deb13u4` |
| SSH | enabled out of the box (Imager) |
| Found at | `172.20.154.205` on 2026-08-18 — **DHCP, will move** |

Joined the hidden SSID `A-510` on first boot; the Imager "Hidden SSID" checkbox
was the thing that made that work.

**Reaching it:** `ssh paul@ezer.local` — **mDNS works fine.** (An earlier note
here claimed it didn't; that was wrong. `raspberrypi.local` failed only because
the hostname is `ezer`.) Key auth is already set up from the Mac's
`id_ed25519`.

`./scripts/find_duck.sh` remains the fallback for when mDNS is flaky or the
host is on a foreign subnet — it matches by MAC and pings to confirm.

> ⚠️ **ARP entries go stale for ~20 min after a device drops.** A host listed in
> `arp -an` is not proof it is alive — this fooled me once. Always ping to
> confirm. `find_duck.sh` does this for you.

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

---

## The black box (instrumenting the Pi before first boot)

**Why this exists.** Three separate times the Pi went dark and the only tools
available were `ping`, `arp`, and an LED. Every one of those returns a single
bit — *is it there* — and none of them says *why not*. Debugging a machine over
the network it has stopped joining is not debugging.

The boot partition is FAT32. Any computer can read it. So the Pi records its
own state there, and diagnosis becomes: pull the card, run one script.

### Install (fresh flash, before first boot)

```bash
./scripts/instrument_sd.sh      # card mounted at /Volumes/bootfs
diskutil eject /Volumes/bootfs
```

It refuses to run on a card that has already booted, because cloud-init only
applies `user-data` once — keyed on the `instance-id` in `meta-data`. On a
card that has booted, nothing would be installed and the script would lie
about success.

It **merges** into Imager's `user-data` rather than replacing it: hostname,
user, password hash, SSH key, and wifi config all survive.

### Read (after any failure)

```bash
./scripts/read_blackbox.sh          # summary
./scripts/read_blackbox.sh --dump   # copy the whole thing off the card
```

### What gets installed

| Path on the Pi | Job |
|---|---|
| `/usr/local/bin/blackbox.sh` | one state line every 15s → `/boot/firmware/blackbox/state.log` |
| `/usr/local/bin/bootsnap.sh` | per-boot forensic dump → `boot-NNN.txt`, keeps last 6 |
| `blackbox.service` | starts at `sysinit.target`, before networking, so it survives a boot that never reaches `multi-user.target` |
| `bootsnap.service` | waits 75s, then photographs a boot that has finished trying |
| `journald.conf.d/persistent.conf` | **the key one** — without persistent journald, the log explaining why the last boot died is erased by the boot that comes asking |
| `usb0.nmconnection` | USB gadget ethernet on link-local; a second way in that does not involve wifi |

### Reading the state line

```
ts=… up=… thr=0x0 temp=44.1 wlan=up ip4=172.20.154.205/24 assoc=yes ssid=A-510 rssi=-51 nm=connected rfkill=no load=0.9 rw=rw
```

- `thr` — `vcgencmd get_throttled`. Bit 0 = undervoltage **now**, bit 16 =
  undervoltage **has occurred**. Given the UBEC hiccup history this is the
  single most important field on the line.
- `assoc` vs `ip4` — separates *never joined the network* from *joined but got
  no lease*. Completely different bugs, and `ping` cannot tell them apart.
- `rw=ro` — root remounted read-only. ext4 does that when it hits an error.
  That is the corruption signature we would expect from repeated hard power cuts.
- `### boot mark` with no `### CLEAN STOP` after it — the Pi was **killed**,
  not shut down. This is how we tell an electrical failure from a software one.

### Deliberate limitation

`bootsnap` writes at 75s. A failure that kills the Pi before then leaves only
`state.log`, which is append-and-`sync` and therefore survives. That trade is
intentional: append is the safest FAT operation under sudden power loss.


### Verified on the 2026-08-24 flash

Pi OS **trixie**, kernel `6.18.34+rpt-rpi-v8`, aarch64, **Python 3.13.5**.
`ezer` at `172.20.154.205`, associated to `A-510` at `rssi=-35`, `thr=0x0`.

Two install-time quirks, both self-correcting on the second boot, worth knowing
so they are not mistaken for failures:

1. **journald is still volatile on the install boot.** cloud-init writes the
   drop-in *after* journald has already started, so the first boot logs to
   `/run/log/journal` (RAM). `/var/log/journal` exists by then, so the next
   boot is persistent. Verified: `journalctl --list-boots` shows `IDX -1`
   after one reboot.
2. **`bootsnap` does not run on the install boot.** cloud-init enables it after
   `multi-user.target` has already been reached, so it first fires on boot #2.

Confirmed working unattended after a clean reboot: `blackbox` active,
`bootsnap` wrote `boot-002.txt` (124 KB, 23 sections) on its own, and
`state.log` recorded `### CLEAN STOP … up=212` — so a graceful shutdown is now
distinguishable from a power cut.

### Python 3.13 vs the runtime pins — settled

Checked against the PyPI file lists, not inferred:

| package | pinned | linux-aarch64 wheels | cp313? |
|---|---|---|---|
| `onnxruntime` | `1.18.1` | cp38–cp312 | **no** |
| `numpy` | `1.26.4` | cp39–cp312 | **no** |

So `pip install -e .` against `Open_Duck_Mini_Runtime` **cannot** work on this
image as shipped. trixie has no `python3.11` package, and the image ships no
`pip` at all (`python3-pip` is not installed; `venv` is present).

`onnxruntime` gained cp313 aarch64 wheels at **1.20.0**. Three ways out:

1. **Miniforge with Python 3.11** — matches the pins exactly, no reflash.
   Preferred: the community's policies were produced and tested against these
   versions, and inference numerics are the last thing worth improvising on.
2. **Unpin** to `onnxruntime>=1.20` + a numpy 2.x. Cheapest, but drags in
   numpy 2.x's breaking changes against code written for 1.26.
3. **Reflash to Bookworm**, which ships Python 3.11 natively.


### Power-cut test, 2026-08-24 — the card survived

Battery switched off with no shutdown, 30s off, back on. Result: **no damage.**

| check | result |
|---|---|
| ext4 errors / I/O errors | none beyond routine orphan cleanup |
| root filesystem | stayed read-write |
| failed units | none |
| undervoltage (`thr`) | `0x0` throughout |
| wifi associated at | `up=43s` — **identical to a clean reboot** |

The recorder caught the cut correctly: a `### boot mark` with no `### CLEAN
STOP` before it.

**Baseline worth keeping: wifi associates at `up=43s`.** Any check that gives
up sooner than that is measuring its own impatience, not the Pi.

**Careful with `ts=`.** The Pi Zero 2W has no RTC, so the clock is wrong until
NTP syncs — which is why a new boot's mark can appear to *precede* the previous
boot's last sample. Reason with `up=`, which is monotonic from boot.

One cut is not proof. The historical failures happened while the UBEC was
hiccuping, i.e. possibly many rapid cuts, and plausibly during writes rather
than at idle. It is also entirely possible the old failures were caused by the
bad barrel-jack ground rather than by filesystem damage at all — that fault is
now fixed, and this card has not misbehaved since.


### Second power-cut test — cut *during boot*, mid-write

Off → on after 10s → **off again while the ACT LED was still flashing** → on.
A cut during boot writes, which is the harsh case. Survived. Wifi back at
`up=43s`, the same baseline as a clean reboot.

What the cuts actually damaged:

| filesystem | result |
|---|---|
| root (ext4 p2) | `Filesystem state: clean`, no I/O errors, orphan cleanup only |
| boot (FAT p1) | dirty bit set + 1 byte differing from the boot-sector backup — `fsck.fat` calls it *"mostly harmless"*, and `systemd-fsck` clears it at each boot |
| systemd journal | `system.journal corrupted or uncleanly shut down, renaming and replacing` |

The journal is the real casualty, and it is the one that matters for
diagnosis: an unclean cut can destroy the previous boot's log, which is
exactly what `bootsnap` reads. **`journal-tail.txt` on the FAT partition is
what covers that gap** — it is refreshed every 60s and survived both cuts.

All black box files survived intact: `boot-001..004`, `journal-tail.txt`,
`state.log`.

#### The PARTUUID changes on first boot — this is normal

The card was flashed with `root=PARTUUID=041bba91-02`; it now runs
`0fc26a91-02`. Not corruption. Raspberry Pi's first-boot resize **regenerates
the partition table**, which changes the MBR disk signature, then rewrites
`cmdline.txt` and `/etc/fstab` to match. Verified: `fdisk` reports
`Disk identifier: 0x0fc26a91` and both files agree.

Do not use a PARTUUID read off a freshly flashed card to diagnose a card that
has since booted.

#### Conclusion

Two abrupt cuts, one of them mid-write, produced no meaningful corruption.
The "it only works right after a reflash" pattern is therefore **not**
explained by power-cut damage. The likelier culprit remains the barrel-jack
ground fault — already found and resoldered.

SD wear baseline for later comparison: `Lifetime writes: 2943 MB`,
`Mount count: 6`.


### Hot-plugging the barrel jack kills the Pi (2026-08-24)

With everything running, plugging the DC barrel jack into the servo board took
the Pi down instantly.

**Mechanism.** The servo board's bulk capacitance is discharged. Connecting it
to a live pack is a near short-circuit for a few milliseconds. The pack sags
hard — measured 6.56V → ~3V doing exactly this — the UBEC falls below its
dropout, and its 5V output disappears. The Pi does not brown out; it simply
loses power.

**`thr` cannot see this.** All 97 samples read `thr=0x0`, including the last
one before death. `vcgencmd get_throttled` reports the SoC's own voltage
monitor, which needs the SoC to still be *running* at a degraded voltage to
latch anything. A rail that collapses outright leaves no trace. The event was
caught instead by a `### boot mark` with no `### CLEAN STOP` before it, and
corroborated by `temp=45.6` at `up=12` — warm silicon means a restart, not a
cold boot.

**Working rule: sequence matters.** Plug the barrel jack in with the power
switch **OFF**, then switch on, so the inrush happens once while nothing is
running. Never hot-plug it into a live system.

**Real fixes, if hot-plug ever has to be safe:** an NTC inrush limiter in
series with the servo board's supply, or enough bulk capacitance on the UBEC
input to ride through the sag. Not needed if the sequence is respected.


### Installing pypot on the Pi — the recipe that works

Pi OS trixie ships Python 3.13 and **no pip**. Miniforge with Python 3.11
matches the runtime's pins without a reflash.

```bash
wget -O /tmp/Miniforge3.sh \
  https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh
bash /tmp/Miniforge3.sh -b -p ~/miniforge3
~/miniforge3/bin/conda create -y -n duck python=3.11
```

Then **two traps**, both of which cost a cycle:

1. **`pypot` drags in `opencv-contrib-python`** — a 58 MB wheel. The Pi's wifi
   dropped that download six times. Fetch it on the Mac and `scp` it over.
2. **Install the *headless* OpenCV.** The normal build links against GTK/X11,
   which Pi OS Lite does not have, so even a clean download dies at
   `import cv2` — and that failure looks like a pypot bug, not a missing
   system library.

`FeetechSTS3215IO` only pulls in `cv2`, `numpy`, and `serial` — verified by
watching `sys.modules`, not by reading the metadata. So skip the rest:

```bash
PIP=~/miniforge3/envs/duck/bin/pip
$PIP install /tmp/opencv_contrib_python_headless-*-aarch64.whl   # keep the real wheel name!
$PIP install numpy pyserial
$PIP install --no-deps "pypot @ git+https://github.com/pollen-robotics/pypot@f6d305e70e1640f66188b256dfd1dcfeb8ab8a59"
```

> A wheel must keep its canonical `{name}-{version}-{python}-{abi}-{platform}.whl`
> filename. Renaming it to something friendlier makes pip reject it with
> *"Invalid wheel filename (wrong number of parts)"*.

Installed: `pypot 5.0.2`, `pyserial 3.5`, `numpy 2.4.6`, `cv2 5.0.0`.

> `numpy 2.4.6` will be **downgraded to 1.26.4** when the runtime is installed,
> since that is what it pins. 1.26.4 has cp311 aarch64 wheels, so this is fine —
> but expect the change and do not read it as breakage.


### IMU — working, with one unresolved question (2026-08-28)

BNO055 answers at `0x28`. I²C needs **both** fixes on a fresh card, and the
second is the one people miss:

```bash
sudo sed -i 's/^#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' /boot/firmware/config.txt
echo i2c-dev | sudo tee -a /etc/modules    # config.txt alone does NOT create /dev/i2c-*
sudo reboot
```

Live reading at rest, `upside_down=False`:

```
accelero [ 1.60  -0.13  -9.83 ]     gyro [ 0.001  -0.003  -0.001 ]
```

Magnitude **9.96 m/s²** vs standard gravity 9.807 — 1.6% high, normal
uncalibrated. It is genuinely measuring the Earth, not returning plausible
numbers.

**Two open items:**

1. **A ~9° tilt.** `acos(9.83/9.96) ≈ 9.3°` off vertical, from the 1.60 on X.
   Either the duck leans on the bench or the IMU sits at an angle in the head.
   The policy takes tilt as input, so a constant bias reads as "falling."

2. **`imu_upside_down` is unresolved.** The two branches in `raw_imu.py`
   differ *only* in the sign of Y and Z:

   | flag | remap signs | Z reads |
   |---|---|---|
   | `False` | `(NEG, POS, POS)` | −9.83 (measured) |
   | `True`  | `(NEG, NEG, NEG)` | +9.83 |

   `v2_rl_walk_mujoco.py:76` takes the flag from `duck_config.json`, and
   :158-159 feed the **raw** `gyro` and `accelero` into the policy's
   observation. So the correct sign is whichever the policy saw in training —
   that convention lives in `Open_Duck_Playground`, not in this repo.

   **Do not guess this.** Wrong sign means the duck's sense of up is inverted.
   Resolve it either by checking the physical mounting of the BNO055 in the
   head, or by reading the observation builder in the training env.

`~/duck_config.json` created from `example_config.json` and confirmed readable
by `DuckConfig`. Attribute is `joints_offset`, singular.


### The STS3215 offset register (addr 31) — verified behaviour

Usable for fixing a horn installed half a turn out, **without disassembly and
without any runtime cost**: the correction is applied inside the servo's own
firmware, so the Pi's control loop never sees it. It lives in EEPROM and
survives power cycles.

Write pattern is the same as Phase 0 config: `set_lock(0)` → write →
`set_lock(1)`.

**pypot's units for this register are wrong for negative values.** It applies a
Dynamixel linear map, but Feetech encodes the register as sign-magnitude around
raw 2048, so the negative half folds. Measured on `head_yaw`:

| wrote | actual shift |
|---|---|
| +10 | +9.94 |
| +90 | +90.02 |
| +170 | +169.93 |
| +180 | −180.13 (same rotation, clean wrap) |
| **−170** | **−10.03** ← not −170 |

Rule for the negative half: real shift = `−(180 + X)`. So to get −171° you
write **−9**, not −171. **Stay in the positive half** and let the ±180 wrap do
the work instead.

A resting `get_offset` of **−180.0 means raw 0, i.e. no offset at all** — not a
180° correction already applied. Do not misread that as a configured value.

**Goal and present positions share one frame.** Verified: with a +90 offset,
commanding 97.00 reached 96.22. So the correction is safe to control through.

