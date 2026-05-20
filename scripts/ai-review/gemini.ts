/** Gemini REST API wrapper — zero deps, native fetch.
 *  Falls back through model chain on 429/5xx (quota / overload). */

const DEFAULT_MODELS = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"];
const FALLBACK_STATUSES = new Set([429, 500, 502, 503, 504]);
const REQUEST_TIMEOUT_MS = 120_000;

export interface GeminiCallOptions {
  systemPrompt: string;
  userPrompt: string;
  maxOutputTokens?: number;
  temperature?: number;
}

export interface GeminiResponse {
  text: string;
  durationMs: number;
  modelUsed: string;
}

export async function callGemini(opts: GeminiCallOptions): Promise<GeminiResponse> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("GEMINI_API_KEY env var is not set.");

  const models =
    process.env.GEMINI_MODELS?.split(",").map((s: string) => s.trim()).filter(Boolean) ||
    DEFAULT_MODELS;

  let lastError: Error | undefined;

  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      const r = await callOne(model, apiKey, opts);
      if (i > 0) console.warn(`⤵️  Fell back to ${model}`);
      return r;
    } catch (err) {
      const status = (err as Error).message.match(/Gemini API (\d{3}):/)?.[1];
      if (status && FALLBACK_STATUSES.has(Number(status))) {
        console.warn(`⚠️  ${model} returned ${status}; trying next.`);
        lastError = err as Error;
        continue;
      }
      throw err;
    }
  }
  throw new Error(`All ${models.length} models failed. Last: ${lastError?.message}`);
}

async function callOne(
  model: string,
  key: string,
  opts: GeminiCallOptions,
): Promise<GeminiResponse> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`;
  const body = {
    systemInstruction: { parts: [{ text: opts.systemPrompt }] },
    contents: [{ role: "user", parts: [{ text: opts.userPrompt }] }],
    generationConfig: {
      temperature: opts.temperature ?? 0.2,
      // CRITICAL: 32K not 8K. 8K truncates findings JSON mid-response.
      maxOutputTokens: opts.maxOutputTokens ?? 32_768,
      responseMimeType: "application/json",
    },
  };

  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  const start = Date.now();

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      throw new Error(`Gemini API ${res.status}: ${(await res.text()).slice(0, 500)}`);
    }
    const json = (await res.json()) as {
      candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
    };
    const text = json.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) {
      throw new Error(`Gemini empty response: ${JSON.stringify(json).slice(0, 500)}`);
    }
    return { text, durationMs: Date.now() - start, modelUsed: model };
  } finally {
    clearTimeout(t);
  }
}

export function parseGeminiJson<T>(text: string): T {
  const cleaned = text
    .trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/i, "")
    .trim();
  try {
    return JSON.parse(cleaned) as T;
  } catch (err) {
    throw new Error(
      `JSON parse failed: ${(err as Error).message}\nFirst 500: ${cleaned.slice(0, 500)}`,
    );
  }
}
