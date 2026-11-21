# Porting a renderer to the Colab contract

A renderer that runs on a laptop usually hardcodes paths, assumes a working directory, renders the whole timeline in one call, and treats expensive optional features as mandatory. Four changes make it portable.

## 1. CLI and root

```python
ROOT   = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
OUT_DIR = ROOT / "out"

ap.add_argument("--start", type=int, default=0)
ap.add_argument("--end",   type=int, default=None)
ap.add_argument("--out",   default=None)
```

Every asset resolves under `ASSETS`. Nothing reads a drive letter, `~`, or the process CWD. Output directories are created on demand.

## 2. One frame range = one complete file

This is the whole trick behind resumable chunking. A chunk must stand alone: same size, same frame rate, same codec, same audio layout, so `ffmpeg -f concat -c copy` can join them without re-encoding.

```
ffmpeg -y -f rawvideo -pix_fmt bgr24 -s 1920x1080 -r 29.97 -i - \
       -i chunk_audio.wav -map 0:v -map 1:a \
       -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p \
       -c:a aac -b:a 160k -ar 48000 -ac 2 \
       -t <chunk_seconds> -movflags +faststart out/chunk.mp4
```

`-t` is not optional. Without it the last chunk inherits the tail of the audio stream and every concat is a few frames long.

## 3. Audio sliced per chunk

Speech is trimmed with `atrim`, SFX are re-timed relative to the chunk, and the mix stays identical in shape to the full-timeline mix:

```
[0:a]atrim=start=S:end=E,asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:channel_layouts=stereo[base];
[1:a]volume=0.17,atrim=0:D,asetpts=PTS-STARTPTS,adelay=MS|MS[s1];
[base][s1]amix=inputs=2:normalize=0:dropout_transition=0[aout]
```

Drop any SFX whose absolute time falls outside `[S, E)`. Encoding every chunk as PCM-then-AAC at the same rate and channel count is what keeps the join seamless; a mono chunk after a stereo one will desync or fail to copy.

## 4. Optional dependencies degrade

```python
try:
    import mediapipe  # heavy, API drift, sometimes no wheel
    HAVE_MATTE = True
except Exception:
    HAVE_MATTE = False
    print("WARNING: depth matte unavailable; the big word renders unmasked.", flush=True)
```

The render must still finish. Declare these in `optional_imports` so STEP 2 warns instead of stopping.

## 5. Progress with an ETA

```python
if done % 100 == 0 and done:
    el = time.time() - t0
    print("frame %d/%d (%.0f%%)  eta %.0fm" % (done, n, 100.0 * done / n, (el / done * n - el) / 60), flush=True)
```

`flush=True` matters: Colab buffers stdout per cell, so an unflushed log looks like a frozen notebook and the user closes the tab.

## Worked example

A 2128-frame 16:9 kinetic-caption renderer was ported this way: its local-only script had hardcoded Windows paths, a full-timeline audio mix, and a mandatory MediaPipe matte. The port added `assets/` (source, word timings, font, matte model, two SFX), replaced the mix with `build_audio(start, end)`, added `render(start, end, out)`, and made `Matte` return a zero mask when the library is absent. Seven files, `renderlab.json`, 23 MB zip.

The kit built from it passed `renderlab_selftest.py`: 48 frames in two 24-frame chunks, joined, audio intact, 1.62 s against an expected 1.60 s. On the machine that built it, 1080p30 with per-frame Pillow compositing runs at about 8 frames/second; expect Colab CPU to be in the same range.
