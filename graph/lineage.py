"""
Write articles and their relationships into the Neo4j lineage graph.

Schema
------
Nodes   : Article, Entity, Topic, Source
Edges   : (Article)-[:FROM]->(Source)
          (Article)-[:TAGGED]->(Topic)
          (Article)-[:MENTIONS]->(Entity)
          (Entity)-[:CO_OCCURS_WITH {count}]-(Entity)
"""

from datetime import datetime, timezone

from graph.neo4j_client import run_query


def ensure_constraints() -> None:
    """Idempotent uniqueness constraints — safe to call on every run."""
    constraints = [
        "CREATE CONSTRAINT article_url IF NOT EXISTS FOR (a:Article) REQUIRE a.url IS UNIQUE",
        "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
        "CREATE CONSTRAINT topic_name  IF NOT EXISTS FOR (t:Topic)  REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT source_name IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE",
    ]
    for q in constraints:
        try:
            run_query(q)
        except Exception as e:
            # Constraint may already exist on older Neo4j syntax — log and continue
            print(f"[lineage] Constraint note: {e}")


def write_article(article: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    url = article.get("url", "")
    if not url:
        return

    # --- Article node ---
    run_query(
        """
        MERGE (a:Article {url: $url})
        SET a.title           = $title,
            a.one_liner       = $one_liner,
            a.summary         = $summary,
            a.relevance_score = $relevance_score,
            a.why_it_matters  = $why_it_matters,
            a.published       = $published,
            a.ingested_at     = $ingested_at,
            a.fingerprint     = $fingerprint
        """,
        {
            "url": url,
            "title": article.get("title", ""),
            "one_liner": article.get("one_liner", ""),
            "summary": article.get("summary", ""),
            "relevance_score": article.get("relevance_score", 0),
            "why_it_matters": article.get("why_it_matters", ""),
            "published": article.get("published", ""),
            "ingested_at": now,
            "fingerprint": article.get("fingerprint", ""),
        },
    )

    # --- Source → Article ---
    run_query(
        """
        MERGE (s:Source {name: $source})
        WITH s
        MATCH (a:Article {url: $url})
        MERGE (a)-[:FROM]->(s)
        """,
        {"source": article.get("source", "Unknown"), "url": url},
    )

    # --- Topic (category) → Article ---
    run_query(
        """
        MERGE (t:Topic {name: $category})
        WITH t
        MATCH (a:Article {url: $url})
        MERGE (a)-[:TAGGED]->(t)
        """,
        {"category": article.get("category", "Other"), "url": url},
    )

    # --- Entity nodes + MENTIONS ---
    entities = [e.strip() for e in article.get("entities", []) if e and e.strip()]
    for entity in entities:
        run_query(
            """
            MERGE (e:Entity {name: $name})
            WITH e
            MATCH (a:Article {url: $url})
            MERGE (a)-[:MENTIONS]->(e)
            """,
            {"name": entity, "url": url},
        )

    # --- CO_OCCURS_WITH (weighted) ---
    for i, e1 in enumerate(entities):
        for e2 in entities[i + 1 :]:
            run_query(
                """
                MATCH (e1:Entity {name: $e1}), (e2:Entity {name: $e2})
                MERGE (e1)-[r:CO_OCCURS_WITH]-(e2)
                ON CREATE SET r.count = 1
                ON MATCH  SET r.count = r.count + 1
                """,
                {"e1": e1, "e2": e2},
            )


def write_all(articles: list[dict]) -> None:
    ensure_constraints()
    errors = 0
    for article in articles:
        try:
            write_article(article)
        except Exception as e:
            errors += 1
            print(f"[lineage] Error writing {article.get('url', '?')}: {e}")
    print(f"[lineage] Wrote {len(articles) - errors}/{len(articles)} articles to graph")
