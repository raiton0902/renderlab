# STEP 1 of 5 — Unpack the package.
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
