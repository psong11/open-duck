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

**note.** I pushed back on being told I needed the battery pack connected —
it felt like an assumption rather than something checked. It turned out to be
correct, but it *was* unsourced when first said. Asking for grounding produced
the official wiring diagram, which is now in `docs/`. Good trade. Keep doing
that.

