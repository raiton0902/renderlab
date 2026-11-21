#!/usr/bin/env bash
# Renderlab installer for macOS / Linux.
#
#   curl -fsSL https://raw.githubusercontent.com/raiton0902/renderlab/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- --claude
#   RENDERLAB_DIR=~/skills/renderlab bash install.sh
set -euo pipefail

REPO="raiton0902/renderlab"
REF="${RENDERLAB_REF:-main}"
NAME="renderlab"
DEST="${RENDERLAB_DIR:-$HOME/.dsh/skills/$NAME}"
FORCE="${RENDERLAB_FORCE:-0}"

while [ $# -gt 0 ]; do
  case "$1" in
    --claude) DEST="$HOME/.claude/skills/$NAME" ;;
    --force) FORCE=1 ;;
    --dir)
      [ -n "${2:-}" ] || { echo "renderlab: --dir needs a path" >&2; exit 2; }
      DEST="$2"; shift ;;
    --dir=*) DEST="${1#--dir=}" ;;
    -h|--help)
      cat <<'EOF'
renderlab - install the Renderlab agent skill

Usage: install.sh [--claude] [--dir PATH] [--force]

  --claude   install into ~/.claude/skills/renderlab
  --dir      install into PATH (default: ~/.dsh/skills/renderlab)
  --force    replace an existing install

Environment: RENDERLAB_DIR, RENDERLAB_FORCE=1, RENDERLAB_REF
EOF
      exit 0 ;;
    *) echo "renderlab: unknown option $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -e "$DEST" ] && [ "$FORCE" != "1" ]; then
  echo "renderlab: already installed at $DEST"
  echo "Use --force to replace it, or --dir to install somewhere else."
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

URL="https://codeload.github.com/$REPO/tar.gz/refs/heads/$REF"
echo "Downloading $REPO ($REF)..."
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$TMP/pkg.tgz"
else
  wget -qO "$TMP/pkg.tgz" "$URL"
fi

tar -xzf "$TMP/pkg.tgz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'renderlab-*' | head -n 1)"
[ -n "$SRC" ] || { echo "renderlab: download did not contain the package" >&2; exit 1; }

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
mkdir -p "$DEST"
for item in SKILL.md README.md LICENSE scripts assets references; do
  cp -R "$SRC/$item" "$DEST/"
done

echo "renderlab installed -> $DEST"
echo
echo "Next steps:"
echo "  1. Restart your agent (or reload skills) so it picks up the new folder."
echo '  2. Ask: "edit this video and render it using /Renderlab".'
echo
echo "Docs: https://github.com/raiton0902/renderlab"
