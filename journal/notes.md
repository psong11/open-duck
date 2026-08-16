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

