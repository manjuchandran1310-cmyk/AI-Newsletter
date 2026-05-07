"""
Category utilities.

Claude assigns a category to each article inside summarise.py.
This module provides helpers to group and filter the enriched articles
for use in the email template and graph ingestion.
"""

AI_CATEGORIES = {"AI", "AI Research", "Innovation & AI", "Meta AI", "Anthropic News", "OpenAI News"}
PRODUCT_CATEGORIES = {"Product", "Figma Updates"}
FUNDING_CATEGORIES = {"Funding", "Business"}
COMMUNITY_CATEGORIES = {"Community"}


def categorise_articles(articles: list[dict]) -> dict[str, list[dict]]:
    """Group articles by their category field."""
    grouped: dict[str, list[dict]] = {}
    for article in articles:
        cat = article.get("category", "Other")
        grouped.setdefault(cat, []).append(article)
    return grouped


def get_top_story(articles: list[dict]) -> dict | None:
    """Return the single highest-scoring article."""
    scored = [a for a in articles if isinstance(a.get("relevance_score"), (int, float))]
    if not scored:
        return None
    return max(scored, key=lambda a: a["relevance_score"])


def filter_by_min_score(articles: list[dict], min_score: int = 4) -> list[dict]:
    """Drop articles below a minimum relevance threshold."""
    return [a for a in articles if a.get("relevance_score", 0) >= min_score]


def get_section(articles: list[dict], categories: set[str], limit: int = 5) -> list[dict]:
    """Return articles matching any of the given categories, sorted by score."""
    matched = [a for a in articles if a.get("category", "") in categories]
    return sorted(matched, key=lambda a: a.get("relevance_score", 0), reverse=True)[:limit]
