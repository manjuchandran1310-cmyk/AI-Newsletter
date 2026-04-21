"""
Analytical Cypher queries for the lineage graph.

Used by main.py to generate the "Rising Topics" section
and to support future relevance-tuning features.
"""

from datetime import datetime, timezone, timedelta

from graph.neo4j_client import run_query


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def trending_topics_this_week(days: int = 7) -> list[dict]:
    """Topics that appeared most in the last N days."""
    return run_query(
        """
        MATCH (a:Article)-[:TAGGED]->(t:Topic)
        WHERE a.ingested_at >= $cutoff
        RETURN t.name AS topic, count(a) AS article_count
        ORDER BY article_count DESC
        LIMIT 10
        """,
        {"cutoff": _cutoff(days)},
    )


def trending_entities_this_week(days: int = 7) -> list[dict]:
    """Entities mentioned most in the last N days."""
    return run_query(
        """
        MATCH (a:Article)-[:MENTIONS]->(e:Entity)
        WHERE a.ingested_at >= $cutoff
        RETURN e.name AS entity, count(a) AS mention_count
        ORDER BY mention_count DESC
        LIMIT 15
        """,
        {"cutoff": _cutoff(days)},
    )


def rising_topics(current_days: int = 7, compare_days: int = 14) -> list[dict]:
    """
    Topics that gained momentum: compare this week vs the prior week.
    Returns topics sorted by delta (this_week - prior_week) descending.
    """
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=current_days)).isoformat()
    prior_start = (now - timedelta(days=compare_days)).isoformat()

    return run_query(
        """
        MATCH (a:Article)-[:TAGGED]->(t:Topic)
        WITH t,
             count(CASE WHEN a.ingested_at >= $week_start THEN 1 END)  AS this_week,
             count(CASE WHEN a.ingested_at >= $prior_start
                         AND a.ingested_at < $week_start  THEN 1 END) AS prior_week
        WHERE this_week > 0
        RETURN t.name  AS topic,
               this_week,
               prior_week,
               this_week - prior_week AS delta
        ORDER BY delta DESC
        LIMIT 10
        """,
        {"week_start": week_start, "prior_start": prior_start},
    )


def co_occurring_entities(entity_name: str, limit: int = 10) -> list[dict]:
    """Entities that most frequently share articles with a given entity."""
    return run_query(
        """
        MATCH (e1:Entity {name: $name})-[r:CO_OCCURS_WITH]-(e2:Entity)
        RETURN e2.name AS entity, r.count AS co_occurrences
        ORDER BY co_occurrences DESC
        LIMIT $limit
        """,
        {"name": entity_name, "limit": limit},
    )


def articles_by_topic(topic: str, days: int = 7) -> list[dict]:
    """Recent articles for a given topic, sorted by relevance score."""
    return run_query(
        """
        MATCH (a:Article)-[:TAGGED]->(t:Topic {name: $topic})
        WHERE a.ingested_at >= $cutoff
        RETURN a.title AS title, a.url AS url,
               a.relevance_score AS score, a.one_liner AS one_liner
        ORDER BY a.relevance_score DESC
        LIMIT 20
        """,
        {"topic": topic, "cutoff": _cutoff(days)},
    )


def top_articles_this_week(days: int = 7, limit: int = 10) -> list[dict]:
    """Highest-scoring articles ingested in the last N days."""
    return run_query(
        """
        MATCH (a:Article)
        WHERE a.ingested_at >= $cutoff
        RETURN a.title AS title, a.url AS url,
               a.relevance_score AS score, a.why_it_matters AS why
        ORDER BY a.relevance_score DESC
        LIMIT $limit
        """,
        {"cutoff": _cutoff(days), "limit": limit},
    )
