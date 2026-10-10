"""Quality metrics for the library graph (book, chapter 3: "Measuring Context Quality").

  Precision       Do the graph's relationships match the source?  (target >= 95%)
  Exhaustiveness  Is everything in the source also in the graph?  (target 100%)
  Freshness       How old is the data?                            (target < 24 hours)
  Coverage        Does every relationship rule in the ontology actually appear?  (target 100%)

The calculations are plain Python functions (easy to test). The read_* functions
fetch what they need from Neo4j and from the source file.
"""

import random
from collections import Counter
from datetime import datetime, timezone

from library_agent.ontology import NODE_TYPES, RELATIONSHIPS

MAX_AGE_HOURS = 24  # a library changes daily; the book uses 1 hour for production infrastructure


# ---------------------------------------------------------------------------
# The four metrics (pure Python)
# ---------------------------------------------------------------------------
def precision(graph_edges: set, source_edges: set, sample_size: int = 50, seed: int = 7) -> dict:
    """Sample edges from the graph and check each one exists in the source."""
    edges = sorted(graph_edges)
    sample = edges if len(edges) <= sample_size else random.Random(seed).sample(edges, sample_size)
    not_in_source = [e for e in sample if e not in source_edges]
    checked = len(sample)
    return {
        "score": (checked - len(not_in_source)) / checked if checked else 1.0,
        "checked": checked,
        "not_in_source": not_in_source,
    }


def exhaustiveness(source_counts: dict, graph_counts: dict) -> dict:
    """Compare how many things the source has with how many reached the graph."""
    per_label = {
        label: (graph_counts.get(label, 0), count) for label, count in source_counts.items()
    }
    total_source = sum(source_counts.values())
    total_graph = sum(min(graph_counts.get(label, 0), count) for label, count in source_counts.items())
    return {
        "score": total_graph / total_source if total_source else 1.0,
        "in_graph": total_graph,
        "in_source": total_source,
        "gaps": {label: pair for label, pair in per_label.items() if pair[0] < pair[1]},
    }


def freshness(timestamps: list, now: datetime, max_age_hours: float = MAX_AGE_HOURS) -> dict:
    """Average and oldest age in hours. A node with no timestamp counts as stale."""
    ages = [(now - datetime.fromisoformat(t)).total_seconds() / 3600 for t in timestamps if t]
    unknown = sum(1 for t in timestamps if not t)
    stale = sum(1 for a in ages if a > max_age_hours) + unknown
    return {
        "avg_hours": sum(ages) / len(ages) if ages else None,
        "oldest_hours": max(ages) if ages else None,
        "stale": stale,
        "total": len(timestamps),
    }


def coverage(rules_in_graph: set) -> dict:
    """Which of the ontology's relationship rules actually appear in the graph?"""
    present = RELATIONSHIPS & rules_in_graph
    return {
        "score": len(present) / len(RELATIONSHIPS),
        "present": len(present),
        "defined": len(RELATIONSHIPS),
        "missing": sorted(RELATIONSHIPS - rules_in_graph),
    }


# ---------------------------------------------------------------------------
# Reading the source file (what reality says)
# ---------------------------------------------------------------------------
def key_of(label: str, props: dict):
    return props.get(NODE_TYPES[label]["key"])


def source_edges(data: dict) -> set:
    return {(r["from"][0], r["from"][1], r["type"], r["to"][0], r["to"][1]) for r in data["relationships"]}


def source_counts(data: dict) -> dict:
    """Things the source has, for node types inside our ontology (Magazine is out of scope)."""
    return dict(Counter(n["label"] for n in data["nodes"] if n["label"] in NODE_TYPES))


# ---------------------------------------------------------------------------
# Reading the graph (what the agent sees)
# ---------------------------------------------------------------------------
def read_graph(driver) -> dict:
    labels = list(NODE_TYPES)
    with driver.session() as session:
        rows = session.run(
            """
            MATCH (a)-[r]->(b)
            WHERE labels(a)[0] IN $labels AND labels(b)[0] IN $labels
            RETURN labels(a)[0] AS fl, properties(a) AS fp, type(r) AS t,
                   labels(b)[0] AS tl, properties(b) AS tp
            """,
            labels=labels,
        ).data()
        counts = {
            r["label"]: r["n"]
            for r in session.run(
                "MATCH (n) WHERE labels(n)[0] IN $labels RETURN labels(n)[0] AS label, count(*) AS n",
                labels=labels,
            ).data()
        }
        stamps = [
            r["t"] for r in session.run(
                "MATCH (n) WHERE labels(n)[0] IN $labels RETURN n.loaded_at AS t", labels=labels
            ).data()
        ]
        claims = Counter(
            r["verdict"] for r in session.run(
                """
                MATCH (s1:Subject_Book)-[:SEQUEL_OF]->(s2:Subject_Book)
                OPTIONAL MATCH (s1)-[:CORRESPONDS_TO]->(b1:Book)
                OPTIONAL MATCH (s2)-[:CORRESPONDS_TO]->(b2:Book)
                RETURN CASE
                  WHEN b1 IS NULL OR b2 IS NULL THEN 'new'
                  WHEN EXISTS { (b1)-[:SEQUEL_OF]->(b2) } THEN 'confirmed'
                  ELSE 'conflict'
                END AS verdict
                """
            ).data()
        )
    edges = {(r["fl"], key_of(r["fl"], r["fp"]), r["t"], r["tl"], key_of(r["tl"], r["tp"])) for r in rows}
    rules = {(r["fl"], r["t"], r["tl"]) for r in rows}
    return {"edges": edges, "rules": rules, "counts": counts, "stamps": stamps, "claims": dict(claims)}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
