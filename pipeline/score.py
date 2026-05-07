"""
Scoring utilities.

The relevance_score (1–10) is produced by Claude inside summarise.py.
This module provides post-enrichment helpers: ranking, filtering, statistics.
"""


def rank_articles(articles: list[dict]) -> list[dict]:
    """Sort articles by relevance_score descending."""
    return sorted(articles, key=lambda a: a.get("relevance_score", 0), reverse=True)


def top_n(articles: list[dict], n: int = 5) -> list[dict]:
    """Return the top N articles by relevance score."""
    return rank_articles(articles)[:n]


def filter_by_min_score(articles: list[dict], min_score: int = 4) -> list[dict]:
    """Drop articles below the minimum score."""
    return [a for a in articles if a.get("relevance_score", 0) >= min_score]


def score_summary(articles: list[dict]) -> dict:
    """Return basic score distribution statistics."""
    scores = [a["relevance_score"] for a in articles if isinstance(a.get("relevance_score"), (int, float))]
    if not scores:
        return {"count": 0, "avg": 0.0, "max": 0, "min": 0}
    return {
        "count": len(scores),
        "avg": round(sum(scores) / len(scores), 2),
        "max": max(scores),
        "min": min(scores),
    }
