#!/usr/bin/env python
"""Read find_soft_offsets.py's output and write the offsets into duck_config.json.

Upstream prints fourteen decimal numbers and tells you to copy them by hand.
One transposed digit is a duck that limps for a reason you will not find.

Parses the LAST "Current offsets :" block in the log -- the script reprints the
full set after every joint, so the last one is the complete answer.

    python scripts/apply_offsets.py --log ~/offsets-2026-08-28-1830.log
    python scripts/apply_offsets.py --log ... --config ~/duck_config.json --write
"""
import argparse
import json
import math
import pathlib
import re

EXPECTED = {"left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee",
            "left_ankle", "neck_pitch", "head_pitch", "head_yaw", "head_roll",
            "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee",
            "right_ankle"}

ap = argparse.ArgumentParser()
ap.add_argument("--log", required=True)
ap.add_argument("--config", default=str(pathlib.Path.home() / "duck_config.json"))
ap.add_argument("--write", action="store_true", help="actually modify the config")
a = ap.parse_args()

text = pathlib.Path(a.log).read_text()
blocks = text.split("Current offsets :")
if len(blocks) < 2:
    raise SystemExit("no 'Current offsets :' block in that log — did the run finish?")

found = {}
for line in blocks[-1].splitlines():
    m = re.match(r"\s*([a-z_]+)\s*:\s*(-?[\d.eE+]+)\s*$", line)
    if m and m.group(1) in EXPECTED:
        found[m.group(1)] = float(m.group(2))

print(f"{'joint':<17}{'offset (rad)':>14}{'= deg':>9}")
print("-" * 40)
for k in sorted(found):
    print(f"{k:<17}{found[k]:>14.4f}{math.degrees(found[k]):>9.2f}")
print("-" * 40)

missing = EXPECTED - set(found)
if missing:
    print(f"MISSING {len(missing)}: {sorted(missing)}")
    print("(skipped joints keep their existing value)")

big = {k: v for k, v in found.items() if abs(math.degrees(v)) > 45}
if big:
    print("\nWorth a second look — over 45 degrees is a lot for a calibration offset:")
    for k, v in big.items():
        print(f"   {k:<17}{math.degrees(v):+8.2f} deg")

cfg_path = pathlib.Path(a.config)
cfg = json.loads(cfg_path.read_text())
before = dict(cfg.get("joints_offsets", cfg.get("joints_offset", {})))
key = "joints_offsets" if "joints_offsets" in cfg else "joints_offset"

if not a.write:
    print(f"\nDRY RUN. Would update {len(found)} of {len(before)} entries in "
          f"{cfg_path}.\nRe-run with --write to apply.")
    raise SystemExit(0)

cfg[key].update(found)
backup = cfg_path.with_suffix(".json.bak")
backup.write_text(json.dumps({key: before}, indent=4))
cfg_path.write_text(json.dumps(cfg, indent=4))
print(f"\nwrote {len(found)} offsets to {cfg_path}")
print(f"previous values saved to {backup}")
