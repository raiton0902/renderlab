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
        m = json.loads(path.read_text(encoding="utf-8"))
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
        path = CELLS / filename
        if not path.is_file():
            die("cell template missing: %s" % path)
        text = path.read_text(encoding="utf-8")
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
    text = f"""# {m['title']} — render on Google Colab

You do not need Python, and you do not edit anything. The free Colab plan is enough.

## What you need

Two files, both in the same folder as this text:

- `{nb_name}` — the notebook
- `{zip_name}` — the package (keep the name exactly as it is)

## Steps

1. Open <https://colab.research.google.com> and sign in with any Google account.
2. `File` → `Upload notebook` → choose `{nb_name}`.
3. Press the play button on **STEP 1**. A file picker opens: choose `{zip_name}`.
   Wait for `Package ready`.
4. Press play on **STEP 2**, wait for `Tools ready`.
5. Press play on **STEP 3**. It renders 24 test frames. Wait for `SMOKE TEST PASSED`.
   If this fails, stop and send the printed box to the assistant — nothing is lost.
6. Press play on **STEP 4**. This is the long part. {est_line}
   Keep the tab open. If the cell stops with an error, run STEP 4 again: finished parts are skipped.
   A disconnect ends the session and deletes its files: upload the package again and start at STEP 1.
7. Press play on **STEP 5**. It prints where the video is.

## Getting the file out

- `Files` icon on the left → `{m['name']}` → `{Path(m['output']).parent.as_posix()}` → `{Path(m['output']).name}` → right-click → **Download**
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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build a Colab render kit.")
    ap.add_argument("--project", required=True, help="folder holding renderlab.json")
    ap.add_argument("--dist", required=True, help="output folder")
    args = ap.parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
