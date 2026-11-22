#!/usr/bin/env node
/**
 * Is this change only formatting? (code-quality skill: references/agent-loop.md, "Adopting a formatter")
 *
 *   node format-only-prettier.mjs [--base origin/main]   (from the repo root, next to node_modules)
 *
 * Running Prettier over old code changes thousands of lines the PR did not really write, and the changed-line
 * checks would judge all of them. CI skips those checks only when this script proves
 * that every changed file is exactly Prettier applied to its own version at the merge base. Anything else (an
 * added, deleted or renamed file of any type, a change to the Prettier settings or dependencies, a file Prettier
 * does not format) means "false", so a real code change cannot pass as formatting. Workflow files (.github/) are
 * not judged: the changed-line checks never cover them, and the formatting PR adds its CI step there.
 * Prints "true" or "false" on stdout and the reason on stderr. Any git or Prettier error prints "false", so the
 * checks run as usual. In CI, run the BASE branch's copy (git show it to an untracked file in the repo root so it
 * resolves node_modules, run it, delete it), so a PR cannot change the check it is judged by.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as prettier from "prettier";

/** Files whose change could alter what Prettier produces; a PR that touches them is never "formatting only". */
const SETTINGS = /^(\.prettierrc.*|prettier\.config\..*|\.prettierignore|\.editorconfig|package(-lock)?\.json)$/;

function git(args) {
  const r = spawnSync("git", args, { encoding: "utf8", maxBuffer: 64 << 20 });
  if (r.status !== 0) throw new Error(`git ${args[0]} failed: ${r.stderr.trim()}`);
  return r.stdout;
}

/** [status, path] pairs from `git diff --name-status -z` output, workflow files left out. */
export function parseNameStatus(text) {
  const parts = text.split("\0");
  const out = [];
  for (let i = 0; i + 1 < parts.length; i += 2) out.push([parts[i], parts[i + 1]]);
  return out.filter(([, file]) => !file.startsWith(".github/"));
}

/** Why this changed file alone rules out "formatting only", or null when it may be a formatting change. */
export function notFormatting(status, file) {
  if (status !== "M") return `${file}: added, deleted or renamed (${status})`;
  if (SETTINGS.test(path.basename(file))) return `${file}: Prettier settings or dependencies changed`;
  return null;
}

/** `source` after Prettier with the options that apply to `file`, as the CLI would; plugins are never loaded. */
export async function formatted(source, file) {
  const options = (await prettier.resolveConfig(file, { editorconfig: true })) ?? {};
  return prettier.format(source, { ...options, plugins: [], filepath: file });
}

const defaultDiff = (base) => git(["diff", "--merge-base", base, "--name-status", "--no-renames", "--relative", "-z"]);

/** [onlyFormatting, reason] for the working tree against the merge base with `base`; I/O injectable for tests. */
export async function check(base, { diff = () => defaultDiff(base), readBase, readHead } = {}) {
  const files = parseNameStatus(diff());
  if (files.length === 0) return [true, "no file changed"];
  for (const [status, file] of files) {
    const reason = notFormatting(status, file);
    if (reason) return [false, reason];
  }
  const mergeBase = readBase ? null : git(["merge-base", base, "HEAD"]).trim();
  const fromBase = readBase ?? ((f) => git(["show", `${mergeBase}:./${f}`]));
  const fromHead = readHead ?? ((f) => readFileSync(f, "utf8"));
  for (const [, file] of files) {
    const info = await prettier.getFileInfo(file, { ignorePath: ".prettierignore" });
    if (info.ignored || !info.inferredParser) return [false, `${file}: not a file Prettier formats`];
    if ((await formatted(fromBase(file), file)) !== fromHead(file)) {
      return [false, `${file}: differs from its formatted base version`];
    }
  }
  return [true, `${files.length} files changed, all only by Prettier`];
}

export async function main(argv) {
  const i = argv.indexOf("--base");
  const base = i >= 0 ? argv[i + 1] : "origin/main";
  let only, reason;
  try {
    [only, reason] = await check(base);
  } catch (e) {
    [only, reason] = [false, `could not check (${e.message}); running the changed-line checks`];
  }
  console.log(only ? "true" : "false");
  console.error(`formatting only: ${reason}`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main(process.argv.slice(2));
