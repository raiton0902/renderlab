#!/usr/bin/env python
"""renderlab_selftest.py - prove a render kit before it is shipped.

    python renderlab_selftest.py --dist <dist-dir> [--base <scratch-dir>] [--frames 48]

It does what Colab does and what a user never should have to do:

1. read the generated notebook and its manifest,
2. rewrite a throwaway copy of the package so it renders only a few frames
   (enough to exercise chunking, concat, audio and the final probe),
3. unpack it into a clean directory,
4. run the notebook's own code cells, headless,
5. check the finished file with ffprobe.

Exit code 0 means the kit works. Nothing should be presented before this passes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

MANIFEST = "renderlab_manifest.json"


def die(msg: str) -> None:
    print("selftest: FAIL - " + msg, file=sys.stderr)
    raise SystemExit(1)


def retarget(zip_in: Path, zip_out: Path, total: int, chunk: int) -> dict:
    with zipfile.ZipFile(zip_in) as z:
        names = z.namelist()
        if MANIFEST not in names:
            die("package has no %s" % MANIFEST)
        m = json.loads(z.read(MANIFEST).decode("utf-8"))
        m["total_frames"] = total
        m["chunk_frames"] = chunk
        m["smoke_frames"] = min(int(m.get("smoke_frames") or 24), max(1, total // 2))
        with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as out:
            for name in names:
                data = z.read(name)
                if name == MANIFEST:
                    data = json.dumps(m, indent=2, ensure_ascii=False).encode("utf-8")
                out.writestr(name, data)
    return m


def probe(path: Path) -> tuple[float, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
         "-of", "json", str(path)],
        text=True, capture_output=True,
    )
    if out.returncode != 0:
        die("ffprobe cannot read %s\n%s" % (path, out.stderr.strip()))
    fmt = json.loads(out.stdout or "{}").get("format", {})
    return float(fmt.get("duration") or 0), int(fmt.get("size") or 0)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Run a render kit the way Colab would.")
    ap.add_argument("--dist", required=True)
    ap.add_argument("--base", default=None, help="scratch folder (default: a temp dir)")
    ap.add_argument("--frames", type=int, default=48, help="frames to render in the test")
    ap.add_argument("--chunk", type=int, default=24, help="frames per chunk in the test")
    ap.add_argument("--keep", action="store_true", help="keep the scratch folder")
    args = ap.parse_args(argv)

    dist = Path(args.dist).resolve()
    if not dist.is_dir():
        die("dist folder not found: %s" % dist)

    zips = sorted(dist.glob("Renderlab_*_package.zip"))
    nbs = sorted(dist.glob("Renderlab_*.ipynb"))
    if len(zips) != 1 or len(nbs) != 1:
        die("expected exactly one notebook and one package in %s, found %d and %d"
            % (dist, len(nbs), len(zips)))
    zip_path, nb_path = zips[0], nbs[0]

    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    cells = [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]
    if len(cells) != 5:
        die("notebook must have 5 code cells, found %d" % len(cells))
    for cell in cells:
        text = "".join(cell["source"])
        if "{{" in text:
            die("cell %s still contains a template token" % cell.get("id"))

    base = Path(args.base).resolve() if args.base else Path(tempfile.mkdtemp(prefix="renderlab_"))
    if args.base:
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True)

    test_zip = base / zip_path.name
    m = retarget(zip_path, test_zip, args.frames, args.chunk)
    print("selftest: notebook %s" % nb_path.name)
    print("selftest: package  %s (%.1f MB)" % (zip_path.name, zip_path.stat().st_size / 1e6))
    print("selftest: running %d frames in chunks of %d from a clean extraction"
          % (args.frames, args.chunk))

    os.environ["RENDERLAB_BASE"] = str(base)
    os.environ["RENDERLAB_ZIP"] = str(test_zip)
    os.environ["RENDERLAB_SKIP_INSTALL"] = "1"

    ns: dict = {"__name__": "__renderlab__", "__builtins__": __builtins__}
    started = time.time()
    for cell in cells:
        cid = cell.get("id", "?")
        src = "".join(cell["source"])
        print("\n--- cell %s ---" % cid)
        try:
            exec(compile(src, "<%s>" % cid, "exec"), ns)
        except SystemExit as exc:
            if exc.code in (0, None):
                continue
            die("cell %s stopped the render (see the PROBLEM box above)" % cid)
        except Exception as exc:  # noqa: BLE001 - report, do not hide
            import traceback
            traceback.print_exc()
            die("cell %s raised %s: %s" % (cid, type(exc).__name__, exc))
    elapsed = time.time() - started

    root = base / m["name"]
    final = root / m["output"]
    if not final.exists():
        die("no output file at %s" % final)

    duration, size = probe(final)
    expected = args.frames / float(m.get("fps") or 30)
    if duration <= 0:
        die("the output file has no duration - it is empty or broken")
    if abs(duration - expected) > max(1.0, expected * 0.15):
        die("duration %.2fs does not match %d frames at %.2f fps (expected about %.2fs)"
            % (duration, args.frames, float(m.get("fps") or 30), expected))
    if size < 20000:
        die("output is only %d bytes" % size)

    chunks = sorted(root.glob("out/chunk_*.mp4"))
    outdir = (root / "out").resolve()
    print()
    print("selftest: PASS")
    print("  cells run : 5")
    print("  wall time : %.1f s" % elapsed)
    print("  output    : %s" % final)
    print("  duration  : %.2f s (expected %.2f)" % (duration, expected))
    print("  size      : %.1f MB" % (size / 1e6))
    print("  chunks    : %d kept in %s" % (len(chunks), outdir))
    print("selftest: the notebook, package, chunking, concat and delivery path all work.")

    if not args.keep and not args.base:
        shutil.rmtree(base, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
