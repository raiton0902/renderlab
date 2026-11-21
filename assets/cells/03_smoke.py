# STEP 3 of 5 — Quick test with a few frames.
# This proves the render works before the long step. About 30 seconds.
import shutil, subprocess, sys, time
from pathlib import Path

OUTDIR = ROOT / "out"
OUTDIR.mkdir(parents=True, exist_ok=True)
SMOKE_OUT = OUTDIR / "_smoke.mp4"
if SMOKE_OUT.exists():
    SMOKE_OUT.unlink()


def run(cmd):
    """Run a command, show its output live, return (code, last_lines, seconds)."""
    t0 = time.time()
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    tail = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            print("   " + line, flush=True)
        tail.append(line)
        tail = tail[-25:]
    code = proc.wait()
    return code, tail, time.time() - t0


smoke_end = min(SMOKE, TOTAL)
print("Rendering %d test frames out of %d..." % (smoke_end, TOTAL))
cmd = [sys.executable, ENTRY, "--start", "0", "--end", str(smoke_end),
       "--out", str(SMOKE_OUT)] + ARGS
code, tail, secs = run(cmd)

ok = code == 0 and SMOKE_OUT.exists() and SMOKE_OUT.stat().st_size > 20000
if not ok:
    reason = "The renderer stopped with error code %d." % code
    if code == 0:
        reason = "The renderer reported success but wrote no usable video file."
    fail(
        "The quick test failed.",
        reason + "\n\nLast lines of output:\n" + "\n".join(tail[-15:]),
        "Copy the lines above and send them to the assistant.\n"
        "Nothing was lost: the full video has not started yet.",
    )

size_mb = SMOKE_OUT.stat().st_size / 1e6
print()
print("SMOKE TEST PASSED — %d frames in %.0f s (%.1f MB)." % (smoke_end, secs, size_mb))
if EST:
    print("The full render will take about %d minutes." % int(EST))
print()
print("Now run STEP 4 (the full render).")
