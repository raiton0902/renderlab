# Renderlab

Turn a local video edit or animation render into a **Google Colab kit** — a notebook, a package, and a plain-language guide — and prove the kit works before handing it over.

Renderlab is a skill for coding agents — **any** coding agent. DeepSeek Harness, Claude Code, Codex, Gemini CLI, Cursor, Copilot, or a script of your own: if the agent can read a `SKILL.md`, it can run this. The contract is one text file, and the tooling is two Python scripts with no dependencies. It exists because rendering 1080p on a laptop eventually fails:

```
OSError: [WinError 1455] The paging file is too small for this operation to complete
```

…and the free Colab tier is a better machine than the laptop, if the project can survive the move.

The user who receives a kit is assumed to have **no coding experience**, **no Python knowledge**, and **no patience for configuration**. They get three files and five play buttons.

## What a kit is

```
Renderlab_<name>.ipynb          the notebook: five cells, nothing to edit
Renderlab_<name>_package.zip    renderer + every asset it touches
RENDER_IN_COLAB.md              the same steps as prose
```

The notebook flow:

| Cell | What it does |
|---|---|
| STEP 1 | Ask for the zip, wipe old state, unpack, verify every file against the manifest, print expected runtime |
| STEP 2 | `pip install` declared dependencies, verify imports, warn on optional ones |
| STEP 3 | Render **24 frames only** — a smoke test that proves decode, compositing, encode and audio all work |
| STEP 4 | Render the timeline in resumable chunks, print percent and ETA, join with `-c copy` |
| STEP 5 | Probe the result, copy to Drive, print the Files-panel path |

The product is **never** a rendered video. It is the kit.

## Install

One command, no clone, installs into `~/.dsh/skills/renderlab`:

```bash
npx github:raiton0902/renderlab
```

Other agents and locations:

```bash
npx github:raiton0902/renderlab --claude      # ~/.claude/skills/renderlab
npx github:raiton0902/renderlab --dir ~/skills/renderlab
npx github:raiton0902/renderlab --force       # replace an existing install
```

