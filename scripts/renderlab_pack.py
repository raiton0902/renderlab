#!/usr/bin/env python
"""renderlab_pack.py - build a Google Colab render kit from a portable render project.

    python renderlab_pack.py --project <dir> --dist <dir>

Reads <dir>/renderlab.json, stats every declared file, then writes:

    Renderlab_<name>.ipynb
    Renderlab_<name>_package.zip
    RENDER_IN_COLAB.md

No third-party dependencies. Fails loudly instead of building a partial kit.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CELLS = HERE.parent / "assets" / "cells"


def cell_text(filename: str) -> str:
    """Cell templates ship as files next to this script.

    A marketplace sandbox may run the script alone from a temporary file, where
    ``assets/cells`` does not exist; the generated copy at the bottom of this
    file is used then. ``--selfcheck`` keeps the two in sync.
    """
    path = CELLS / filename
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if filename in _EMBEDDED_CELLS:
        return _EMBEDDED_CELLS[filename]
    die("cell template missing: %s (and no embedded copy)" % filename)
MANIFEST_NAME = "renderlab_manifest.json"
ZIP_DATE = (2020, 1, 1, 0, 0, 0)

REQUIRED = ("name", "title", "entry", "output", "total_frames", "files")
DEFAULTS = {
    "fps": 30,
    "smoke_frames": 24,
    "chunk_frames": None,
    "deps": [],
    "imports": [],
    "optional_imports": [],
    "entry_args": [],
    "est_minutes": None,
    "notes": "",
}


class PackError(SystemExit):
    pass


def die(msg: str) -> None:
    print("renderlab: " + msg, file=sys.stderr)
    raise SystemExit(2)


def load_manifest(project: Path) -> dict:
    path = project / "renderlab.json"
    if not path.is_file():
        die("no renderlab.json in %s" % project)
    try:
        m = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        die("renderlab.json is not valid JSON: %s" % exc)

    missing = [k for k in REQUIRED if k not in m]
    if missing:
        die("renderlab.json is missing: %s" % ", ".join(missing))
    for key, value in DEFAULTS.items():
        m.setdefault(key, value)
    if not m["chunk_frames"]:
        m["chunk_frames"] = int(m["total_frames"])
    return m


def validate(project: Path, m: dict) -> list[Path]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,40}", m["name"]):
        die("name must be a slug like 'laura13' (lowercase, digits, - or _)")
    if not isinstance(m["files"], list) or not m["files"]:
        die("files must be a non-empty list")
    if len(set(m["files"])) != len(m["files"]):
        die("files contains duplicates")

    if m["entry"] not in m["files"]:
        die("entry %r is not in files" % m["entry"])

    out = Path(m["output"])
    if out.is_absolute() or ".." in out.parts:
        die("output must be a relative path inside the package")

    if int(m["total_frames"]) <= 0:
        die("total_frames must be positive")
    if int(m["smoke_frames"]) <= 0 or int(m["smoke_frames"]) > int(m["total_frames"]):
        die("smoke_frames must be between 1 and total_frames")
    if int(m["chunk_frames"]) <= 0:
        die("chunk_frames must be positive")

    resolved = []
    missing = []
    for rel in m["files"]:
        p = project / rel
        if not p.is_file():
            missing.append(rel)
        else:
            resolved.append(p)
    if missing:
        die("declared files missing from the project:\n  " + "\n  ".join(missing))
    return resolved


def build_zip(project: Path, files: list[Path], m: dict, dest: Path) -> Path:
    manifest = dict(m)
    manifest["files"] = list(m["files"])
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        info = zipfile.ZipInfo(MANIFEST_NAME, date_time=ZIP_DATE)
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, json.dumps(manifest, indent=2, ensure_ascii=False))
        for rel in m["files"]:
            src = project / rel
            arc = Path(rel).as_posix()
            info = zipfile.ZipInfo(arc, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, src.read_bytes())
    return dest


def verify_zip(zip_path: Path, m: dict) -> None:
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        bad = z.testzip()
    if bad:
        die("zip is corrupt at %s" % bad)
    expect = set(m["files"]) | {MANIFEST_NAME}
    absent = expect - names
    if absent:
        die("zip is missing entries: %s" % ", ".join(sorted(absent)))
    extra = names - expect
    if extra:
        die("zip has unexpected entries: %s" % ", ".join(sorted(extra)))


def source_lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if lines and lines[-1].endswith("\n"):
        lines[-1] = lines[-1][:-1]
    return lines


def code_cell(text: str, cell_id: str) -> dict:
    return {
        "cell_type": "code",
        "id": cell_id,
        "metadata": {"cellView": "form"},
        "execution_count": None,
        "outputs": [],
        "source": source_lines(text),
    }


def markdown_cell(text: str, cell_id: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {},
        "source": source_lines(text),
    }


def build_notebook(m: dict, dest: Path) -> Path:
    files = {
        "00_intro.md": "intro",
        "01_unpack.py": "step1",
        "02_install.py": "step2",
        "03_smoke.py": "step3",
        "04_render.py": "step4",
        "05_deliver.py": "step5",
    }
    tokens = {
        "{{TITLE}}": m["title"],
        "{{NAME}}": m["name"],
        "{{ZIPNAME}}": "Renderlab_%s_package.zip" % m["name"],
    }
    cells = []
    for filename, cell_id in files.items():
        text = cell_text(filename)
        for key, value in tokens.items():
            text = text.replace(key, value)
        if "{{" in text:
            die("unreplaced token in %s" % filename)
        if filename.endswith(".md"):
            cells.append(markdown_cell(text, cell_id))
        else:
            cells.append(code_cell(text, cell_id))

    nb = {
        "cells": cells,
        "metadata": {
            "colab": {"provenance": [], "toc_visible": True},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    dest.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    json.loads(dest.read_text(encoding="utf-8"))
    return dest


def build_readme(m: dict, zip_name: str, nb_name: str, dest: Path) -> Path:
    est = m.get("est_minutes")
    est_line = ("It takes about %d minutes on the free plan." % int(est)) if est else ""
    note = (m.get("notes") or "").strip()
    text = f"""# {m['title']} â€” render on Google Colab

