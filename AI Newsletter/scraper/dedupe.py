"""
Fingerprint-based deduplication.

Each article gets a SHA-256 fingerprint derived from its domain + title slug.
Seen fingerprints are persisted in seen.json at the repo root so duplicates
are skipped across pipeline runs without needing a database.

The GitHub Actions workflow commits seen.json back to the repo after each run.
"""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

SEEN_PATH = Path(__file__).parent.parent / "seen.json"


def _load_seen() -> set[str]:
    if SEEN_PATH.exists():
        with open(SEEN_PATH) as f:
            return set(json.load(f).get("fingerprints", []))
    return set()


def _save_seen(fingerprints: set[str]) -> None:
    with open(SEEN_PATH, "w") as f:
        json.dump({"fingerprints": sorted(fingerprints)}, f, indent=2)


def make_fingerprint(article: dict) -> str:
    """Stable fingerprint: SHA-256(domain + normalised_title)[:16]."""
    domain = urlparse(article.get("url", "")).netloc.lower()
    slug = re.sub(r"[^a-z0-9]", "-", article.get("title", "").lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")[:80]
    raw = f"{domain}:{slug}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def dedupe(articles: list[dict]) -> tuple[list[dict], int]:
    """
    Filter out already-seen articles and persist new fingerprints.

    Returns:
        (new_articles, skipped_count)
    """
    seen = _load_seen()
    new_articles: list[dict] = []
    new_fps: set[str] = set()
    skipped = 0

    for article in articles:
        fp = make_fingerprint(article)
        if fp in seen:
            skipped += 1
            continue
        article["fingerprint"] = fp
        new_articles.append(article)
        new_fps.add(fp)

    _save_seen(seen | new_fps)
    return new_articles, skipped
