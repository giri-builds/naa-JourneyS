/** AI PR Review — orchestrator. Runs Pass 1 (security), Pass 2 (architect),
 *  Pass 3 (lead synthesis), filters hallucinations, posts a single review. */

import { callGemini, parseGeminiJson } from "./gemini.ts";
import {
  getPullRequest,
  postReview,
  postComment,
  type ReviewComment,
} from "./github.ts";
import {
  loadDiff,
  loadContextFile,
  buildDiffLineSet,
  MAX_PR_LINES,
} from "./loader.ts";

interface Finding {
  severity: "BLOCKING" | "IMPORTANT" | "NICE-TO-HAVE";
  file: string;
  line: number;
  title: string;
  explanation: string;
  fix: string;
}

interface PassOutput {
  findings: Finding[];
}

interface LeadOutput {
  verdict: "APPROVE" | "REQUEST_CHANGES" | "COMMENT";
  body: string;
  inline_comments: Array<{ file: string; line: number; body: string }>;
}

const SPECULATIVE_PHRASES = [
  /\bcould lead to\b/i,
  /\bmight lead to\b/i,
  /\bcould potentially\b/i,
  /\bpotentially (?:leading|causing|resulting|introducing)\b/i,
  /\bmay (?:lead|cause|result) to\b/i,
  /\bif not implemented\b/i,
  /\bif (?:it|this|that|x) (?:were|was)\b/i,
  /\bif .{1,80}? (?:are|is) not (?:updated|set|defined|present|provided|configured|implemented)\b/i,
  /\bwill be undefined\b/i,
  /\bappears to be\b/i,
  /\bseems to lack\b/i,
  /\bseems to be\b/i,
  /\bthe documentation states\b/i,
  /\bthe documentation suggests\b/i,
  /\bwithout the full diff\b/i,
  /\bin a worst case scenario\b/i,
];

function looksSpeculative(body: string): boolean {
  return SPECULATIVE_PHRASES.some((re) => re.test(body));
}

function normalizeWhitespace(s: string): string {
  return s.replace(/\s+/g, " ").trim();
}

/**
 * Pull every backtick-quoted snippet ≥15 chars containing programming-ish
 * characters, then check that at least one is a (whitespace-normalised)
 * substring of the diff. If none match, the LLM fabricated the quote.
 */
function hasGroundedQuote(body: string, diff: string): boolean {
  const re = /`([^`\n]{15,})`/g;
  const normalizedDiff = normalizeWhitespace(diff);
  let m: RegExpExecArray | null;
  while ((m = re.exec(body)) !== null) {
    const snippet = m[1];
    if (!/[{};=()<>.\[\]]|=>/.test(snippet)) continue;
    if (normalizedDiff.includes(normalizeWhitespace(snippet))) return true;
  }
  return false;
}

/**
 * Line:1–5 with no import/module/env context = the agent pattern-matched
 * the path without reading the code.
 */
function hasSuspiciousLineNumber(line: number, body: string): boolean {
  if (line > 5) return false;
  return !/import|require|module|export const|export default|env\.|os\.environ/i.test(body);
}

function repoSlug(): { owner: string; repo: string } {
  const slug = process.env.GITHUB_REPOSITORY;
  if (!slug || !slug.includes("/")) {
    throw new Error(`GITHUB_REPOSITORY must be 'owner/repo', got: ${slug}`);
  }
  const [owner, repo] = slug.split("/");
  return { owner, repo };
}

async function runPass(
  passName: string,
  personaFile: string,
  stackRules: string,
  diff: string,
  truncated: boolean,
  extraContext?: string,
): Promise<{ findings: Finding[]; durationMs: number; modelUsed: string }> {
  const persona = await loadContextFile(personaFile);
  const systemPrompt = `${persona}\n\n---\n\n# Project Stack Rules\n\n${stackRules}`;
  const userPrompt = [
    `# PR Diff (truncated=${truncated})`,
    "",
    "```diff",
    diff,
    "```",
    extraContext ? `\n\n${extraContext}` : "",
  ].join("\n");

  console.log(`▶  ${passName} starting`);
  const r = await callGemini({ systemPrompt, userPrompt });
  console.log(`✓  ${passName} done in ${r.durationMs}ms (${r.modelUsed})`);

  let parsed: PassOutput;
  try {
    parsed = parseGeminiJson<PassOutput>(r.text);
  } catch (err) {
    console.warn(`⚠️  ${passName} returned unparseable JSON: ${(err as Error).message}`);
    parsed = { findings: [] };
  }
  return { findings: parsed.findings || [], durationMs: r.durationMs, modelUsed: r.modelUsed };
}

