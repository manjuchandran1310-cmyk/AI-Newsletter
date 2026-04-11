"""
Singleton Neo4j driver for AuraDB.

Reads connection details from environment variables:
  NEO4J_URI      — bolt+s:// or neo4j+s:// URI from the AuraDB console
  NEO4J_USER     — usually "neo4j"
  NEO4J_PASSWORD — generated on instance creation
"""

import os
from neo4j import GraphDatabase, Driver

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        uri = os.environ["NEO4J_URI"]
        user = os.environ["NEO4J_USER"]
        password = os.environ["NEO4J_PASSWORD"]
        _driver = GraphDatabase.driver(uri, auth=(user, password))
        _driver.verify_connectivity()
        print("[neo4j] Connected to AuraDB")
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        print("[neo4j] Connection closed")


def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return all records as plain dicts."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(cypher, params or {})
        return [record.data() for record in result]
