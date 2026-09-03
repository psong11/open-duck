import json, os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.expanduser("~/Documents/personal_projects/open-duck/scripts"))
import duck_fall

# Her real resting vector, measured on the robot today.
REST = np.array([-5.14, 1.22, 8.23])
REST_HAT = REST / np.linalg.norm(REST)

def vec_at(deg, mag=9.81):
    """A gravity vector `deg` away from REST, in the REST/x-ish plane."""
    # build an orthonormal basis around REST_HAT
    tmp = np.array([0.0, 1.0, 0.0])
    perp = np.cross(REST_HAT, tmp); perp /= np.linalg.norm(perp)
    r = np.radians(deg)
    return mag * (np.cos(r) * REST_HAT + np.sin(r) * perp)

tmp = tempfile.mkdtemp()
ref_file = os.path.join(tmp, "fall_reference.json")
json.dump({"reference": REST.tolist()}, open(ref_file, "w"))

fails = []
def check(name, got, want):
    ok = got == want
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))
    if not ok: fails.append(name)

def mk(**env):
    for k in ("DUCK_FALL_DEG","DUCK_FALL_REL","DUCK_FALL_TICKS","DUCK_FALL_ARM"):
        os.environ.pop(k, None)
    os.environ.update({k: str(v) for k, v in env.items()})
    duck_fall.REF_PATH = ref_file
    return duck_fall.FallWatch()

print("\n1. no reference file -> disabled, never fires")
duck_fall.REF_PATH = os.path.join(tmp, "nope.json")
w = duck_fall.FallWatch()
for _ in range(50): w.update(vec_at(180))
check("disabled never fires", w.poll(), None)

print("\n2. standing still at the tared pose -> silent")
w = mk(DUCK_FALL_DEG=50, DUCK_FALL_TICKS=8)
for _ in range(100): w.update(vec_at(0.3))
check("upright silent", w.poll(), None)
check("tilt ~0", round(w.tilt), 0)

print("\n3. over threshold but too briefly -> silent")
w = mk(DUCK_FALL_DEG=50, DUCK_FALL_TICKS=8)
for _ in range(7): w.update(vec_at(70))
check("7 ticks of 8 silent", w.poll(), None)

print("\n4. sustained -> fires exactly once")
w = mk(DUCK_FALL_DEG=50, DUCK_FALL_TICKS=8)
for _ in range(8): w.update(vec_at(70))
first = w.poll()
check("fires on the 8th", first is not None, True)
print("     message:", first)
for _ in range(200): w.update(vec_at(70))
check("stays latched while down", w.poll(), None)

print("\n5. recover below release, fall again -> fires again")
for _ in range(20): w.update(vec_at(10))
check("silent on recovery", w.poll(), None)
for _ in range(8): w.update(vec_at(80))
check("re-arms after recovery", w.poll() is not None, True)

print("\n6. hovering between release and trigger does NOT re-fire")
w = mk(DUCK_FALL_DEG=50, DUCK_FALL_REL=35, DUCK_FALL_TICKS=8)
for _ in range(8): w.update(vec_at(60))
w.poll()
for _ in range(30): w.update(vec_at(40))   # under trigger, over release
for _ in range(30): w.update(vec_at(60))   # back over trigger
check("no re-fire while hovering", w.poll(), None)

print("\n7. self-acceleration samples are discarded, not counted")
w = mk(DUCK_FALL_DEG=50, DUCK_FALL_TICKS=8)
for _ in range(50): w.update(vec_at(70, mag=25.0))   # hard footfall, |a|=25
check("out-of-band never fires", w.poll(), None)
for _ in range(50): w.update(vec_at(70, mag=2.0))    # free fall, |a|=2
check("low-|a| never fires", w.poll(), None)
check("tilt untouched by bad samples", w.tilt, 0.0)

print("\n8. armed flag comes from the environment")
check("shadow by default", mk().armed, False)
check("default trigger is collapse-only", mk().deg, 65.0)
check("default release", mk().rel, 45.0)
check("armed when asked", mk(DUCK_FALL_ARM=1).armed, True)
w = mk(DUCK_FALL_ARM=0, DUCK_FALL_DEG=50, DUCK_FALL_TICKS=2)
for _ in range(2): w.update(vec_at(70))
check("shadow message says so", "(shadow)" in w.poll(), True)

print("\n9. take_max reports the peak, then decays to current")
w = mk(DUCK_FALL_DEG=50, DUCK_FALL_TICKS=8)
w.update(vec_at(5)); w.update(vec_at(41)); w.update(vec_at(5))
check("peak captured", w.take_max(), 41.0)
check("resets to current", w.take_max(), round(w.tilt,1))

print("\n10. a total collapse must clear the trigger with margin")
w = mk(DUCK_FALL_TICKS=8)          # 65 deg default
for _ in range(8): w.update(vec_at(90))   # flat on the floor
check("90 deg collapse fires at the default", w.poll() is not None, True)
w = mk(DUCK_FALL_TICKS=8)
for _ in range(60): w.update(vec_at(30))  # a deep but honest forward lean
check("30 deg lean stays silent", w.poll(), None)
naive = np.degrees(np.arccos(np.dot(REST_HAT, [0,0,1])))
print(f"     a slumped/limp pose read {naive:.1f} deg from +Z")

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
