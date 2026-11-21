---
name: renderlab
description: Turn a local video edit or animation project into a self-contained Google Colab render kit — a ready-to-run .ipynb notebook plus a package .zip plus plain-language steps — and prove the kit works before shipping it. Use when the user says "render it in Colab", "/Renderlab", "render on Google Colab", "I only have Colab", "my laptop can't render this", or hands over a renderer and wants a notebook they can run without touching Python. Covers free-plan limits, dependency failures, disconnects, and file download.
---

# Renderlab

Renderlab moves a render off the user's machine and onto Google Colab **without the user ever seeing or editing code**. The deliverable is never the finished video. It is a kit:

1. `Renderlab_<name>.ipynb` — the notebook. Upload it, press play on five cells, get the video.
2. `Renderlab_<name>_package.zip` — renderer + every asset it touches.
3. `RENDER_IN_COLAB.md` — the same steps as prose, for people who lose the chat.

The user is assumed to be on the **free Colab tier**, with **zero configuration appetite**, and **no coding or Python experience**. Treat every number of clicks and every error message as a design constraint.

This skill is **host-agnostic**. It is one `SKILL.md` plus two Python 3.8+ standard-library scripts, so DeepSeek Harness, Claude Code, Codex, Gemini CLI, Cursor or a custom agent can all run it; only the folder it lives in changes. Do not assume a specific harness's extra tools — a shell, file access, and the ability to run Python are enough.

## The one rule that matters

**A kit that has not been run inside a clean extraction is not finished.** The failure this skill exists to prevent: a package missing two files shipped anyway, produced 121 seconds of blank video, then died in `ffmpeg` with `Impossible to open ... no such file or directory`. The user saw a 60-line traceback for a missing PNG.

So: build the zip, extract it to an empty directory, run the notebook's own cells against that extraction, and look at the output file before presenting anything. `scripts/renderlab_selftest.py` does exactly this. Run it. No exceptions.

## Phase 0 — Scope the job

Ask nothing you can read from the project. Confirm only:

- **Source assets exist and are final.** A missing B-roll is not a Colab problem; it is a render problem, and Colab will just fail later and more expensively.
- **The long pole.** Estimate render minutes per project: frames × per-frame cost. If the total is over ~40 minutes on Colab CPU, plan chunking and tell the user the honest number.

Do not ask the user about Python versions, pip, Drive, or runtime types. Those are your problem, not theirs.

## Phase 1 — Make the renderer portable

Colab is Linux with `/content` as the workspace. A renderer that hardcodes `D:\...` is dead on arrival. Enforce this contract:

**Entry point.** One script, declared in the manifest, callable as:

```
python <entry> --start <frame> --end <frame> --out <path>
```

- `--start`/`--end` are frame indices, half-open. Output covers exactly that range.
- Every invocation must be **independently valid**: audio mixed for that range, identical encoder settings, same frame rate. That is what makes chunk concat with `-c copy` safe.
- Exit code 0 means the file exists and is complete. Any other code means human-readable failure.

**Paths.** Everything resolves from `Path(__file__).resolve().parent`. Assets live under `assets/`. Outputs under `out/`. No absolute paths, no drive letters, no `..`, no environment assumptions.

`references/porting-renderer.md` has the exact recipes: the CLI shape, the chunk-safe encoder settings, the `atrim`/`adelay` audio slice that keeps concat seamless, and the optional-dependency guard.

**Optional features degrade, never crash.** A depth matte, a GPU encoder, a heavyweight model: wrap it, and on failure fall back to the plain version and print one warning line. MediaPipe is the canonical example — its API has broken across major versions, and a missing silhouette should cost the user a shadow, not the whole render.

**Fail fast, fail in English.** Preflight every input at startup and print, for example:

```
PROBLEM: assets/narration.wav is missing from the package.
WHAT TO DO: this is a packaging bug, not your fault. Send this text to the assistant.
```

Never let a non-coder interpret a traceback.

**Progress.** Print `frame 600/2128 (28%)  eta 6m 12s` every ~100 frames, flushed. Silence reads as a hang; a hang is what makes people close the tab, and closing the tab kills a free runtime.

## Phase 2 — Write the manifest

`renderlab.json` sits at the package root:

```json
{
  "name": "laura13",
  "title": "Laura 13 — kinetic captions",
  "entry": "render.py",
  "output": "out/final.mp4",
  "total_frames": 2128,
  "fps": 29.97,
  "smoke_frames": 24,
  "chunk_frames": 600,
  "deps": ["numpy", "opencv-python-headless", "pillow"],
  "imports": ["numpy", "cv2", "PIL"],
  "optional_imports": ["mediapipe"],
  "files": ["render.py", "assets/source.mp4", "assets/words.json", "assets/font.ttf"],
  "est_minutes": 15,
  "notes": "Renders at 1920x1080. Audio is mixed into every chunk."
}
```

- `files` is an **explicit list**. No globs. A glob that quietly matches nothing is how the broken package shipped. The packer stats every entry and refuses to build if one is missing.
- `imports` are verified after install. `optional_imports` only warn.
- `smoke_frames` stays small enough that the smoke test finishes under a minute; 24 frames is the floor that proves decode, compositing, encode, and audio mux all work.
- `chunk_frames` exists so a disconnect costs one chunk, not the whole render. `600` is a sane default for 1080p30; fewer if a chunk takes over ~10 minutes.

## Phase 3 — Pack

```bash
python <skill>/scripts/renderlab_pack.py --project <staging-dir> --dist <out-dir>
```

Emits the three deliverables and validates: manifest schema, every file present, entry present, output path sane, zip readable, file count matches. It refuses ambiguous input rather than guessing.

