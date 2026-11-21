# Colab reality — failures that shaped this skill

Every item below happened on a real free-tier Colab render. The rule each one produced is in `SKILL.md`; this file keeps the evidence so the next kit does not relearn it.

## 1. The incomplete package: 121 seconds of blank video, then a concat crash

The zip held 58 entries: `package.json`, `tsconfig.json`, `src/**`, `video/scripts/**`. Missing: `index.html`, `vite.config.ts`, `public/`, `video/scene1-tontine-intro.mp4`, the voiceover MP3.

Two independent failures came from the same omission:

```
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x5acc8b855f80] Auto-inserting h264_mp4toannexb bitstream filter
[concat @ 0x5b13e1f98d40] Impossible to open '/content/tontinesats/video/scene1-tontine-intro.mp4'
Error opening input file /content/tontinesats/video/tmp/concat.txt.
```

and, earlier, every Playwright selector missing because Vite had nothing to serve at `/`:

```
Warning: element not found: (() => { const b = document.querySelector('button[aria-label="English"]'); ...
```

The pipeline recorded 93.75 s and 27.10 s of a 404 page without complaint.

**Rules:** `files` is an explicit list, packed and stat-checked. STEP 1 verifies the manifest after extraction. STEP 3 renders 24 frames so a broken package fails in 30 seconds, not 20 minutes.

## 2. The health check that only checked liveness

`run_pipeline.py` treated *any* HTTP response as proof the frontend was up, so a 404 printed:

```
Vite frontend is ONLINE on port 5175!
```

**Rule:** assert content, not reachability. If the kit starts a server, request `/` and look for a marker. `ONLINE` must mean usable.

## 3. Hardcoded `/content/...` segment paths

`compose_final.py` named three segments by absolute path, including a file the package never shipped. Resolve everything from the project root; keep the segment list in the manifest, not in three string literals.

## 4. Stale processes on same-session retry

`vite --strictPort` plus a left-over backend meant a retry in the same runtime failed to bind, after a failed first attempt. Restarting the runtime "fixed" it, which teaches the user nothing.

**Rule:** wipe the extraction at STEP 1 and kill anything the kit may have left running before starting. Retry must be a no-op re-entry, not a ritual.

## 5. `files.download()` hangs on a 21 MB MP4

The render finished:

```
SUCCESS! Final demo video created at:
  -> /content/tontinesats/tontinesats-demo.mp4
```

The download cell then spun for 10+ minutes with no error and no progress. `google.colab.files.download()` pushes bytes through a browser comm channel in 1 MiB chunks and rebuilds a Blob; on a big file or a slow channel it stalls silently ([colabtools#3155](https://github.com/googlecolab/colabtools/issues/3155)).

**Rule:** never call it. STEP 5 copies to Drive when available and always prints the Files-panel path (`Files` icon → folder → right-click → `Download`), which is a plain HTTP transfer with progress.

## 6. Python moved, wheels did not

Colab now runs Python 3.13 (`/usr/lib/python3.13/subprocess.py` in the traceback). Many native packages publish cp310–cp312 wheels only, so a pin either has no wheel or is silently ignored. MediaPipe is the sharp edge: `0.10.x` is cp310–cp312, while `1.2.x` ships `py3-none-<platform>` wheels that install anywhere but may have moved the Tasks API.

**Rules:** verify by import, not by version string. Mark heavy/optional libraries `optional_imports` and degrade (no matte, software encoder, smaller effect) instead of failing the render.

## 7. The user's laptop, not Colab, was the bottleneck

Before any of this, the local render died with:

```
OSError: [WinError 1455] The paging file is too small for this operation to complete
```

at 1.4 GB free / 1.0 GB commit — `ffmpeg` could not even spawn, and later `import cv2` failed the same way. A 20-minute 1080p render needs several GB of transient float buffers per frame.

**Rule:** this is the reason the skill exists. Free Colab gives ~12 GB RAM; the kit must also *tell* the user the expected minutes before they start, so a 90-minute idle disconnect does not surprise them.

## 8. Silent long renders look like hangs

Local logs printed every 200 frames, which is the only reason a 2000-frame render was tolerable to watch. A Colab cell that prints nothing for eight minutes gets closed by the user, and closing the tab kills the runtime.

**Rule:** print frame progress, percent, and ETA at least every ~100 frames, unbuffered (`flush=True`), from the renderer *and* per chunk from the notebook.

## Checklist distilled

- [ ] Package built from an explicit file list, every entry stat-checked
- [ ] Paths resolved from the project root; no drive letters, no `/content` literals
- [ ] Entry accepts `--start/--end/--out`; each range is independently valid, audio included
- [ ] Optional libraries wrapped; fallback path prints one warning line
- [ ] Preflight prints `PROBLEM:` / `WHAT TO DO:` in plain language
- [ ] Notebook verifies the extraction against the manifest
- [ ] Imports verified after install; missing optional import only warns
- [ ] 24-frame smoke test gates the full render
- [ ] Chunks are resumable skip-units; concat with `-c copy`
- [ ] Delivery via Drive / Files panel, never `files.download()`
- [ ] Expected minutes printed before the long cell
