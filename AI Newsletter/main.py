"""
AI Newsletter Pipeline — Orchestrator
======================================
Stages
  1. Fetch   — pull articles from all configured RSS / HTML sources
  2. Dedupe  — skip articles already processed in prior runs
  3. Enrich  — summarise, score, and categorise via Gemini API (batches of 10)
  4. Graph   — write articles + entities + relationships to Neo4j AuraDB
  5. Email   — render Jinja2 template and deliver via Resend

Run locally:
  cp .env.example .env   # fill in your secrets
  pip install -r requirements.txt
  python main.py

In CI the env vars come from GitHub Secrets (see .github/workflows/newsletter.yml).
"""

import os
import sys

# Load .env for local development (no-op when vars are already set in CI)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional in CI


def _check_env(*keys: str) -> None:
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        print(f"[main] Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)


def main() -> None:
    _check_env("GOOGLE_API_KEY", "RESEND_API_KEY", "RECIPIENT_EMAIL")

    print("=" * 50)
    print("  AI Newsletter Pipeline")
    print("=" * 50)

    # ── 1. Fetch ──────────────────────────────────────────
    print("\n[1/5] Fetching articles from all sources...")
    from scraper.fetch import fetch_all
    articles = fetch_all()
    print(f"  → {len(articles)} articles fetched total")

    # ── 2. Deduplicate ────────────────────────────────────
    print("\n[2/5] Deduplicating...")
    from scraper.dedupe import dedupe
    articles, skipped = dedupe(articles)
    print(f"  → {len(articles)} new  |  {skipped} duplicate(s) skipped")

    if not articles:
        print("\nNothing new to process today. Exiting cleanly.")
        return

    # ── 3. Enrich (Claude API) ────────────────────────────
    print(f"\n[3/5] Enriching {len(articles)} articles via Claude API...")
    from pipeline.summarise import summarise_all
    from pipeline.score import filter_by_min_score, rank_articles, score_summary
    articles = summarise_all(articles)
    articles = filter_by_min_score(articles, min_score=4)
    articles = rank_articles(articles)
    stats = score_summary(articles)
    print(f"  → {len(articles)} articles passed scoring  |  stats: {stats}")

    # ── 4. Graph (Neo4j AuraDB) ───────────────────────────
    trending: list[dict] = []
    neo4j_configured = all(
        os.environ.get(k) for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")
    )
    if neo4j_configured:
        print("\n[4/5] Writing lineage graph to Neo4j AuraDB...")
        from graph.lineage import write_all
        from graph.queries import trending_topics_this_week, rising_topics
        from graph.neo4j_client import close_driver
        try:
            write_all(articles)
            trending = trending_topics_this_week(days=7)
            rising = rising_topics()
            print(f"  → Trending: {[t['topic'] for t in trending[:5]]}")
            print(f"  → Rising:   {[t['topic'] for t in rising[:3]]}")
        except Exception as e:
            print(f"  → Neo4j error (non-fatal, skipping graph): {e}")
        finally:
            close_driver()
    else:
        print("\n[4/5] Neo4j env vars not set — skipping graph step")

    # ── 5. Email ──────────────────────────────────────────
    print("\n[5/5] Rendering and sending newsletter...")
    from email.build import render_email, send_email
    html = render_email(articles, trending_topics=trending)
    send_email(html)

    print("\n" + "=" * 50)
    print("  Pipeline complete ✓")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
