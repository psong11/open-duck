# The self-observing test rig

*2026-09-02. Phase 0 SHIPPED (disarmed); phases 1-4 proposed. Every phase
below is priced in testing sessions, because that is the currency that
matters.*

Diagrams: https://claude.ai/code/artifact/e9ed1e23-892a-45d3-a5eb-857281dd7388

## The pitch

Every robotics lab has a camera rig over the test area, because the
bottleneck in making a robot walk is not compute and not the policy — it is
how fast you can see what went wrong and try again. Right now that loop runs
through a human narrator: the robot moves, a person watches, the person
describes it in words, an AI reasons about the words. Each hop loses
information, and the lossiest hop is the description.

This proposal replaces the narrator with a camera the AI can read directly.
The duck's runs get recorded automatically, bracketed by the same script that
already owns the run's lifecycle. The duck protects itself when it falls,
using the IMU it already has. And every run becomes a labeled record — video,
joint telemetry, power telemetry, and the policy's own observations, aligned
in time — which is exactly the dataset you would need to close the
sim-to-real gap later. It is built from hardware already on the desk: a
Jetson with a working camera pipeline, a Pi with a flight recorder, and a
walk script that already marks its own events.

## The loop today, and where it leaks

```
  AI proposes a run
      │
      ▼
  Paul runs it, watches, resets the duck        ← costs a battery charge
      │
      ▼
  Paul types what he saw                        ← the lossy hop
      │
      ▼
  AI reasons about the words, proposes again    ← reasons about a summary,
                                                   not the event
```

Two things are wrong with this. The obvious one is that words are a bad
sensor: "it wiggled and buried its face" is a real observation, but it cannot
answer *which foot left the ground first* or *did it fall before or after the
voltage dipped*. The less obvious one is that an AI reasoning about a summary
will confidently prescribe things the raw data already rules out — the
"charge it and try `-p 24`" call was made while the logs sat there saying the
Pi never browned out. Primary evidence makes that kind of miss harder.

What this does **not** fix is also worth saying up front: the battery charge
per run, the physical reset, and the hand on the power switch stay manual.
This halves the loop; it does not close it.

## The system, in one sentence each

Three jobs, deliberately separated, because they have different latency and
different failure modes:

| job | who does it | why there |
|---|---|---|
| **Protect** — torque off when the duck falls | the Pi, from the IMU, inside the control loop | sub-tick latency, no network, works when the Jetson is off |
| **Record** — video of every run, bracketed to its lifecycle | the Jetson, inside the process that already owns the camera | the CSI camera has exactly one owner |
| **Analyze** — turn a run into something the AI can read in one call | a script on the Mac, after the run | no real-time constraint, so keep it off the robot |

The key design decision is the first row. Vision-based fall detection was
the original idea, and it is the wrong tool for *safety*: it adds a network
hop, a second machine, and a detector that has to be trained on falls it has
not seen yet. The BNO055 already knows which way is down — it is column 3–5
of the policy's observation. A fall is the gravity vector leaving the cone
around vertical. That check is four lines, runs at 50 Hz on the Pi, and
degrades to nothing if the Jetson is unplugged. The camera's job is to let
the AI *see*, not to keep the duck safe.

## Architecture

### Lifecycle bracket — `run_walk.sh`

`run_walk.sh` already owns the run: it starts the power watcher before
torque-on, runs the walk in the foreground, and cleans up on any exit. The
camera hooks in at the same two points, and must never be able to stop a
run from happening:

```
curl -s --max-time 1 "http://jetson.local:8080/rec/start?label=$LABEL" || true
... existing watcher + walk ...
curl -s --max-time 1 "http://jetson.local:8080/rec/stop" || true
```

Recording starts before the pre-run voltage check and stops after the
post-run one, so the video brackets the whole thing. "Timing it perfectly
with when the walk begins" is a non-problem once one script owns both ends.

### Event marks — no clock sync required

The walk script already calls `fl.mark("torque on, entering loop")` into the
flight log. Each mark also gets sent to the Jetson:

```
GET /rec/mark?label=torque_on
```

