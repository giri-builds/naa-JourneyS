/** GitHub REST API wrapper — zero deps, native fetch.
 *  Handles diff fetch with paginated /files fallback for >300-file PRs. */

const GITHUB_API = "https://api.github.com";
const FILES_PAGE_SIZE = 100;
const MAX_FILES_PAGES = 30; // 30 * 100 = 3000 files max
const REQUEST_TIMEOUT_MS = 60_000;

export interface PullRequest {
  number: number;
  title: string;
  body: string | null;
  head: { sha: string; ref: string };
  base: { sha: string; ref: string };
  changed_files: number;
  additions: number;
  deletions: number;
}

export interface ReviewComment {
  path: string;
  line: number;
  body: string;
  side?: "RIGHT" | "LEFT";
}

interface FileEntry {
  filename: string;
  status: string;
  patch?: string;
}

function authHeaders(): Record<string, string> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error("GITHUB_TOKEN env var is not set.");
  return {
    Authorization: `Bearer ${token}`,
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "ai-review-agent",
  };
}

async function ghFetch(path: string, init?: RequestInit & { acceptDiff?: boolean }): Promise<Response> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  try {
    const headers: Record<string, string> = {
      ...authHeaders(),
      Accept: init?.acceptDiff
        ? "application/vnd.github.v3.diff"
        : "application/vnd.github+json",
      ...((init?.headers as Record<string, string>) || {}),
    };
    return await fetch(`${GITHUB_API}${path}`, {
      ...init,
      headers,
      signal: ctrl.signal,
    });
  } finally {
    clearTimeout(t);
  }
}

export async function getPullRequest(
  owner: string,
  repo: string,
  n: number,
): Promise<PullRequest> {
  const res = await ghFetch(`/repos/${owner}/${repo}/pulls/${n}`);
  if (!res.ok) {
    throw new Error(`GitHub getPullRequest ${res.status}: ${(await res.text()).slice(0, 500)}`);
  }
  return (await res.json()) as PullRequest;
}

export async function getPullRequestDiff(
  owner: string,
  repo: string,
  n: number,
): Promise<string> {
  const res = await ghFetch(`/repos/${owner}/${repo}/pulls/${n}`, { acceptDiff: true });

  if (res.ok) return await res.text();

  // 422 with "exceeded the maximum number of files" → fall back to paginated /files
  const errText = await res.text();
  const tooLarge =
    res.status === 422 &&
    /exceeded the maximum number of files/i.test(errText);
  if (!tooLarge) {
    throw new Error(`GitHub getPullRequestDiff ${res.status}: ${errText.slice(0, 500)}`);
  }

  console.warn("⚠️  PR exceeds 300 files; falling back to paginated /files endpoint");

  const parts: string[] = [];
  for (let page = 1; page <= MAX_FILES_PAGES; page++) {
    const r = await ghFetch(
      `/repos/${owner}/${repo}/pulls/${n}/files?per_page=${FILES_PAGE_SIZE}&page=${page}`,
    );
    if (!r.ok) {
      throw new Error(`GitHub /files page ${page} ${r.status}: ${(await r.text()).slice(0, 500)}`);
    }
    const files = (await r.json()) as FileEntry[];
    if (files.length === 0) break;

    for (const f of files) {
      if (!f.patch) continue; // binary/renamed-only files have no patch
      parts.push(`diff --git a/${f.filename} b/${f.filename}`);
      parts.push(`--- a/${f.filename}`);
      parts.push(`+++ b/${f.filename}`);
      parts.push(f.patch);
    }
    if (files.length < FILES_PAGE_SIZE) break;
  }

  return parts.join("\n") + "\n";
}

export async function postReview(
  owner: string,
  repo: string,
  n: number,
  payload: {
    event: "APPROVE" | "REQUEST_CHANGES" | "COMMENT";
    body: string;
    comments?: ReviewComment[];
  },
): Promise<void> {
  const res = await ghFetch(`/repos/${owner}/${repo}/pulls/${n}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`GitHub postReview ${res.status}: ${(await res.text()).slice(0, 1000)}`);
  }
}

export async function postComment(
  owner: string,
  repo: string,
  n: number,
  body: string,
): Promise<void> {
  const res = await ghFetch(`/repos/${owner}/${repo}/issues/${n}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
  if (!res.ok) {
    throw new Error(`GitHub postComment ${res.status}: ${(await res.text()).slice(0, 500)}`);
  }
}
