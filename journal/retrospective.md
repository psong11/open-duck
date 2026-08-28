Fourteen servos, two 18650 cells, a five-volt regulator, a computer the size of
a stick of gum, and about two weeks. This is what building the body taught me —
written for the version of me who starts this again, and for you, if you're
about to.

### The thing I actually came away with

I expected to learn robotics. What I got instead was an education in **how
astonishing it is that anything works at all.**

Getting this duck to *reliably power on* — not walk, not balance, just come up
the same way twice — took longer than every software problem in the project
combined. Two cells, some basic robotic cabling, one microcontroller. That's
nearly the simplest possible system, and it still demanded that mechanical,
electrical, and compute all be correct simultaneously, along with a fourth
thing: how the duck thinks. A loose battery contact and a bad ground both
present as *"the software doesn't work."*

Several times a year I get into a large metal compartment with jutting sheets
of metal, shaped vaguely like a bird, and trust it with my life at 30,000 feet.
The landing gear. The wiring harness. Every microcontroller. Every actuator on
every aileron. The cockpit. Those aircraft are checked rigorously before each
flight — and then they fly again, and again, and again, for years.

I could not get a duck to boot twice in a row.

### Miles per touch

Somewhere in the middle of this I started thinking in a metric I haven't seen
named anywhere, so I'll name it: **miles per touch.**

*Miles* is how far, or how long, a system runs on its own. *Touches* are every
moment a human has to intervene — reseat, resolder, reflash, reboot, reason
about. You want to maximize the fraction.

It reframes what engineering maturity actually is. A first build has a
miles-per-touch near zero: it runs for ninety seconds and then wants you. An
airliner's is enormous, and every point of that ratio was bought by someone,
once, finding a failure mode and designing it out permanently.

The measurement is also unforgiving in a way I like. It doesn't care how
elegant your architecture is. It asks one question: **did it need you?**

Almost everything I got right on this build, I got right by reducing touches —
verifying EEPROM writes on a fresh connection instead of trusting the report,
having the robot record its own state where a dead network couldn't hide it.
Almost everything that cost me days, cost me because I answered a question by
hand that a machine should have been answering.

### What the manual doesn't tell you

The instructions cover assembly order. They don't cover craft. These cost me
real time:

**Wires before screws.** Route and seat every wire before the fastener goes in.
A screw that has to come back out because a cable is trapped under it is not a
small loss — it's threadlock, disassembly, and a scratched printed part.

**Prove the connection before the final screw.** Once a joint is closed up, a
marginal crimp becomes a multi-hour debugging session with the whole leg in the
way. Tug it, measure it, *then* close it.

**Measure across your solder joints, not just at the pads.** A soldered
connection adds resistance. So does a crimp, a connector, a switch. The
idealized schematic has none of that, and the gap between the schematic and the
bench is exactly where your robot will misbehave. I found a fault only because
the voltage across two points that "should" have been identical wasn't.

**Tape each servo with its number before you begin.** Fourteen identical black
motors. By motor nine you will not remember which is which. This was the single
most useful instruction anyone gave me and it appears in no documentation
anywhere.

**Debug outward from power.** My first total failure — a completely silent
servo bus, every baud rate, every address, raw protocol pings — was *one 18650
not touching its contact.* I exonerated the software in two minutes and then
went looking for a clever cause anyway.

### Eight things to look out for

If you're building this, these are the traps, in the order they'll find you:

1. **The board's USB-C is data only.** Servos get power from the barrel jack.
   An unpowered bus is *silent*, not degraded — it looks exactly like a
   software problem.
2. **Unconfigured servos all answer to id 1.** Put exactly one motor on the bus
   at a time until each has its own address.
3. **EEPROM writes fail silently.** A config tool that reads its own writes
   back inside the same connection proves nothing. Reconnect and re-read.
4. **USB-C-to-USB-C won't charge the pack.** Cheap boards omit the 5.1 kΩ CC
   pull-downs, so the charger never offers power. USB-A-to-C works.
5. **Never hot-plug the barrel jack.** The servo board's bulk capacitors are
   empty; connecting them to a live pack is a near short. The pack sags
   (I measured 6.56 V → ~3 V), the regulator drops out, the Pi dies instantly.
   Connect it with the switch **off**, then switch on.
6. **Ground topology is not a detail.** I had the barrel jack's ground soldered
   straight to the BMS, bypassing the switch. That's a ground loop: servo
   return current flowed through the regulator's ground path and corrupted its
   reference. Everything downstream looked haunted until it was resoldered so
   both grounds meet at one node.
7. **The undervoltage flag can't see a fast collapse.** `vcgencmd get_throttled`
   needs the chip still *running* at a degraded voltage to latch anything. Mine
   read clean through a failure that killed the Pi outright.
8. **Instrument the SD card before first boot.** The boot partition is FAT32 and
   readable by any computer. Have the robot log its own state there. When it
   stops answering the network, the network is the last thing you can ask.

### A few moments worth keeping

> First reading back from a live motor:
> `FEETECH_STS3215 · 7.3V · 26°C · position 179.91`.
> A thing on my desk answered a question.

> All fourteen named in one sitting. A pile of identical black servos became a
> right leg, a left leg, and a head — entirely because of masking tape and a
> number written in EEPROM. Nothing about them changed physically. They're just
> *addressable* now.

> So much heft and bulk behind a robot this small. New respect for good physical
> design. Good physical design is more impressive to me right now than good
> software design. Maybe I'm just jaded by software.

> `responding 14 / 14` — every motor answering on one bus, through the Pi, on a
> robot I assembled with my hands. Not walking yet. But I asked, and it answered.

### Where it stands

Body assembled. Power system proven — including deliberate abuse: abrupt cuts,
one of them mid-write, with no filesystem damage. Fourteen motors answering on
a single bus through the Pi's own nervous system. Torque off, joints limp,
waiting.

Next it gets a mind — someone else's first, trained a few million falls at a
time in simulation, dropped in as a single file. Then its own.