No Node? The shell installers do exactly the same:

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/raiton0902/renderlab/main/install.sh | bash
```

```powershell
# Windows
irm https://raw.githubusercontent.com/raiton0902/renderlab/main/install.ps1 | iex
```

Or the boring way:

```bash
git clone https://github.com/raiton0902/renderlab.git ~/.dsh/skills/renderlab
```

Restart your agent afterwards so it reloads the skills folder, then ask *"edit this video and render it using /Renderlab"*.

### Works with every agent

Nothing here is specific to one host. The skill is `SKILL.md` plus plain files; the installer only decides **which folder** to copy into.

| Agent | Command | Lands in |
|---|---|---|
| DeepSeek Harness | `npx github:raiton0902/renderlab` | `~/.dsh/skills/renderlab` |
| Claude Code | `npx github:raiton0902/renderlab --claude` | `~/.claude/skills/renderlab` |
| Gemini CLI, Codex, Cursor, Copilot, other | `npx github:raiton0902/renderlab --dir <path>` | whatever folder that agent reads |
| No Node at all | `install.sh` (macOS/Linux) or `install.ps1` (Windows) | same paths, same result |

If your agent has no skills folder, copy the directory anywhere and point the agent at it — e.g. add one line to your `AGENTS.md`:

```md
- Renderlab: build verified Google Colab render kits. Read `skills/renderlab/SKILL.md` before rendering.
```

The packer and selftest are pure Python 3.8+ standard library, so they run under any agent's shell, in CI, or by hand. No API key, no service, no runtime.

`npx github:` runs this repo's installer directly, so nothing has to be published first. If the package is published to npm later, `npx renderlab` is the same command.

## Quickstart (for the person rendering)

1. Open <https://colab.research.google.com>, sign in with any Google account.
2. `File` → `Upload notebook` → pick `Renderlab_<name>.ipynb`.
3. Press play on STEP 1, choose the zip in the file picker.
4. Press play on STEP 2 → 3 → 4 → 5, in order. Keep the tab open.
5. STEP 5 prints where the video is. Download it from the Files panel or from Drive.

A failure never shows a traceback. It prints:

```
PROBLEM: <what broke>
WHAT TO DO: <one action, in plain words>
```

## Quickstart (for an agent using the skill)

Copy this folder to your skills directory, e.g. `~/.dsh/skills/renderlab/`, then follow `SKILL.md`.

```bash
# 1. make the renderer portable (contract: --start --end --out, root-relative paths)
# 2. write renderlab.json next to it
python skills/renderlab/scripts/renderlab_pack.py --project ./my-render --dist ./dist
python skills/renderlab/scripts/renderlab_selftest.py --dist ./dist
```

`renderlab_selftest.py` unpacks the package into a clean directory, executes the generated notebook's own code cells headlessly, renders a few frames in several chunks, joins them, and checks the file with `ffprobe`. **Nothing is presented before it passes.**

## The renderer contract

```bash
python render.py --start 0 --end 700 --out out/chunk_0001.mp4
```

- `--start` / `--end` are half-open frame indices.
- Every invocation produces a **complete, independent file**: same codec, frame rate, and audio layout, so chunks concatenate without re-encoding.
- All assets resolve from `Path(__file__).resolve().parent`. No drive letters, no `/content` literals.
- Optional heavyweight features (depth mattes, GPU encoders) degrade with one warning line instead of failing the render.

`references/porting-renderer.md` has the exact recipes, including the `atrim`/`adelay` audio slice that keeps a joined chunk's audio in sync.

## Manifest

`renderlab.json` lists everything explicitly — no globs:

```json
{
  "name": "laura13",
  "title": "Laura 13 - kinetic captions",
  "entry": "render.py",
  "output": "out/final.mp4",
  "total_frames": 2128,
  "fps": 29.97,
  "smoke_frames": 24,
  "chunk_frames": 700,
  "deps": ["numpy", "opencv-python-headless", "pillow"],
  "imports": ["numpy", "cv2", "PIL"],
  "optional_imports": ["mediapipe"],
  "files": ["render.py", "assets/source.mp4", "assets/words.json", "assets/font.ttf"],
  "est_minutes": 14,
  "notes": "1920x1080. Audio is mixed into every chunk, so parts join cleanly."
}
```

The packer stats every entry and refuses to build if one is missing. A glob that quietly matches nothing is how a package once shipped without its footage, produced two minutes of blank video, and died in `ffmpeg` with `Impossible to open ... No such file or directory`.

## Verified, not asserted

The reference port — a 2128-frame 16:9 kinetic-caption renderer with a MediaPipe matte, two SFX and a 24 MB source — passed:

- smoke: 24 frames, file present, audio stream present
- selftest: 48 frames as 2×24-frame chunks joined with `-c copy`, **1.62 s against 1.60 s expected**
- negative tests: a missing asset stops at STEP 1, a missing import stops at STEP 2, the packer refuses an incomplete file list and an unpackaged entry

One selftest run hit a genuine `MemoryError` mid-smoke: the kit stopped at STEP 3 with a `PROBLEM:` box and never started the full render. That is the intended behavior.

## Why the rules are shaped this way

`references/colab-reality.md` records the failures that produced them, with the original error text:

- an incomplete zip → 121 seconds of blank video, then a concat crash
- a 404 page that printed `frontend is ONLINE` → the recording drove an error page for 93 s
- a hardcoded `/content/.../intro.mp4` → `Impossible to open`
- a stale process on a strict port → retry could not bind
- `google.colab.files.download()` on a 21 MB MP4 → a 10-minute silent spinner
- Python 3.13 with no cp312 wheel → the install dies
- 1.4 GB of free RAM on the user's laptop → `ffmpeg` cannot even spawn

Short version: **assert content, not liveness; list files explicitly; verify by import, not by version; never call `files.download()`; prove the kit with a 24-frame render before spending 20 minutes.**

## Repository layout

```
SKILL.md                        the skill: phases, contract, hard rules
bin/renderlab.js                installer behind `npx github:raiton0902/renderlab`
install.sh / install.ps1        curl / irm installers, no Node needed
package.json                    publish-ready npm wrapper around the skill
scripts/renderlab_pack.py       validate manifest → zip → notebook → readme
scripts/renderlab_selftest.py   run the generated kit headless
assets/cells/                   the five notebook cells as plain .py / .md
assets/renderlab.json.example   manifest to copy
references/colab-reality.md     failure log, with quoted errors
references/porting-renderer.md  renderer porting recipes
tools/embed_cells.py            regenerate the cell copies embedded in the packer
tools/package_agensi.py         build + validate the marketplace upload ZIP
```

Edit `assets/cells/*` to change the notebook every future kit gets, then repack. The packer refuses unreplaced template tokens.

## Uploading to a marketplace (Agensi)

```bash
python tools/package_agensi.py --out dist
# -> dist/renderlab-agensi-v1.0.0.zip
```

The ZIP puts `SKILL.md` at the root, ships text only, and carries an embedded copy of the notebook cells — marketplace sandboxes run each script alone from a temporary file, where `assets/cells` is not on disk. `python scripts/renderlab_pack.py --selfcheck` verifies that embedded copy still matches the files; `tools/embed_cells.py` regenerates it after an edit.

Verified by extracting the ZIP and running both scripts the way the sandbox would: the packer alone in an empty directory builds a kit, and the selftest passes (1.62 s against 1.60 s expected).

Listing fields come from the `SKILL.md` frontmatter: `name`, `description`, `summary`, `version`, `tags`, `keywords`, `use_cases`, `docs_url`.

## Free-tier limits the kit tells users about

- ~12 GB RAM, shared CPU
- the browser tab must stay open — closing it ends the session and deletes its files
- roughly 12 hours per session, sooner if idle
- a finished render exists only in that session until it is downloaded or copied to Drive

## License

MIT — see [LICENSE](LICENSE).
