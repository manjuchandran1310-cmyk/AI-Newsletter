"""
Summarise articles using the Google Gemini API (gemini-1.5-flash).

Free tier: 1,500 requests/day, 1M tokens/min — no credit card required.
Get your key at: https://aistudio.google.com/app/apikey

Sends batches of up to 10 articles per API call to minimise quota usage.
Gemini returns structured JSON with: title, one_liner, summary, category,
relevance_score, entities, and why_it_matters.
"""

import json
import os
import re
import time

import google.generativeai as genai

MODEL = "gemini-1.5-flash"

SYSTEM_INSTRUCTION = (
    "You are an expert AI industry analyst writing for a technical audience of "
    "engineers, product managers, and founders. You produce concise, insightful "
    "newsletter summaries. Always respond with valid JSON only — no markdown "
    "fences, no preamble, no trailing text."
)

BATCH_PROMPT = """\
Analyse the {n} articles below. Return a JSON array — one object per article, \
preserving the original index field — with exactly these fields:

  "index"           : integer  (same as input)
  "title"           : string   (original title, unchanged)
  "one_liner"       : string   (≤20 words — what happened)
  "summary"         : string   (3–4 sentences: key facts, context, implications)
  "category"        : string   (one of: AI, Product, Funding, Research, Community, \
Innovation & AI, Figma Updates, Meta AI, Anthropic News, OpenAI News, Other)
  "relevance_score" : integer  (1–10; 10 = must-read for AI practitioners)
  "entities"        : [string] (company / person / product names mentioned)
  "why_it_matters"  : string   (1 sentence for a reader with 30 seconds to spare)

Articles:
{articles_json}

Return only the JSON array."""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _get_model() -> genai.GenerativeModel:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    return genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
    )


def summarise_batch(articles: list[dict]) -> list[dict]:
    """Summarise up to 10 articles in a single Gemini API call."""
    model = _get_model()

    payload = [
        {
            "index": i,
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "content": a.get("content", a.get("summary", ""))[:2000],
            "source": a.get("source", ""),
        }
        for i, a in enumerate(articles)
    ]

    prompt = BATCH_PROMPT.format(
        n=len(articles),
        articles_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )

    response = model.generate_content(prompt)
    raw = _strip_fences(response.text)
    results: list[dict] = json.loads(raw)

    # Index results for fast lookup
    by_index = {r.get("index", i): r for i, r in enumerate(results)}

    enriched = []
    for i, article in enumerate(articles):
        claude_data = by_index.get(i, {})
        enriched.append({**article, **claude_data})
    return enriched


def summarise_all(articles: list[dict], batch_size: int = 10) -> list[dict]:
    """Summarise all articles, processing in batches of `batch_size`."""
    results: list[dict] = []
    total_batches = (len(articles) + batch_size - 1) // batch_size

    for batch_num, start in enumerate(range(0, len(articles), batch_size), 1):
        batch = articles[start : start + batch_size]
        print(f"[summarise] Batch {batch_num}/{total_batches} ({len(batch)} articles)...")
        try:
            enriched = summarise_batch(batch)
            results.extend(enriched)
            # Small delay to respect free-tier rate limits (2 req/s)
            if batch_num < total_batches:
                time.sleep(0.5)
        except Exception as e:
            print(f"[summarise] Batch {batch_num} failed: {e} — including raw articles")
            results.extend(batch)

    return results
