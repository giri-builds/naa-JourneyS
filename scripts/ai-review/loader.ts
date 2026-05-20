/** Diff loader, filter, and diff-line-set builder. */

import { promises as fs } from "node:fs";
import * as path from "node:path";
import { getPullRequestDiff } from "./github.ts";

export const MAX_DIFF_CHARS = 200_000;
export const MAX_PR_LINES = 100_000;

// Files we never want the agent reviewing — lockfiles, binaries, generated
// artifacts, journey content (markdown), and docs (cause hallucinations:
// the agent reads docs as findings instead of code).
const EXCLUDE_PATTERNS: RegExp[] = [
  /(^|\/)package-lock\.json$/,
  /(^|\/)pnpm-lock\.yaml$/,
  /(^|\/)yarn\.lock$/,
  /(^|\/)Pipfile\.lock$/,
  /(^|\/)poetry\.lock$/,
  /(^|\/)Cargo\.lock$/,
  /(^|\/)go\.sum$/,
  /\.(png|jpg|jpeg|gif|webp|svg|ico|bmp|tiff)$/i,
  /\.(woff2?|ttf|otf|eot)$/i,
  /\.(mp3|mp4|webm|ogg|wav|mov)$/i,
  /\.(zip|tar|gz|bz2|7z|rar)$/i,
  /\.npy$/, /\.bin$/, /\.parquet$/,
  /(^|\/)backend\/data\//,
  /(^|\/)node_modules\//,
  /(^|\/)\.venv\//, /(^|\/)venv\//, /(^|\/)__pycache__\//,
  /(^|\/)dist\//, /(^|\/)build\//, /(^|\/)\.next\//, /(^|\/)\.astro\//,
  /(^|\/)public\//,
  /\.min\.(js|css)$/,
  /\.md$/i,        // exclude markdown — docs cause hallucinations
  /(^|\/)docs\//i, // ditto
];

function isExcluded(filename: string): boolean {
  return EXCLUDE_PATTERNS.some((re) => re.test(filename));
}

export interface LoadedDiff {
  diff: string;
  truncated: boolean;
  filesIncluded: number;
  filesExcluded: number;
  totalLines: number;
}

/**
 * Fetch the raw diff, drop excluded files block-by-block, cap at
 * MAX_DIFF_CHARS. Returns the filtered diff and metadata.
 */
export async function loadDiff(
  owner: string,
  repo: string,
  n: number,
): Promise<LoadedDiff> {
  const raw = await getPullRequestDiff(owner, repo, n);

  // Split on `diff --git ...` boundaries while keeping the boundary line.
  const blocks: string[] = [];
  const lines = raw.split("\n");
  let current: string[] = [];
  for (const line of lines) {
    if (line.startsWith("diff --git ")) {
      if (current.length) blocks.push(current.join("\n"));
      current = [line];
    } else {
      current.push(line);
    }
  }
  if (current.length) blocks.push(current.join("\n"));

  let filesIncluded = 0;
  let filesExcluded = 0;
  const kept: string[] = [];

  for (const block of blocks) {
    const m = block.match(/^diff --git a\/(.+?) b\/(.+?)$/m);
    if (!m) continue;
    const filename = m[2]; // NEW path
    if (isExcluded(filename)) {
      filesExcluded++;
      continue;
    }
    filesIncluded++;
    kept.push(block);
  }

  let diff = kept.join("\n");
  let truncated = false;
  if (diff.length > MAX_DIFF_CHARS) {
    diff = diff.slice(0, MAX_DIFF_CHARS);
    truncated = true;
  }

  const totalLines = diff.split("\n").length;
  return { diff, truncated, filesIncluded, filesExcluded, totalLines };
}

export async function loadContextFile(filename: string): Promise<string> {
  const root = process.cwd();
  const p = path.join(root, ".github", "ai-review", filename);
  return await fs.readFile(p, "utf8");
}

/**
 * Parse a unified diff and return the set of (file, NEW-side line) pairs
 * that GitHub will accept as inline-comment targets — added lines (+) and
 * unchanged context lines (space). Used to filter hallucinated comment
 * targets before posting; otherwise GitHub rejects the WHOLE review with
 * 422 on the first invalid line.
 */
export function buildDiffLineSet(diff: string): Set<string> {
  const set = new Set<string>();
  const lines = diff.split("\n");
  let currentFile: string | null = null;
  let newLine = 0;
  let inHunk = false;

  for (const line of lines) {
    const fileMatch = line.match(/^\+\+\+ b\/(.+)$/);
    if (fileMatch) {
      currentFile = fileMatch[1];
      inHunk = false;
      continue;
    }
    const hunkMatch = line.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
    if (hunkMatch) {
      newLine = Number(hunkMatch[1]);
      inHunk = true;
      continue;
    }
    if (!inHunk || !currentFile) continue;

    if (line.startsWith("+") && !line.startsWith("+++")) {
      set.add(`${currentFile}:${newLine}`);
      newLine++;
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      // OLD-side only; don't advance newLine
    } else if (line.startsWith(" ")) {
      // context line — addressable
      set.add(`${currentFile}:${newLine}`);
      newLine++;
    } else if (line.startsWith("\\")) {
      // "\ No newline at end of file" — skip
    }
  }
  return set;
}