The Jetson stamps it against its *own* frame counter. So the video and the
telemetry are aligned by shared events, not by two clocks agreeing. NTP is a
nice-to-have, not a dependency. Marks worth having: `torque_on`,
`init_pose_reached`, `loop_start`, `fall` (from the IMU check), `exit`.

### Recorder — inside `liveview.py`

Only one process can hold `nvarguscamerasrc`, and `liveview.py` is it
(running as `liveview.service`). So recording is a feature of that service,
not a sibling process. It already has a frame loop, a watchdog, and a
`fresh_raw()` accessor; the recorder is a `cv2.VideoWriter` fed from that
loop between `/rec/start` and `/rec/stop`.

Encode with the hardware H.264 encoder (`nvv4l2h264enc`), not MJPEG — a 60 s
run at 1080p is ~20–30 MB instead of ~500 MB. Output:

```
~/runs/<label>-<yyyymmdd-hhmmss>/
    video.mp4
    marks.json        # {label: frame_index}
```

**Verify the recording before trusting it.** The Jetson's own failure log has
an entry for "started successfully" being mistaken for "works." `/rec/stop`
returns the frame count and file size; `run_walk.sh` prints both. Zero
frames is a loud failure, not a silent one.

### Analysis — `scripts/read_run.sh` on the Mac

Extends the existing `read_walklog.sh`. Pulls the walk log and power log from
the Pi, the video and marks from the Jetson, and produces the one thing an AI
can read in a single call: a **contact sheet** — a grid of frames at 1 Hz,
plus a frame at every mark, each captioned with the mark label and the
telemetry at that instant (pack voltage, `dt_max`, `lcrit`). One image, one
`Read`, the whole run.

Later, the same script overlays the flight-log series on the frame timeline —
the sag curve with a video thumbnail at the moment it dips.

### Fall detection — the IMU check on the Pi  [SHIPPED 2026-09-02]

The first sketch assumed "up" is the +Z axis:

```python
g = imu_data["accelero"]
tilt = degrees(acos(clip(g[2] / norm(g), -1, 1)))   # 0 = upright  <- WRONG
if tilt > FALL_DEG:  fl.mark("fall"); break
```

Measuring first killed that. The IMU sits in the **torso**, it is not mounted
square, and -- the part that matters -- **her torso is pitched forward on
purpose**. The lean is what the gait is built around, not a symptom. A
detector that treats tilt as trouble would fight the design.

So "a fall" means TOTAL COLLAPSE, not tilt. Flat on the floor is ~90 deg from
the reference, so the trigger sits at 65 deg with a 45 deg release: clear of
any honest stride, still early enough to catch her before she ploughs her
face along the carpet. Every one of those numbers is a placeholder -- shadow
mode writes `tilt_max` to the flight log every 100 ms, so the first real walk
says what she actually reaches upright, and the threshold gets set from that.

So the shipped version takes a **reference pose** instead of assuming one,
and **disables itself loudly** when no reference exists rather than guessing.
A missing tare means the walk behaves exactly as it did before.

The tare must be taken with the servos **holding the init crouch**:

    python slew_to_init.py           # moves there, exits STILL HOLDING
    python fall_check.py --tare      # only touches the I2C IMU, not the bus
    python slew_to_init.py --release

A limp duck slumped on the bench sits at a different torso angle entirely.
The first tare (2026-09-02) caught exactly that mistake -- all 14 servos
unpowered, hips 50 deg off init, knees 22 deg -- and was set aside.

Two more gates keep it from killing good runs. Gravity has to dominate: a
walking robot accelerates itself, and during a hard footfall the vector does
not point at the floor, so samples outside a band around 9.81 are discarded.
And the tilt has to *persist* — eight consecutive valid samples, with a latch
that releases only below 45 deg, so a duck hovering at the threshold reports
once instead of forty times.

It ships in **shadow mode**: it marks the log and does not act. Only
`DUCK_FALL_ARM=1` stops the walk.

    scripts/duck_fall.py    FallWatch: gravity gate + debounce + latch
    scripts/fall_check.py   bench tool, read-only. --tare captures the ref
    scripts/test_fall.py    18 synthetic checks

