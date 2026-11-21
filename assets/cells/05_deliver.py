# STEP 5 of 5 — Find and save the finished video.
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
