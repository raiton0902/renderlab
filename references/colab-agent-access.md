# Reaching Colab without a human (optional paths)

The default Renderlab kit assumes a person presses play in a browser. That is still the right deliverable when the end user is a non-coder. But Google now exposes Colab to agents directly, and in three situations that is the better path.

Verified 2026-11-26 against Google's docs. Treat versions and flags as moving targets; re-check before promising anything.

## The three routes

| Route | Who drives | OS | Best for |
|---|---|---|---|
| Notebook in the browser | the end user | anything | non-technical user, one-off render, zero setup |
| Colab CLI | the agent (terminal) | **Linux / macOS only** | agent-rendered kits, no tab to close, artifacts pulled back |
| Colab MCP endpoint | the agent (MCP client) | anything, HTTP | Windows agents, long jobs with reattach |

## Colab CLI

Install (needs Python; `uv` preferred):

```bash
uv tool install google-colab-cli      # or: pip install google-colab-cli
```

Windows is **not supported** — if the agent runs on Windows, use the MCP endpoint or hand the kit to a person.

Minimum headless render of a kit:

```bash
colab new -s render --high-mem        # --high-mem needs Pro/Pro+ entitlement
colab upload -s render Renderlab_x_package.zip /content/Renderlab_x_package.zip
RENDERLAB_ZIP=/content/Renderlab_x_package.zip colab exec -s render -f Renderlab_x.ipynb
colab download -s render /content/<name>/out/final.mp4 ./final.mp4
colab stop -s render
```

Why this beats the browser for a long render: the session stays alive while the kernel is active, so closing a laptop lid does not kill a 20-minute encode. `colab run script.py` goes further — fresh VM, run, tear down in one command.

Useful commands: `new`, `sessions`, `status`, `exec [-f FILE]`, `run`, `upload`, `download`, `ls`, `log [-o FILE]`, `install`, `drivemount`, `stop`, `usage`.
`colab exec -f notebook.ipynb` runs every code cell and writes `<basename>_output.ipynb` next to the input.

## Hosted MCP endpoint

Global endpoint: `https://colaboratory.googleapis.com/mcp` (Colab API). Requires enabling MCP servers and Google OAuth setup first.

Tools: `create_runtime`, `create_session`, `execute_code`, `get_runtime`, `list_runtimes`, `list_runtime_specs`, `delete_session`, `delete_runtime`, `list_sessions`, `get_subscription`.

Rules that shape a driver:

- `execute_code` is cut off at **600 s per call** with `DEADLINE_EXCEEDED`, but the code keeps running. Retry the **identical** call with the same `session` and `executionId` to reattach and collect output. A new `executionId` runs the code again.
- Pass exactly one of `session` or `runtime`. Use `session` for stateful multi-step work; `runtime` opens a session you must reuse or close.
- Output is **text only** — no images, plots or binary. Long output is truncated and flagged `outputTruncated`.
- Files move over HTTP, not through the tool: `GET {connectionInfo.url}/files/{path}` downloads, `PUT {connectionInfo.url}/api/contents/{path}` uploads (JSON, `base64` or `text`, under 50 MB per request, `chunk` 1..n, `-1` on the last piece) with header `X-Colab-Runtime-Proxy-Token: {connectionInfo.token}`. Paths are absolute without the leading slash.
- `get_runtime` tokens expire after about an hour — call it again.
- Free tier works but is quota-limited: `FAILED_PRECONDITION` on `create_runtime` usually means quota, capacity or too many active runtimes; `RESOURCE_EXHAUSTED` is a rate limit, retry with backoff.

Reasonable agent flow: `list_runtimes` (reuse), else `create_runtime` with an eligible spec from `list_runtime_specs` → `create_session` → upload the kit zip via the runtime HTTP proxy → `execute_code` the notebook's cells, splitting each long cell into its own call so nothing approaches 600 s → download `out/final.mp4` → `delete_session`.

## Local MCP server (browser-driven)

`uvx git+https://github.com/googlecolab/colab-mcp` exposes a stdio MCP server that drives a notebook the user already has open in Colab: add cells, run them, inspect state. Use this when the user wants to watch and take over, not for unattended rendering.

## What this does NOT change

- The kit is still the deliverable. A notebook plus a manifest is the artifact that survives agent changes, OS changes and a user who never installs anything.
- Keep the 24-frame smoke gate. A headless path that skips it turns a 30-second check into a 20-minute failure.
- Chunking still matters: `execute_code` has a 600 s ceiling and a CLI session can still hit quota limits.
- Never let a driver rely on `files.download()`. Use the HTTP proxy or the CLI's `download`.