Verified against the live IMU: silent for 60 ticks at the tared pose, fires
on tick 3 of an injected 90 deg topple, mark lands in the flight log.
Backup of the pre-patch walk script: `v2_rl_walk_mujoco.py.prefall`.

**Still outstanding: one tare with her standing properly.** Until then the
detector prints that it is disabled and does nothing.

## Phases — each priced in sessions

| phase | what ships | validated by | session cost |
|---|---|---|---|
| **0 — Protect** | **DONE** — IMU fall check, shadow mode, in the walk script | 18 synthetic checks + live IMU integration test | **0** — none used |
| **1 — Record** | `/rec/*` in `liveview.py`; bracket in `run_walk.sh` | point the camera at anything; then it rides on the next walk you were doing anyway | **0** extra |
| **2 — Read** | `read_run.sh` → contact sheet | the recordings phase 1 already made | **0** |
| **3 — Arm** | fall check flips from mark to act | the shadow-mode marks vs the video, from runs already recorded | **0** extra |
| **4 — See live** | the Jetson runs a fall classifier as a *second opinion*; live view in the AI's browser pane | fall footage that phases 1–3 collected passively | **0** extra — and optional |

Phase 0 is an hour and makes every subsequent run safer. Phase 1 is an
evening. Phase 2 is the payoff. Phases 3 and 4 are earned by the data the
first three produce, which is the point: nothing here needs a session of its
own.

## Watch out for

- **Coupling.** The walk must run identically with the Jetson off. Every
  camera call is `--max-time 1 || true`. If a recording is missing, the run
  still happened and the flight logs still exist.
- **One camera owner.** A second `nvarguscamerasrc` pipeline hangs the
  first. Recording goes inside `liveview.py` or it does not go.
- **Driving the Jetson over SSH.** Read `jetson-yolo-stream/docs/ssh_jetson.md`
  and `docs/failure_log.md` first. Background processes, quoting, and the
  sudo allowlist have each cost a session before.
- **Framing.** Fixed camera, moving robot. Frame wide, from slightly above,
  with the duck starting near the far edge of the field walking toward the
  camera. It covers about a meter in 60 s; it will stay in frame.
- **Storage.** H.264 only. A `runs/` directory that keeps the last 20 and a
  `read_run.sh` that pulls to the Mac, where the archive actually lives.
- **Shadow before arm.** The fall detector marks before it acts. Same rule as
  the power watcher: instrument first, trust second.
- **The serial timeout.** A dropped servo packet still ends a run today. That
  is a separate fix (a retry around the read, logging which id went quiet)
  and it rides along with phase 0 — but the rig does not depend on it.
- **The hand on the switch.** Nothing in this proposal lets the AI start a
  run. Paul presses go. The rig automates observing, not actuating.

## Feasibility

Yes, and most of it exists:

| piece | state |
|---|---|
| Jetson camera pipeline, MJPEG hub, watchdog, snapshots | **built** — `liveview.py`, running as a service |
| Hardware H.264 encoder | on the Orin Nano, unused so far |
| Run lifecycle owner | **built** — `run_walk.sh` |
| fsynced flight recorder with event marks | **built** — `duck_flightlog.py`, `fl.mark()` already in the walk script |
| 20 Hz power watcher | **built** — `powerwatch.py` |
| IMU gravity vector in the control loop | **built** — it is already in the observation |
| Fall detector, bench tool, tests | **built** — `duck_fall.py`, `fall_check.py`, `test_fall.py` |
| Policy observation recorder | **built upstream** — `--save_obs` |
| Log puller on the Mac | **built** — `read_walklog.sh`, to be extended |

What is genuinely new: ~80 lines in `liveview.py`, two `curl` lines in
`run_walk.sh`, four lines in the walk script, and the contact-sheet script.

## Why this is bigger than debugging

A run recorded this way — video, marks, joint positions and velocities at
50 Hz, pack voltage at 20 Hz, and the exact 101-number observation the
policy saw each tick — is a *labeled real-world rollout*. That is the raw
material for the next thing after "it walks": measuring the sim-to-real gap
with `--replay_obs`, and eventually fine-tuning on real data. The rig built
to debug a wobble is the same rig that makes the robot a research platform.
