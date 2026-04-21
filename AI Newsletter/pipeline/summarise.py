"""
Summarise articles using the Groq API (llama-3.3-70b-versatile).

Groq is FREE — no credit card required.
Free tier: 14,400 requests/day, 30 req/min, 6,000 tokens/min
Sign up + get API key at: https://console.groq.com

Sends batches of up to 5 articles per API call (Groq token limits are tighter).
Includes automatic retry with back-off for 429 rate-limit responses.
"""

import json
import os
import re
import time

from groq import Groq

MODEL = "llama-3.3-70b-versatile"   # best free model on Groq; 128k context window
MAX_RETRIES = 3
BATCH_SIZE = 5                       # smaller batches to stay within token limits

SYSTEM_PROMPT = (
    "You are an expert AI industry analyst writing for a technical audience of "
    "engineers, product managers, and founders. "
    "Always respond with valid JSON only — no markdown fences, no preamble, no trailing text."
)

BATCH_PROMPT = """\
Analyse the {n} articles below. Return a JSON array — one object per article, \
preserving the original index field — with exactly these fields:

  "index"           : integer  (same as input)
  "title"           : string   (original title, unchanged)
  "one_liner"       : string   (<=20 words — what happened)
  "summary"         : string   (3-4 sentences: key facts, context, implications)
  "category"        : string   (one of: AI, Product, Funding, Research, Community, \
Innovation & AI, Figma Updates, Meta AI, Anthropic News, OpenAI News, Other)
  "relevance_score" : integer  (1-10; 10 = must-read for AI practitioners)
  "entities"        : [string] (company / person / product names mentioned)
  "why_it_matters"  : string   (1 sentence for a reader with 30 seconds to spare)

Articles:
{articles_json}

Return only the JSON array, nothing else."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_retry_delay(error_str: str) -> int:
    """Extract the suggested retry delay (seconds) from a 429 error message."""
    match = re.search(r"try again in ([\d.]+)s", error_str, re.IGNORECASE)
    if match:
        return int(float(match.group(1))) + 2
    return 30   # safe default


def _get_client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def summarise_batch(articles: list[dict]) -> list[dict]:
    """Summarise up to 5 articles in a single Groq API call (with retry)."""
    client = _get_client()

    payload = [
        {
            "index": i,
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "content": a.get("content", a.get("summary", ""))[:1500],
            "source": a.get("source", ""),
        }
        for i, a in enumerate(articles)
    ]

    prompt = BATCH_PROMPT.format(
        n=len(articles),
        articles_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            raw = _strip_fences(response.choices[0].message.content)
            results: list[dict] = json.loads(raw)

            by_index = {r.get("index", i): r for i, r in enumerate(results)}
            return [{**article, **by_index.get(i, {})} for i, article in enumerate(articles)]

        except Exception as e:
            last_error = e
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str.lower():
                wait = _parse_retry_delay(error_str)
                print(f"  [retry {attempt}/{MAX_RETRIES}] Rate limited — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise   # non-rate-limit errors bubble up immediately

    raise last_error   # all retries exhausted


def summarise_all(articles: list[dict], batch_size: int = BATCH_SIZE) -> list[dict]:
    """Summarise all articles, processing in batches."""
    results: list[dict] = []
    total_batches = (len(articles) + batch_size - 1) // batch_size

    for batch_num, start in enumerate(range(0, len(articles), batch_size), 1):
        batch = articles[start : start + batch_size]
        print(f"[summarise] Batch {batch_num}/{total_batches} ({len(batch)} articles)...")
        try:
            enriched = summarise_batch(batch)
            results.extend(enriched)
            if batch_num < total_batches:
                time.sleep(1.5)   # gentle pacing — Groq free tier: 30 req/min
        except Exception as e:
            print(f"[summarise] Batch {batch_num} failed: {e}")
            print(f"[summarise] Including {len(batch)} articles without AI enrichment")
            for a in batch:
                a.setdefault("relevance_score", 5)
                a.setdefault("one_liner", a.get("title", ""))
                a.setdefault("summary", a.get("content", a.get("summary", "")))
                a.setdefault("category", a.get("category", "Other"))
                a.setdefault("entities", [])
                a.setdefault("why_it_matters", "")
            results.extend(batch)

    return results