## Phase 4 — Prove it

```bash
python <skill>/scripts/renderlab_selftest.py --dist <out-dir> --base <scratch-dir>
```

It unpacks the zip into `<scratch-dir>` exactly as Colab would, executes the generated notebook's own code cells headlessly, and checks the final file with `ffprobe`. Locally installed dependencies are reused (`RENDERLAB_SKIP_INSTALL=1`), so no network is needed.

A pass means: extraction works, validation passes, smoke completes, chunks concat, audio survives, output plays. **Present nothing before this passes.** If it fails, fix the project — never ship with a note saying "should work".

## Phase 5 — Deliver

Present the three files with `present`. Then, in the user's language and without jargon:

1. Open <colab.research.google.com>, `File → Upload notebook`, choose the `.ipynb`.
2. Press play on STEP 1, choose the `.zip` when the file picker appears.
3. Press play on STEP 2, 3, 4, 5 in order. About N minutes total.
4. STEP 5 prints where the video is. `Files` panel on the left → right-click → `Download`, or take it from Drive.

Include the honest limits: free tier gives roughly 12 GB RAM and a 12-hour ceiling with a roughly 90-minute idle timeout; keep the tab open; a disconnect means re-running steps, which chunking softens but does not erase.

## Notebook anatomy (fixed)

Five code cells, in this order. The generator bakes every project value in; the user edits nothing.

| Cell | Job |
|---|---|
| STEP 1 | Find/upload the zip, wipe the old extraction, unpack, verify every manifest file, print sizes and expected runtime. |
| STEP 2 | `pip install` the declared deps, then verify imports. Missing required import → plain-English stop with one pasteable line. |
| STEP 3 | Render `smoke_frames` only. Check the file exists and is not truncated. Print **SMOKE TEST PASSED** or stop with the last lines of output. |
| STEP 4 | Render every chunk, skipping chunks already on disk, printing percent and ETA, then concat with `-c copy` into the final file. |
| STEP 5 | Probe duration and size, copy to Drive if mounted, otherwise print the Files-panel path. Never call `files.download()`. |

Cell 1 defines `fail(title, detail, action)`; every later failure goes through it. Every cell starts with one plain sentence describing what it does.

## Hard rules

1. **Never return a rendered video as the answer** unless the user explicitly asks for one. The product is the kit.
2. **Never use `google.colab.files.download()`.** It streams through a browser comm channel and hangs silently on files over a few MB — observed at 10+ minutes on a 21 MB MP4 while the render was already complete. Use the Files panel or Drive.
3. **Never trust a health check that only checks liveness.** A 404 page answers HTTP 200. If the kit serves something, assert content, not reachability.
4. **Kill stale state on rerun.** Same-session retries collide with leftover processes and half-written temp files. Wipe the extraction directory at STEP 1 and use chunk files as the skip signal.
5. **Pin nothing you cannot verify.** Prefer unpinned installs plus an import check over a pin that silently has no wheel for the current Python. Colab's interpreter moves; wheels lag. Handle the failure, do not celebrate the pin.
6. **One process, absolute paths.** Use `sys.executable` and absolute paths. `!python` and `cd` in shell cells are how the wrong interpreter or the wrong working directory gets used.
7. **Size the package for upload.** Under ~100 MB uploads fine in the file picker. Beyond that, tell the user to put the zip in Drive and name the exact folder; never make a non-coder discover that a 2 GB upload times out.
8. **Write outputs where STEP 5 looks.** A render written to the kernel's CWD is a render the user cannot find.

## Failure reflection

`references/colab-reality.md` records the concrete failures that produced these rules, with the exact error text. Read it before designing a kit for an unfamiliar project; it is the difference between a first-try render and three rounds of tracebacks.

The short version:

- Missing files in the zip → blank video and a concat crash. Explicit file list, preflight, smoke test.
- "Frontend is ONLINE" from a 404 → Playwright recorded nothing. Assert content.
- Hardcoded `/content/.../intro.mp4` → `Impossible to open`. Resolve paths from the project root.
- Stale Vite on a strict port → retry fails. Kill and wipe.
- `files.download()` on 21 MB → infinite spinner. Drive or Files panel.
- Python 3.13, no cp312 wheel → install dies. Check imports, offer a graceful path.
- 1.4 GB free RAM on the user's laptop → even `ffmpeg` cannot spawn. Colab is the fix, and it is why this skill exists.

## What ships in this skill

```
SKILL.md                      this file
scripts/renderlab_pack.py     validate manifest, zip, generate notebook + readme
scripts/renderlab_selftest.py run the generated kit headless, the way Colab would
assets/cells/                 the five notebook cells, as plain .py/.md (editable)
assets/renderlab.json.example manifest to copy for a new project
references/colab-reality.md   the failure log behind every rule
references/porting-renderer.md  CLI, chunk-safe encode, per-chunk audio, graceful fallback
```

Edit `assets/cells/*` to change the notebook for every future kit. Re-run the packer afterwards; it refuses unreplaced tokens.

## Worked example

A 2128-frame 16:9 kinetic-caption renderer (per-frame Pillow compositing, MediaPipe depth matte, two SFX, 24 MB HiDPI source) was ported to the contract described above. Its kit verified clean:

- smoke: 24 frames, file present, audio stream present
- selftest: 48 frames as two 24-frame chunks, joined by `-c copy`, 1.62 s against 1.60 s expected
- negative tests: missing asset stops at STEP 1, missing import stops at STEP 2, packer refuses an incomplete file list

The project itself is not redistributed here — its footage is third-party. What transfers is the structure: `render.py`, `assets/`, `renderlab.json`. Keep it when starting a new render and replace the contents.
