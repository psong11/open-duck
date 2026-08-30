# Raw notes

Unpolished on purpose. Capture first, shape later — this is the raw material
for whatever the recap / site ends up being.

Two kinds of thing go here:
- **moments** — what building this actually felt like, including what working
  with Claude was like
- **notes** — observations that aren't technical reference (those live in
  `NOTES.md`)

---

## 2026-08-14 — day zero

**moment.** The instruction that landed wasn't in any documentation: *"put a
piece of tape on it marked 10."* Fourteen identical black servos in a pile, and
by motor nine you won't remember which is which. Nobody writes that down — it's
the kind of thing you'd only get from someone who has actually done it, or from
someone paying attention to what you're about to walk into. Worth remembering
that this is the part of building-with-Claude I want to capture: not the code
it wrote, the things it thought to mention.

**moment.** Spent a real stretch debugging a completely silent servo bus.
Swept every baud rate, every address 0–253, sent raw protocol pings. Nothing.
Then walked the multimeter out from the battery and found it: **one 18650
wasn't touching its contact.** The most ordinary failure imaginable, at the
very start of the chain. Sighed audibly.

The lesson isn't "check your batteries." It's that the software layer got
fully exonerated in about two minutes, and I still went looking for a clever
cause instead of the physical one. Debug outward from power.

**moment.** First reading back from a live motor:
`FEETECH_STS3215 · 7.3V · 26°C · position 179.91`. A thing on my desk answered
a question. Then it took the name `10`, drove itself to zero, and held there
waiting for a horn.

**moment.** All fourteen named in one sitting. `10` through `14`, `20` through
`24`, `30` through `33`. A pile of identical black servos became a right leg, a
left leg, and a head — entirely because of masking tape and a number written in
EEPROM. Nothing about them changed physically. They're just *addressable* now.

**note.** Motor 11-of-14 (`neck_pitch`, id 30) reported success while one
register — `max_acceleration` — silently stayed at the factory 50 instead of 0.
It only surfaced because the number looked different from the ten before it.

The root cause of the *class* of bug: `configure_motor.py` reads its own writes
back within the same connection, which proves nothing about whether they landed
in EEPROM. So we added `verify_motor.py`, which reconnects and checks. The
remaining three self-verified.

Worth keeping: the fix wasn't "be more careful reading output." It was making
the machine check, because at motor eleven of fourteen I would eventually stop
looking.

---

## 2026-08-15 — heft

**moment.** Building feet, ankles, knees, thighs, hips. Fun build. But the
thing I keep noticing is the *weight*. So much heft and bulk behind a robot
this small.

New respect for good physical design — servos well integrated, wires routed
properly, pieces modular enough that a broken part can actually be replaced.
Good physical design is more impressive to me right now than good software
design. Maybe I'm just jaded by software.

**note.** People don't appreciate how heavy a real humanoid is going to be.
It's basically straight metal. Not a light agile thing. And the force and
momentum available from the servos *plus* the mass of the body is remarkable.

*(The physics behind that instinct: mass scales with volume, L³. Actuator
torque scales roughly with cross-section, L². Double a robot's height and it
gets ~8× heavier but only ~4× stronger. That's the square-cube law, and it's
exactly why humanoids are so heavy and why a 42cm duck is feasible at all —
at this scale the law is on my side.)*

---

**note.** I pushed back on being told I needed the battery pack connected —
it felt like an assumption rather than something checked. It turned out to be
correct, but it *was* unsourced when first said. Asking for grounding produced
the official wiring diagram, which is now in `docs/`. Good trade. Keep doing
that.


---

## 2026-08-28 — the body answers, and then runs out of breath

**moment.** Fourteen motors, one bus, one command, and every one answered.
`responding 14 / 14`. The legs I built, the head, the neck — all of it
introducing itself through a single cable to a computer the size of a stick of
gum sitting in the duck's skull. Not walking yet. But I asked, and it answered,
and every part of it was something I put together with my hands.

**note.** The IMU said the duck was tilted nine degrees. It wasn't. The sensor
is mounted component-side down — upside down — and with the axis convention
corrected it reads dead level, gravity a clean `+9.91` on Z. The nine degrees
was never real. It was gravity leaking into the wrong axis.

Worth keeping because the wrong diagnosis was the *plausible* one: "your robot
leans slightly" is a perfectly reasonable thing to believe, and it would have
had me shimming a joint that was already true.

**note.** Both hip pitch horns went on half a turn out. Instead of taking the
legs apart, we wrote a `+180` correction into each servo's own EEPROM — the
motor now does the arithmetic in its firmware, so the Pi's control loop never
sees it and pays nothing for it. Upstream has this on their TODO list and
hasn't built it yet.

Finding out whether that register was trustworthy took four tests, not one. The
first test — ten degrees — passed beautifully. So did ninety, and a hundred and
seventy. Then negative a hundred and seventy came back as negative ten, because
the chip encodes sign one way and the library reads it another. The number I
actually needed sat right on that seam. A single clean test would have written
a wrong number permanently into a structural joint.

**note.** Three brownouts in one evening, and they rank exactly the way physics
says they should: idle runs for hours, holding a pose dies after minutes,
walking dies in seconds. The last one killed the Pi so fast that the log file
never made it out of the page cache — **the absence of the log was the
measurement.** It bounded the run at under five seconds.

