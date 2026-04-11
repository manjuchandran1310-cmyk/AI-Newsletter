"""
Fetch articles from RSS/Atom feeds (feedparser) and HTML pages (httpx + BS4).
Falls back to HTML scraping when a source doesn't expose a feed.
"""

import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import httpx
import yaml
from bs4 import BeautifulSoup

SOURCES_PATH = Path(__file__).parent / "sources.yaml"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AINewsletter/1.0; +https://github.com)"}


def load_sources() -> list[dict]:
    with open(SOURCES_PATH) as f:
        return yaml.safe_load(f)["feeds"]


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def fetch_feed(source: dict) -> list[dict]:
    """Parse an RSS/Atom feed with feedparser. Returns up to 10 articles."""
    articles = []
    try:
        parsed = feedparser.parse(source["url"])
        if parsed.bozo and not parsed.entries:
            return []
        for entry in parsed.entries[:10]:
            raw_summary = entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "")
            articles.append({
                "title": entry.get("title", "").strip(),
                "url": entry.get("link", "").strip(),
                "summary": _clean_html(raw_summary)[:600],
                "published": entry.get("published", datetime.now(timezone.utc).isoformat()),
                "source": source["name"],
                "category": source["category"],
            })
    except Exception as e:
        print(f"[fetch] RSS error for {source['name']}: {e}")
    return articles


def fetch_html_page(source: dict) -> list[dict]:
    """Scrape an HTML page for article links as a fallback."""
    articles = []
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(source["url"])
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        base = urlparse(source["url"])
        seen_hrefs: set[str] = set()

        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]
            if not text or len(text) < 25 or len(text) > 200:
                continue
            if href.startswith("/"):
                href = f"{base.scheme}://{base.netloc}{href}"
            elif not href.startswith("http"):
                continue
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            articles.append({
                "title": text,
                "url": href,
                "summary": "",
                "published": datetime.now(timezone.utc).isoformat(),
                "source": source["name"],
                "category": source["category"],
            })
            if len(articles) >= 10:
                break
    except Exception as e:
        print(f"[fetch] HTML scrape error for {source['name']}: {e}")
    return articles


def fetch_article_content(url: str) -> str:
    """
    Fetch the full text of an article URL for richer Claude summarisation.
    Returns up to 3 000 characters of extracted body text.
    """
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers=HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        main = soup.find("article") or soup.find("main") or soup.find("body")
        if main:
            text = main.get_text(separator=" ", strip=True)
            text = re.sub(r"\s{2,}", " ", text)
            return text[:3000]
    except Exception as e:
        print(f"[fetch] Content fetch error for {url}: {e}")
    return ""


def fetch_all() -> list[dict]:
    """
    Fetch articles from every configured source.
    Tries RSS first; falls back to HTML scraping.
    Optionally enriches each article with full-page content.
    """
    sources = load_sources()
    all_articles: list[dict] = []

    for source in sources:
        print(f"[fetch] {source['name']} ...", end=" ", flush=True)
        articles = fetch_feed(source)
        if not articles:
            articles = fetch_html_page(source)
        print(f"{len(articles)} articles")
        all_articles.extend(articles)

    # Optionally backfill content for articles with thin summaries
    for article in all_articles:
        if len(article.get("summary", "")) < 100 and article.get("url"):
            article["content"] = fetch_article_content(article["url"])
        else:
            article["content"] = article.get("summary", "")

    return all_articles
