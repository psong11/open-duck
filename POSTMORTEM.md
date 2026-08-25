# What went wrong, and the rules that come out of it

Not a confession list. Every rule below is here because breaking it cost real
hours on this build, and each one names the concrete trigger that should fire
next time.

---

## 1. Never state a fact about hardware you have not checked

**Trigger:** you are about to write a sentence about how a component behaves,
and the source is your own recall.

This was the dominant failure mode by a wide margin:

- Claimed the servo board's control-mode jumper belonged on **A (UART)**. Wrong —
  the runtime hardcodes `/dev/ttyACM0`, which is USB CDC. It stays on **B**.
- Claimed mDNS didn't resolve on this network. I had tested
  `raspberrypi.local`; the hostname is `ezer`. `ezer.local` worked the whole time.
- Declared "no Raspberry Pi OUI anywhere" from an incomplete vendor list.
  `88:A2:9E` is Raspberry Pi Trading.
- Diagnosed a dying SD card. It was a seating problem.
- Diagnosed a boot failure by looking for `firstrun.sh`. Pi OS trixie uses
  cloud-init; that file does not exist and its absence meant nothing.
- Said 0V at a BMS output "is not a fault." It is a documented fault signature.
- Presented a solder order as spec when it is hobby convention.

**Rule:** check it, or mark it as a guess in the same sentence. "I believe" is
cheap. A retraction three steps later is not — it poisons everything built on
top of it.

Paul's version, which was right: *"Any instructions you give me should be
grounded in something that's documented online or something that's clear
common sense from an electrical engineering standpoint."*

---

## 2. A test whose failure mode looks like a real result is worse than no test

**Trigger:** you are about to report a negative result from a command you did
not confirm actually ran.

- Reported "no cp313 wheel" for the runtime's pinned packages. `pip3` **did not
  exist** on the image. Command-not-found was being read as wheel-not-found.
  The conclusion happened to be right, which is worse — it means luck covered
  for method.
- A background watcher printed "EZER IS UP" while the verification lines below
  it showed 0 packets received.
- `configure_motor.py` read its own writes back inside the same connection,
  which proves nothing about EEPROM. Motor 30 reported success with
  `max_acceleration` still at the factory 50.
- A reboot watcher polled for 40 seconds — shorter than a Pi Zero takes to
  boot — then reported "did not return."

**Rule:** separate "the check failed" from "the check could not run." Assert a
known-good control first. When waiting on hardware, know the real timing
before choosing a window: **wifi associates at `up=43s` on this Pi**, measured
across four boots.

---

## 3. Do not modify the system you are trying to diagnose

**Trigger:** you are about to edit a config file on the machine that is
currently misbehaving.

Mid-investigation I added `console=ttyGS0,115200` to `cmdline.txt` and made it
the *last* console, which makes it `/dev/console`. With no USB host attached,
that is a console with nothing on the other end. Whatever the next boot did,
it was no longer comparable to the previous ones — I had changed the
experiment while running it.

**Rule:** if a change is needed to observe, say plainly that the run is no
longer a clean comparison, and keep a backup so the original state is
recoverable. `cmdline.txt.bak` existed; the warning came late.

---

## 4. When a failure is intermittent, build the recorder before the next occurrence

**Trigger:** you are about to ask for the same one-bit check a second time.

Six rounds of `ping` and `arp` sweeps produced one bit each — *is it there* —
and never once said why not. Every round cost Paul a physical action.

Paul: *"Why can you not just predict what's going to happen in the future and
create whatever scripts you need to... I can't keep on doing everything that
you just ask me to do because I don't have time and the money for this."*

He was right, and the fix was available from day one: the boot partition is
FAT32 and readable by any computer, so the Pi can record its own state
somewhere the network cannot hide.

**Rule:** ask *what will I wish I had been recording when this fails again?*
Then record it now. Instrument in one shot at install time, so there is
exactly one manual step ever — not one per hypothesis.

---

## 5. Test the diagnostic tooling itself, against data that looks like failure

**Trigger:** you are about to ship a script whose whole job is to work during
an emergency.

Testing the black box found six defects in it before it mattered, and two more
that only a real power cut exposed:

- `systemctl restart` fires `ExecStop`, which wrote `CLEAN STOP` — **forging
  the exact marker the power-cut test depends on.**
- The Pi Zero 2W has no RTC, so `ts=` is wrong until NTP syncs. A new boot's
  mark can appear to *precede* the previous boot's last sample. `up=` is
  monotonic; reason with that.
- The reader counted a recorder restart as a hard power cut.
- A mount-ordering race would have written early samples to the root
  filesystem, where the real `/boot/firmware` mount then hid them.
- `perl -pi` silently expanded `$(date …)` into garbage inside a `runcmd`.
- journald was still volatile and `bootsnap` had never run — both assumed
  working, both were not.

**Rule:** run the tooling against synthetic failure data before trusting it,
then against the first real event. A broken reader at the critical moment
costs a whole cycle.

---

## 6. Scaffold explanations; density is the failure mode, not length

**Trigger:** you are about to introduce more than one unfamiliar term in a
paragraph.

Paul, on the first response of this project: *"It's hard, if I'm being honest,
to digest all the information... I haven't even started yet, and you're already
telling me to commit `uv.lock`, and I don't even know what that file is."*

**Rule:** mental model first, jargon deferred, dense reference into a repo file
rather than the chat.

---

## 7. Report what a signal cannot tell you, not just what it can

**Trigger:** an instrument reads clean and you are about to call that evidence
of health.

Plugging in the barrel jack killed the Pi instantly, and `thr` read `0x0` on
every one of the 97 samples — including the last one before death. That is not
"power was fine." `vcgencmd get_throttled` needs the SoC to still be *running*
at a degraded voltage to latch anything. A rail that collapses outright leaves
no trace in it.

**Rule:** know each instrument's blind spot and say it out loud. The failure
was caught by a different field entirely — a boot mark with no `CLEAN STOP`.

---

## The corrections, for the record

Battery-pack requirement asserted without a source · BMS 0V fault signature ·
solder order stated as spec · FD/CD pads claimed unused · mDNS · Raspberry Pi
OUI · "SD card is dying" · UART jumper position · USB-wrong-port theory ·
`firstrun.sh` · pip3 wheel test · false-positive watcher · watcher window too
short · PARTUUID change nearly reported as corruption (caught by checking
`fdisk` first).