async function main(): Promise<void> {
  const { owner, repo } = repoSlug();
  const prNumber = Number(process.env.PR_NUMBER);
  if (!Number.isFinite(prNumber) || prNumber <= 0) {
    throw new Error(`PR_NUMBER env var must be a positive integer, got: ${process.env.PR_NUMBER}`);
  }

  console.log(`🔎 Reviewing ${owner}/${repo}#${prNumber}`);

  const pr = await getPullRequest(owner, repo, prNumber);
  console.log(`   "${pr.title}" — ${pr.changed_files} files, +${pr.additions}/-${pr.deletions}`);

  const totalLines = pr.additions + pr.deletions;
  if (totalLines > MAX_PR_LINES) {
    const msg = [
      `🛡️ AI review skipped — PR is too large (${totalLines} lines changed; cap is ${MAX_PR_LINES}).`,
      ``,
      `Please split this into smaller PRs. The reviewer is calibrated for focused changes; very large PRs produce diluted findings.`,
    ].join("\n");
    await postComment(owner, repo, prNumber, msg);
    return;
  }

  const { diff, truncated, filesIncluded, filesExcluded, totalLines: diffLines } = await loadDiff(
    owner, repo, prNumber,
  );
  console.log(
    `   Diff: ${filesIncluded} file(s) included, ${filesExcluded} excluded, ${diffLines} lines, truncated=${truncated}`,
  );
  if (filesIncluded === 0) {
    await postComment(
      owner,
      repo,
      prNumber,
      "🛡️ AI review skipped — no reviewable code in this PR (all files excluded: lockfiles, binaries, docs, generated artifacts).",
    );
    return;
  }

  const stackRules = await loadContextFile("stack-rules.md");

  const [pass1, pass2] = await Promise.all([
    runPass("Pass 1 (security)", "persona-security.md", stackRules, diff, truncated),
    runPass("Pass 2 (architect)", "persona-architect.md", stackRules, diff, truncated),
  ]);

  const passContext = [
    "# Pass 1 (Security) findings",
    JSON.stringify(pass1.findings, null, 2),
    "",
    "# Pass 2 (Architect) findings",
    JSON.stringify(pass2.findings, null, 2),
  ].join("\n");

  const leadPersona = await loadContextFile("persona-lead.md");
  const leadSystem = `${leadPersona}\n\n---\n\n# Project Stack Rules\n\n${stackRules}`;
  const leadUser = [
    `# PR Diff (truncated=${truncated})`,
    "",
    "```diff",
    diff,
    "```",
    "",
    passContext,
  ].join("\n");

  console.log(`▶  Pass 3 (lead) starting`);
  const leadRaw = await callGemini({ systemPrompt: leadSystem, userPrompt: leadUser });
  console.log(`✓  Pass 3 (lead) done in ${leadRaw.durationMs}ms (${leadRaw.modelUsed})`);

  let lead: LeadOutput;
  try {
    lead = parseGeminiJson<LeadOutput>(leadRaw.text);
  } catch (err) {
    throw new Error(`Pass 3 returned unparseable JSON: ${(err as Error).message}`);
  }

  // Filter inline comments: drop fabricated, speculative, line:1-5-without-context,
  // and any line outside the diff line set.
  const lineSet = buildDiffLineSet(diff);
  let droppedFabricated = 0;
  let droppedSpeculative = 0;
  let droppedSuspiciousLine = 0;
  const orphaned: typeof lead.inline_comments = [];

  const validInline: ReviewComment[] = [];
  for (const c of lead.inline_comments || []) {
    if (!hasGroundedQuote(c.body, diff)) {
      droppedFabricated++;
      continue;
    }
    if (looksSpeculative(c.body)) {
      droppedSpeculative++;
      continue;
    }
    if (hasSuspiciousLineNumber(c.line, c.body)) {
      droppedSuspiciousLine++;
      continue;
    }
    if (!lineSet.has(`${c.file}:${c.line}`)) {
      orphaned.push(c);
      continue;
    }
    validInline.push({ path: c.file, line: c.line, body: c.body, side: "RIGHT" });
  }

  const filterCount = droppedFabricated + droppedSpeculative + droppedSuspiciousLine;
  const filterBanner =
    filterCount > 0
      ? `🛡️ Filtered ${filterCount} unsubstantiated finding(s): ${droppedFabricated} fabricated quote(s), ${droppedSpeculative} speculative claim(s), ${droppedSuspiciousLine} suspicious line:1–5 reference(s).\n\n`
      : "";

  const orphanedSection =
    orphaned.length > 0
      ? [
          "",
          "---",
          "",
          "### ⚠️ Inline comments not pinned to diff",
          "",
          "These findings reference lines outside the changed hunks; surfaced here instead:",
          "",
          ...orphaned.map((o) => `- **${o.file}:${o.line}** — ${o.body}`),
        ].join("\n")
      : "";

  const reviewedFooter = [
    "",
    "---",
    "",
    "**What I reviewed**",
    `- Files: ${filesIncluded} included, ${filesExcluded} excluded (lockfiles/binaries/docs)`,
    `- Diff size: ${diffLines} lines${truncated ? " (truncated)" : ""}`,
    `- Pass 1 (security): ${pass1.durationMs}ms via ${pass1.modelUsed}`,
    `- Pass 2 (architect): ${pass2.durationMs}ms via ${pass2.modelUsed}`,
    `- Pass 3 (lead): ${leadRaw.durationMs}ms via ${leadRaw.modelUsed}`,
  ].join("\n");

  const finalBody = `${filterBanner}${lead.body}${orphanedSection}${reviewedFooter}`;

  await postReview(owner, repo, prNumber, {
    event: lead.verdict,
    body: finalBody,
    comments: validInline,
  });

  console.log(
    `✅ Posted ${lead.verdict} with ${validInline.length} inline comment(s); filtered ${filterCount}, ${orphaned.length} orphan(s) moved to body`,
  );
}

main().catch(async (err) => {
  console.error("❌ AI review failed:", err);
  try {
    const { owner, repo } = repoSlug();
    const prNumber = Number(process.env.PR_NUMBER);
    if (Number.isFinite(prNumber) && prNumber > 0) {
      await postComment(
        owner,
        repo,
        prNumber,
        [
          "🛡️ **AI review failed**",
          "",
          "The reviewer hit an error before posting findings. The team should investigate the workflow run.",
          "",
          "```",
          (err as Error).message?.slice(0, 1500) || String(err),
          "```",
        ].join("\n"),
      );
    }
  } catch (postErr) {
    console.error("Also failed to post error comment:", postErr);
  }
  process.exit(1);
});
