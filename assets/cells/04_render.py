# STEP 4 of 5 — Render the whole video. This is the long step.
# Keep the tab open. If it stops, run this cell again: finished parts are skipped.
import shutil, subprocess, sys, time
from pathlib import Path

if "run" not in globals() or "TOTAL" not in globals():
    print("Run STEP 1, STEP 2 and STEP 3 first — this step needs them.")
    raise SystemExit(1)

OUTDIR = ROOT / "out"
OUTDIR.mkdir(parents=True, exist_ok=True)

chunks = [(s, min(s + CHUNK, TOTAL)) for s in range(0, TOTAL, CHUNK)]
print("Rendering %d frames in %d part(s) of up to %d frames each."
      % (TOTAL, len(chunks), CHUNK))
print()

started = time.time()
done_frames = 0.0
finished = []

for i, (s, e) in enumerate(chunks, 1):
    target = OUTDIR / ("chunk_%04d.mp4" % i)
    finished.append(target)
    if target.exists() and target.stat().st_size > 20000:
        print("Part %d/%d — already finished, skipping." % (i, len(chunks)), flush=True)
        done_frames += e - s
        continue

    print("Part %d/%d — frames %d to %d  (%.0f%% of the video)"
          % (i, len(chunks), s, e, 100.0 * e / TOTAL), flush=True)
    cmd = [sys.executable, ENTRY, "--start", str(s), "--end", str(e),
           "--out", str(target)] + ARGS
    code, tail, secs = run(cmd)

    if code != 0 or not target.exists() or target.stat().st_size < 20000:
        fail(
            "Rendering stopped at part %d of %d." % (i, len(chunks)),
            "Error code %d.\n\nLast lines of output:\n%s" % (code, "\n".join(tail[-20:])),
            "Copy the lines above and send them to the assistant.\n"
            "Parts already finished are still on disk: run STEP 4 again after the fix "
            "and it will continue from part %d." % i,
        )

    done_frames += e - s
    elapsed = time.time() - started
    if done_frames > 0:
        left = (TOTAL - done_frames) / (done_frames / elapsed) / 60.0
        print("   part done in %.0f s — about %.0f minute(s) left" % (secs, left), flush=True)
    print()

# --- join the parts ----------------------------------------------------
final = ROOT / OUTPUT
final.parent.mkdir(parents=True, exist_ok=True)
if final.exists():
    final.unlink()

if len(finished) == 1:
    shutil.move(str(finished[0]), str(final))
    print("Video written: %s" % final)
else:
    if not shutil.which("ffmpeg"):
        fail(
            "Joining the parts failed.",
            "The video tool ffmpeg is not available in this session.",
            "Send this line to the assistant: NO_FFMPEG",
        )
    listing = OUTDIR / "parts.txt"
    listing.write_text(
        "".join("file '%s'\n" % p.name for p in finished), encoding="utf-8"
    )
    print("Joining %d parts into one file..." % len(finished))
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", listing.name, "-c", "copy", "-movflags", "+faststart",
         str(final)],
        cwd=str(OUTDIR), text=True, capture_output=True,
    )
    if proc.returncode != 0 or not final.exists():
        fail(
            "Joining the parts failed.",
            (proc.stderr or "")[-1500:],
            "Copy the lines above and send them to the assistant.\n"
            "The finished parts are still on disk, so nothing needs re-rendering.",
        )

if not final.exists() or final.stat().st_size < 20000:
    fail(
        "The video file is missing or empty.",
        "Expected: %s" % final,
        "Send this line to the assistant: NO_OUTPUT",
    )

print()
print("RENDER FINISHED — %.1f MB in %.0f minute(s)." % (final.stat().st_size / 1e6, (time.time() - started) / 60.0))
print("Now run STEP 5 to collect the file.")
