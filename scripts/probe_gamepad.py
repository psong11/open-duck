#!/usr/bin/env python
"""Discover how YOUR gamepad enumerates, and whether it matches what the
runtime expects.

xbox_controller.py hardcodes indices for an Xbox pad paired over Bluetooth on
Linux: sticks on axes 0-3, triggers on 4-5, A/B/X/Y on buttons 0/1/3/4, LB/RB
on 6/7. A GameSir in the wrong mode enumerates differently, and the duck would
receive garbage as velocity commands.

Press things. It prints what changed.

    python scripts/probe_gamepad.py
"""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")   # headless Pi
import pygame

EXPECT = {"axes": {0: "left stick X", 1: "left stick Y", 2: "right stick X",
                   3: "right stick Y", 4: "RIGHT trigger", 5: "LEFT trigger"},
          "buttons": {0: "A", 1: "B", 3: "X", 4: "Y", 6: "LB", 7: "RB"}}

pygame.init()
pygame.joystick.init()
if pygame.joystick.get_count() == 0:
    raise SystemExit("No gamepad seen by SDL. Is it paired AND connected?\n"
                     "  bluetoothctl -> info <MAC> should say Connected: yes")

js = pygame.joystick.Joystick(0)
js.init()
print(f"name    : {js.get_name()}")
print(f"axes    : {js.get_numaxes()}   (runtime needs at least 6)")
print(f"buttons : {js.get_numbuttons()}  (runtime needs at least 8)")
print(f"hats    : {js.get_numhats()}    (runtime needs at least 1)")
print()
if js.get_numaxes() < 6 or js.get_numbuttons() < 8:
    print("!! Fewer inputs than the runtime indexes. It will crash or misread.")
    print("   Try a different controller mode (Xbox/XInput) and re-pair.\n")

print("Press buttons and move sticks. Ctrl-C when done.\n")
base = [round(js.get_axis(i), 2) for i in range(js.get_numaxes())]
try:
    while True:
        pygame.event.pump()
        for i in range(js.get_numaxes()):
            v = round(js.get_axis(i), 2)
            if abs(v - base[i]) > 0.35:
                print(f"  axis {i:<2} = {v:+5.2f}   runtime thinks this is: "
                      f"{EXPECT['axes'].get(i, '(unused)')}")
                base[i] = v
        for i in range(js.get_numbuttons()):
            if js.get_button(i):
                print(f"  button {i:<2} pressed   runtime thinks this is: "
                      f"{EXPECT['buttons'].get(i, '(unused)')}")
                time.sleep(0.25)
        for i in range(js.get_numhats()):
            h = js.get_hat(i)
            if h != (0, 0):
                print(f"  hat {i} = {h}   (runtime uses hat 0, vertical axis)")
                time.sleep(0.25)
        time.sleep(0.03)
except KeyboardInterrupt:
    print("\ndone.")
