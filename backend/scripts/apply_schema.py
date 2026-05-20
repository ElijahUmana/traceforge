"""Apply Neo4j schema (constraints + indexes) from .cypher files."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SCHEMA_FILES = [
    PROJECT_ROOT / "cypher" / "constraints.cypher",
    PROJECT_ROOT / "cypher" / "indexes.cypher",
]


def parse_cypher_statements(filepath: Path) -> list[str]:
    """Parse a .cypher file into individual executable statements.

    Splits on semicolons and strips comment-only lines. Handles multi-line
    statements (e.g., CREATE VECTOR INDEX ... OPTIONS {}).
    """
    text = filepath.read_text()
    raw_parts = text.split(";")
    statements: list[str] = []
    for part in raw_parts:
        # Strip leading/trailing whitespace
        cleaned = part.strip()
        if not cleaned:
            continue
        # Remove lines that are purely comments
        lines = [
            line for line in cleaned.splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        if lines:
            statements.append("\n".join(lines))
    return statements


def apply_schema() -> None:
    """Connect to Neo4j Aura and apply all schema files."""
    uri = os.environ["NEO4J_URI"]
    username = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    print(f"Connected to Neo4j at {uri}")

    total_applied = 0
    total_skipped = 0

    for schema_file in SCHEMA_FILES:
        print(f"\n--- Applying {schema_file.name} ---")
        statements = parse_cypher_statements(schema_file)

        with driver.session(database=database) as session:
            for stmt in statements:
                preview = stmt.replace("\n", " ")[:80]
                try:
                    session.run(stmt)
                    print(f"  OK: {preview}...")
                    total_applied += 1
                except Exception as e:
                    print(f"  SKIP: {preview}... ({e})")
                    total_skipped += 1

    driver.close()
    print(f"\nSchema applied. {total_applied} succeeded, {total_skipped} skipped.")


if __name__ == "__main__":
    apply_schema()
