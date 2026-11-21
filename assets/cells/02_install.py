# STEP 2 of 5 — Install the tools this render needs.
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