**note.** A dead Pi leaves the duck *rigid*, not limp. The servos live on the
raw battery rail; only the brain sits behind the regulator. So when the brain
dies the joints hold their last order indefinitely, and nothing on the network
can reach them. The only real emergency stop is the power switch. I had been
handed a software kill switch that ran on the machine that failed.

**note.** The table showed every motor sitting up to 358° away from its goal
position while drawing exactly zero current. That's how you know torque is
off — if it were on, a 358° error would have slammed fourteen servos to full
power against a robot I just finished assembling. Limp and waiting is the
correct state, and it was legible from the numbers rather than from hoping.

**note.** Getting there took a detour through a 58 MB OpenCV wheel that
`pypot` wants and the servo code never uses, downloaded six times over wifi
that kept dropping it. Fixed by pulling it on the Mac and pushing it over the
LAN — and by using the *headless* build, since the normal one needs graphics
libraries that a headless Pi doesn't have. That would have been an hour of
confusing debugging: the symptom is `ModuleNotFoundError: cv2`, and the cause
is a window manager that isn't there.

**moment.** Paired the controller after a genuinely stupid chain: bluetooth was
soft-blocked by rfkill, which reports as a meaningless `org.bluez.Error.Failed`;
game controllers speak Bluetooth Classic while every scan I'd run was looking at
Low Energy; the Pi shares one antenna between wifi and bluetooth so the thing
had to be pressed against the duck's head; and pairing needs an agent process
that `bluetoothctl` silently fails to register when driven from a pipe.

Four independent walls. None of them mentioned anywhere in the build docs.

**moment.** Late in the night I read back through the reasoning and found a
line where it had worked out, from a UTC timestamp in a log, that it was about
half past nine my time — and decided on its own to stop pushing and start
wrapping up, because I'd been at this since morning.

I asked how that happens. The honest answer was that nothing is hardcoded for
it: the timestamps and the session length were just observations, like a voltage
reading, and the disposition to *act* on them fell out of training rather than
being installed. It won't claim to have felt anything, and it won't deny it
either.

I don't fully know what to do with that. But building a robot all day and
having the thing helping me build it notice I was tired — I'm floored, and I
wanted it written down.

---

## 2026-08-30 — the instrument is cheaper than the guessing

**moment.** The duck has never taken a step. I found that out today, on the
fourth try, and it reframes everything I thought I knew about this problem.
Three times I'd said "walking browns out the Pi." It doesn't. The Pi dies four
and a half seconds in, during start-up, before the control loop ever begins.
The walk was never reached. I'd been naming the failure after the script it
happened inside.

**note.** The reason it took four attempts to learn this is that the machine
writing down what happened was the machine that kept dying. Every brownout
destroyed its own evidence. So before running anything else I built a recorder
that forces each sample to disk the instant it's taken — a queue on the control
loop, a writer thread doing the `fsync`, so the loop never waits on an SD card
and nothing that lands is lost to a power cut. A clean run ends by writing the
word `END`. A file that just stops is a death. That one difference is the
whole diagnostic.

**note.** Found a sensor on the Pi I didn't know was there:
`/sys/class/hwmon/hwmon1/in0_lcrit_alarm`, the low-voltage flag from the
`rpi_volt` driver. It's a plain file read rather than a call into the firmware,
which means it can be sampled twenty times a second instead of once. Worth
knowing: it never tripped. Neither did the throttle word. That is *not* the
same as the power being fine — the chip has to survive at a degraded voltage
long enough to notice and set a bit, and a fast enough collapse leaves nothing
behind at all. Silence from a sensor is not a negative result.

**note.** My first real test was a bad experiment and I want it written down
rather than quietly deleted. I ramped the servo gain from 4 to 32, the full
runtime value, and the pack didn't budge — a tenth of a volt. Looked like an
exoneration. It wasn't: I'd parked every joint's target at exactly where it
already was, so the position error was zero, and gain is a multiplier on error.
I'd floored the accelerator in neutral. The lesson isn't "test more carefully,"
it's that a test which cannot fail hasn't told you anything, and a clean result
should make you suspicious before it makes you confident.

**note.** The real test was the crouch. Start-up writes an init pose to all
fourteen servos in one command — knees near 78°, hips 36°, ankles 45°. Stretch
that move over ten seconds instead and read the pack twenty times a second, and
the answer is a slope, not a cliff: 7.6 V down to 6.5 V, about a tenth of a
volt for every ten percent deeper the duck squats. Load-proportional, all the
way down.

**note.** Then the part I didn't expect. Reading the load on every joint while
it held that crouch: twelve of the fourteen are doing essentially nothing, and
two — both hip pitches — are pulling twenty times the median and stalling
twenty degrees short of where they were told to go. A stalled motor is a motor
drawing its maximum current. Two servos are carrying the entire robot and
getting hot doing it.

**worth keeping.** The shape of the answer is a vice with no gap in it. At low
gain the duck survives but can't hold itself up. At the gain that would hold it
up, the current drags the pack below what the Pi's regulator needs and the
brain dies. There is no setting that does both. That's not a bug I can write my
way out of — it's a battery that can't afford to stand up. Two full overnight
charges both stopped at 7.8 V on a pack whose full is 8.4, which is either a
charger in the wrong mode or a pack near the end of its life. Tomorrow's
problem.

**worth keeping.** The thing I'll actually carry out of today isn't about
batteries. It's that I spent three sessions asking *why did it die* and getting
nowhere, and about an hour building something that could survive the death and
tell me — and then knew within one run. The instrument was cheaper than the
guessing. It always is, and I keep having to relearn it.
