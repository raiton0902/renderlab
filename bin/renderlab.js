#!/usr/bin/env node
/**
 * Renderlab installer.
 *
 *   npx github:raiton0902/renderlab             install to ~/.dsh/skills/renderlab
 *   npx github:raiton0902/renderlab --claude    install to ~/.claude/skills/renderlab
 *   npx github:raiton0902/renderlab --dir PATH  install anywhere
 *   npx github:raiton0902/renderlab --force     overwrite an existing install
 */
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");

const ITEMS = ["SKILL.md", "README.md", "LICENSE", "scripts", "assets", "references"];
const NAME = "renderlab";

function usage() {
  console.log(`renderlab - install the Renderlab agent skill

Usage:
  npx github:raiton0902/renderlab [options]

Options:
  --dir <path>   install into <path> (default: ~/.dsh/skills/renderlab)
  --claude       install into ~/.claude/skills/renderlab
  --force        overwrite an existing install
  -h, --help     show this message
`);
}

function parse(argv) {
  const opts = { dir: null, claude: false, force: false, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--help" || a === "-h") opts.help = true;
    else if (a === "--claude") opts.claude = true;
    else if (a === "--force") opts.force = true;
    else if (a === "--dir") {
      const next = argv[i + 1];
      if (!next) throw new Error("--dir needs a path");
      opts.dir = next;
      i += 1;
    } else if (a.startsWith("--dir=")) opts.dir = a.slice(6);
    else throw new Error("unknown option: " + a);
  }
  return opts;
}

function copyInto(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      if (entry === "__pycache__" || entry.endsWith(".pyc")) continue;
      copyInto(path.join(src, entry), path.join(dest, entry));
    }
  } else {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
  }
}

function main() {
  let opts;
  try {
    opts = parse(process.argv.slice(2));
  } catch (err) {
    console.error("renderlab: " + err.message + "\n");
    usage();
    process.exit(2);
  }
  if (opts.help) {
    usage();
    return;
  }

  const pkgRoot = path.resolve(__dirname, "..");
  const missing = ITEMS.filter((item) => !fs.existsSync(path.join(pkgRoot, item)));
  if (missing.length) {
    console.error(
      "renderlab: this package is incomplete, missing: " + missing.join(", ") + "\n" +
      "Reinstall with: npx --yes github:raiton0902/renderlab"
    );
    process.exit(1);
  }

  const target = path.resolve(
    opts.dir ||
      (opts.claude
        ? path.join(os.homedir(), ".claude", "skills", NAME)
        : path.join(os.homedir(), ".dsh", "skills", NAME))
  );

  if (fs.existsSync(target) && !opts.force) {
    console.error(
      "renderlab: already installed at " + target + "\n" +
      "Add --force to replace it, or --dir to install somewhere else."
    );
    process.exit(1);
  }

  fs.rmSync(target, { recursive: true, force: true });
  fs.mkdirSync(target, { recursive: true });
  for (const item of ITEMS) copyInto(path.join(pkgRoot, item), path.join(target, item));

  console.log("renderlab installed -> " + target);
  console.log("");
  console.log("Next steps:");
  console.log("  1. Restart your agent (or reload skills) so it picks up the new folder.");
  console.log('  2. Ask: "edit this video and render it using /Renderlab".');
  console.log("");
  console.log("Docs: https://github.com/raiton0902/renderlab");
}

main();
