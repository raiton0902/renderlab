#!/usr/bin/env python
"""Build the Agensi upload ZIP and validate it against the marketplace rules.

    python tools/package_agensi.py [--out dist]

Rules encoded here (agensi.io/docs/packaging):
  * one ZIP, SKILL.md at the root with name + description frontmatter
  * text/code only: no executables, no bundled dependencies
  * 50 MB / 1,000 files on website upload
  * every script must run alone from a temporary file
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CELLS = ["00_intro.md", "01_unpack.py", "02_install.py",
         "03_smoke.py", "04_render.py", "05_deliver.py"]

# Shipped to buyers: the skill and everything it needs at runtime.
INCLUDE = [
    "SKILL.md",
    "README.md",
    "LICENSE",
    "scripts/renderlab_pack.py",
    "scripts/renderlab_selftest.py",
    "assets/renderlab.json.example",
    "references/colab-reality.md",
    "references/porting-renderer.md",
    "references/colab-agent-access.md",
] + ["assets/cells/" + c for c in CELLS]

BAD_EXT = {".exe", ".dll", ".so", ".dylib", ".bin", ".app", ".dmg", ".msi",
           ".deb", ".rpm", ".wasm", ".class", ".jar", ".war"}
BAD_DIRS = {"node_modules", "site-packages", "__pycache__", ".venv", "venv", ".git"}
ZIP_DATE = (2026, 1, 1, 0, 0, 0)


def die(msg: str) -> None:
    print("package_agensi: FAIL - " + msg, file=sys.stderr)
    raise SystemExit(1)


def frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        die("SKILL.md does not start with frontmatter")
    body = text[4:]
    end = body.find("\n---")
    if end < 0:
        die("SKILL.md frontmatter is not closed")
    block = body[:end]
    fields = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if m and m.group(2).strip():
            fields[m.group(1)] = m.group(2).strip()
    return fields


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args(argv)

    missing = [rel for rel in INCLUDE if not (ROOT / rel).is_file()]
    if missing:
        die("missing files:\n  " + "\n  ".join(missing))

    meta = frontmatter((ROOT / "SKILL.md").read_text(encoding="utf-8"))
    if "name" not in meta or "description" not in meta:
        die("SKILL.md needs name and description frontmatter")
    if meta["name"] != "renderlab":
        die("frontmatter name is %r, expected renderlab" % meta["name"])

    outdir = (ROOT / args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    zip_path = outdir / ("renderlab-agensi-v%s.zip" % args.version)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in INCLUDE:
            data = (ROOT / rel).read_bytes()
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                die("%s is not UTF-8 text; Agensi delivers text only" % rel)
            info = zipfile.ZipInfo(rel, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)

    # --- validate the artefact we are about to upload -------------------
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if z.testzip():
            die("zip is corrupt")
        roots = [n for n in names if n == "SKILL.md"]
        if roots != ["SKILL.md"]:
            die("SKILL.md must sit at the ZIP root, found %r" % roots)
        if len(names) > 1000:
            die("%d files, limit is 1000" % len(names))
        for name in names:
            parts = Path(name).parts
            if any(p in BAD_DIRS for p in parts):
                die("forbidden path in package: %s" % name)
            if Path(name).suffix.lower() in BAD_EXT:
                die("executable file in package: %s" % name)
            try:
                z.read(name).decode("utf-8")
            except UnicodeDecodeError:
                die("non-text file in package: %s" % name)
        size = zip_path.stat().st_size
        if size > 50 * 1024 * 1024:
            die("%.1f MB, website upload limit is 50 MB" % (size / 1e6))

    print("package_agensi: built %s" % zip_path)
    print("  files   : %d (%.0f KB zipped, %.0f KB raw)"
          % (len(names), size / 1024, sum((ROOT / r).stat().st_size for r in INCLUDE) / 1024))
    print("  skill   : %s v%s" % (meta["name"], meta.get("version", "?")))
    tops = sorted({Path(n).parts[0] + ("/" if len(Path(n).parts) > 1 else "") for n in names})
    print("  entries : " + ", ".join(tops))
    print("  checks  : root SKILL.md, text-only, no executables, under 50 MB")
    print("  next    : upload at https://agensi.io/creator (Creator Studio -> Submit a Skill)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