You do not need Python, and you do not edit anything. The free Colab plan is enough.

## What you need

Two files, both in the same folder as this text:

- `{nb_name}` â€” the notebook
- `{zip_name}` â€” the package (keep the name exactly as it is)

## Steps

1. Open <https://colab.research.google.com> and sign in with any Google account.
2. `File` â†’ `Upload notebook` â†’ choose `{nb_name}`.
3. Press the play button on **STEP 1**. A file picker opens: choose `{zip_name}`.
   Wait for `Package ready`.
4. Press play on **STEP 2**, wait for `Tools ready`.
5. Press play on **STEP 3**. It renders 24 test frames. Wait for `SMOKE TEST PASSED`.
   If this fails, stop and send the printed box to the assistant â€” nothing is lost.
6. Press play on **STEP 4**. This is the long part. {est_line}
   Keep the tab open. If the cell stops with an error, run STEP 4 again: finished parts are skipped.
   A disconnect ends the session and deletes its files: upload the package again and start at STEP 1.
7. Press play on **STEP 5**. It prints where the video is.

## Getting the file out

- `Files` icon on the left â†’ `{m['name']}` â†’ `{Path(m['output']).parent.as_posix()}` â†’ `{Path(m['output']).name}` â†’ right-click â†’ **Download**
- or take the copy STEP 5 saves to your Google Drive

Never use a "files.download" button: on a large video it can hang with no error.

## If something goes wrong

Every failure prints a box:

```
PROBLEM: <what broke>
WHAT TO DO: <what to do>
```

Copy the whole box to the assistant. The usual causes:

| Message | Meaning |
|---|---|
| The package was not uploaded | Run STEP 1 again and choose the zip |
| The package is incomplete | Packaging bug: send the `MISSING=` line |
| A required tool is missing | Send the `MISSING_DEP=` line; the kit gets rebuilt |
| The quick test failed | Send the last lines; the full render never started |
| Rendering stopped at part N | Run STEP 4 again; it continues from that part |

## Honest limits of the free plan

- About 12 GB of memory and a shared CPU: {est_line or 'the render is sized for this.'}
- The tab must stay open. Closing it ends the session and deletes the files in it.
- A session ends after roughly 12 hours, or sooner if it idles too long.
- Download the video in the same session. A finished render is not stored anywhere else.

{('## Note\n\n' + note) if note else ''}
"""
    dest.write_text(text, encoding="utf-8")
    return dest


def selfcheck() -> int:
    """Verify the embedded cell copies are byte-identical to assets/cells."""
    order = ["00_intro.md", "01_unpack.py", "02_install.py",
             "03_smoke.py", "04_render.py", "05_deliver.py"]
    stale = []
    for name in order:
        path = CELLS / name
        if not path.is_file():
            stale.append(name + " (file missing)")
        elif _EMBEDDED_CELLS.get(name) != path.read_text(encoding="utf-8"):
            stale.append(name)
    if stale:
        print("renderlab: embedded cells are stale: " + ", ".join(stale), file=sys.stderr)
        print("renderlab: regenerate them with tools/embed_cells.py", file=sys.stderr)
        return 1
    print("renderlab: embedded cells match assets/cells (%d files)" % len(order))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build a Colab render kit.")
    ap.add_argument("--project", help="folder holding renderlab.json")
    ap.add_argument("--dist", help="output folder")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verify the embedded cell copies match assets/cells, then exit")
    args = ap.parse_args(argv)

    if args.selfcheck:
        return selfcheck()
    if not args.project or not args.dist:
        ap.error("--project and --dist are required (unless --selfcheck)")

    project = Path(args.project).resolve()
    dist = Path(args.dist).resolve()
    if not project.is_dir():
        die("project folder not found: %s" % project)
    dist.mkdir(parents=True, exist_ok=True)

    m = load_manifest(project)
    files = validate(project, m)

    zip_name = "Renderlab_%s_package.zip" % m["name"]
    nb_name = "Renderlab_%s.ipynb" % m["name"]
    zip_path = dist / zip_name
    nb_path = dist / nb_name
    readme_path = dist / "RENDER_IN_COLAB.md"

    build_zip(project, files, m, zip_path)
    verify_zip(zip_path, m)
    build_notebook(m, nb_path)
    build_readme(m, zip_name, nb_name, readme_path)

    total_mb = sum(p.stat().st_size for p in files) / 1e6
    print("renderlab: packaged %s" % m["name"])
    print("  files   : %d (%.1f MB, zip %.1f MB)" % (len(files), total_mb, zip_path.stat().st_size / 1e6))
    print("  frames  : %d @ %.2f fps, chunks of %d, smoke %d"
          % (int(m["total_frames"]), float(m["fps"]),
             int(m["chunk_frames"]), int(m["smoke_frames"])))
    print("  notebook: %s" % nb_path)
    print("  package : %s" % zip_path)
    print("  readme  : %s" % readme_path)
    if total_mb > 200:
        print("  WARNING : package is over 200 MB; uploads may time out. Tell the user to "
              "put the zip in Google Drive instead.", file=sys.stderr)
    print("renderlab: next step is scripts/renderlab_selftest.py --dist %s" % dist)
    return 0


# --- BEGIN EMBEDDED CELLS (generated by tools/embed_cells.py - do not edit by hand)
_EMBEDDED_CELLS = {
    '00_intro.md': r'''# {{TITLE}}

This notebook renders the video. You do not need to know Python, and you must not edit any cell.

**How to use it**

1. Press the play button on each step, in order: STEP 1, then 2, 3, 4, 5.
2. Wait for the message at the end of a step before starting the next one.
3. Keep this browser tab open while it renders. Closing it stops the render.
4. STEP 5 tells you where the finished video is.

**You need:** the file `{{ZIPNAME}}` (the package that came with this notebook). Nothing else, no installation on your computer. The free Colab plan is enough.

**If something goes wrong**, the cell prints a box that starts with `PROBLEM:` and tells you what to do. Copy that box to the assistant. Nothing is lost — you can run the step again.
''',
    '01_unpack.py': r'''# STEP 1 of 5 — Unpack the package.
# Press the play button at the left of this cell. Wait for "Package ready".
import json, os, shutil, sys, zipfile
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules
BASE = Path(os.environ.get("RENDERLAB_BASE", "/content"))
NAME = "{{NAME}}"
ZIPNAME = "{{ZIPNAME}}"
ROOT = BASE / NAME


def fail(title, detail, action):
    print()
    print("!" * 68)
    print("PROBLEM: " + title)
    if detail:
        print()
        print(detail)
    print()
    print("WHAT TO DO:")
    print(action)
    print("!" * 68)
    raise SystemExit(1)


print("=" * 68)
print("  {{TITLE}}")
print("  Render kit for Google Colab")
print("=" * 68)

# --- get the package ---------------------------------------------------
zip_path = BASE / ZIPNAME
if not zip_path.exists():
    env_zip = os.environ.get("RENDERLAB_ZIP")
    if env_zip and Path(env_zip).exists():
        BASE.mkdir(parents=True, exist_ok=True)
        shutil.copy2(env_zip, zip_path)
        print("Package found: %s" % zip_path)
    elif IN_COLAB:
        print("A file picker will open. Choose:  %s" % ZIPNAME)
        print("(If you uploaded it earlier in this session, press Cancel — the file is still there.)")
        from google.colab import files
        try:
            uploaded = files.upload()
        except Exception as exc:
            uploaded = {}
            print("The upload window closed without a file (%s)." % exc)
        zips = [p for p in uploaded if str(p).lower().endswith(".zip")]
        if zips:
            shutil.move(zips[0], str(zip_path))
            print("Package found: %s" % zip_path)
    if not zip_path.exists():
        fail(
            "The package was not uploaded.",
            "This notebook needs the file %s, uploaded next to it." % ZIPNAME,
            "Run this cell again and choose %s in the file picker.\n"
            "If no picker appears, click the folder icon on the left, then upload the file there." % ZIPNAME,
        )

# --- clean unpack ------------------------------------------------------
if ROOT.exists():
    shutil.rmtree(ROOT)
print("Unpacking... (a few seconds)")
ROOT.mkdir(parents=True)
with zipfile.ZipFile(zip_path) as z:
    z.extractall(ROOT)

manifest_path = ROOT / "renderlab_manifest.json"
if not manifest_path.exists():
    fail(
        "The package is incomplete.",
        "The file renderlab_manifest.json is not inside the zip.",
        "Send this line to the assistant: MISSING=renderlab_manifest.json",
    )
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

missing = [f for f in manifest["files"] if not (ROOT / f).exists()]
if missing:
    fail(
        "The package is incomplete.",
        "%d file(s) did not arrive:\n  %s" % (len(missing), "\n  ".join(missing[:10])),
        "This is a packaging bug, not your mistake.\n"
        "Send this line to the assistant: MISSING=" + ",".join(missing),
    )

# --- read the plan -----------------------------------------------------
TOTAL = int(manifest["total_frames"])
FPS = float(manifest.get("fps") or 30)
CHUNK = int(manifest.get("chunk_frames") or TOTAL)
SMOKE = int(manifest.get("smoke_frames") or 24)
ENTRY = manifest["entry"]
OUTPUT = manifest["output"]
ARGS = list(manifest.get("entry_args") or [])
DEPS = list(manifest.get("deps") or [])
IMPORTS = list(manifest.get("imports") or [])
OPTIONAL = list(manifest.get("optional_imports") or [])
EST = manifest.get("est_minutes")

total_bytes = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file())
print("Files unpacked: %d  (%.0f MB)" % (len(manifest["files"]), total_bytes / 1e6))
print("Video to render: %d frames = %.1f seconds at %.2f frames/second" % (TOTAL, TOTAL / FPS, FPS))
if EST:
    print("Expected time on free Colab: about %d minutes. Keep this tab open." % int(EST))
note = (manifest.get("notes") or "").strip()
if note:
    print("Note: " + note)
print()
print("Package ready. Now run STEP 2.")
''',
    '02_install.py': r'''# STEP 2 of 5 — Install the tools this render needs.
# Takes one or two minutes on a fresh session. Press play and wait.
import importlib, os, subprocess, sys


def _installed(module):
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


if os.environ.get("RENDERLAB_SKIP_INSTALL"):
    print("Tools already available on this machine. Skipping the download.")
elif DEPS:
    print("Downloading %d tool(s). This is normal and takes a minute..." % len(DEPS))
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--no-input",
         "--disable-pip-version-check", *DEPS],
        text=True,
    )
    if proc.returncode != 0:
        fail(
            "A tool could not be installed.",
            "The installer stopped with error code %d." % proc.returncode,
            "Run this cell one more time — it often succeeds on the second try.\n"
            "If it still fails, send this line to the assistant: PIP=" + " ".join(DEPS),
        )
else:
    print("No extra tools needed.")

missing = [m for m in IMPORTS if not _installed(m)]
extra_missing = [m for m in OPTIONAL if not _installed(m)]

if missing:
    fail(
        "A required tool is missing.",
        "Not available: " + ", ".join(missing),
        "Send this exact line to the assistant: MISSING_DEP=" + ",".join(missing) + "\n"
        "The package will be rebuilt for this Colab version. Your project is not lost.",
    )
if extra_missing:
    print("Optional feature unavailable: %s — the video renders without it." % ", ".join(extra_missing))

print()
print("Tools ready. Now run STEP 3 (the quick test).")
''',
    '03_smoke.py': r'''# STEP 3 of 5 — Quick test with a few frames.
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
''',
    '04_render.py': r'''# STEP 4 of 5 — Render the whole video. This is the long step.
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
''',
    '05_deliver.py': r'''# STEP 5 of 5 — Find and save the finished video.
# Press play. It prints exactly where the file is and how to download it.
import os, shutil, subprocess, sys
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules
if "ROOT" not in globals():
    print("Run STEP 1 first — it sets up the project folder.")
    raise SystemExit(1)
final = ROOT / OUTPUT
if not final.exists():
    fail(
        "No video found.",
        "Expected %s but it is not there." % final,
        "Run STEP 4 first. If STEP 4 said it finished, send this line to the assistant: NO_OUTPUT",
    )

size_mb = final.stat().st_size / 1e6


def probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size:stream=codec_type,width,height",
             "-of", "default=nw=1", str(path)],
            text=True, capture_output=True,
        ).stdout
        return out
    except Exception:
        return ""


info = probe(final)
duration = ""
for line in info.splitlines():
    if line.startswith("duration="):
        try:
            duration = "%.1f s" % float(line.split("=", 1)[1])
        except ValueError:
            pass

print("=" * 68)
print("  VIDEO READY")
print("=" * 68)
print("File: %s" % final)
print("Size: %.1f MB%s" % (size_mb, ("   Length: " + duration) if duration else ""))

# --- also put a copy in Google Drive when possible ---------------------
copied = None
if IN_COLAB:
    try:
        from google.colab import drive
        if not Path("/content/drive/MyDrive").exists():
            print()
            print("A Google sign-in window will appear. Allow it to save a copy to your Drive.")
            drive.mount("/content/drive")
        if Path("/content/drive/MyDrive").exists():
            dest = Path("/content/drive/MyDrive") / final.name
            shutil.copy2(final, dest)
            copied = dest
    except Exception as exc:
        print("(A copy could not be saved to Drive: %s)" % exc)

if copied:
    print()
    print("A copy is also in your Google Drive: %s" % copied)
    print("Open drive.google.com, find that file, right-click it, choose Download.")

print()
print("-" * 68)
print("HOW TO DOWNLOAD")
print("-" * 68)
print("Option 1 (works best for big files):")
print("  Left sidebar -> folder icon (Files) -> open folder %s" % ROOT.name)
print("  -> open folder %s -> right-click %s -> Download"
      % (Path(OUTPUT).parent.name, Path(OUTPUT).name))
print()
print("Option 2: use the Google Drive copy printed above.")
print()
print("Do not use the old 'files.download' button: on big videos it can hang forever.")
print()
print("Keep this session open until the download has finished.")
''',
}
# --- END EMBEDDED CELLS

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
