"""Quality metric tests. No Neo4j needed."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from library_agent.ontology import RELATIONSHIPS
from library_agent.quality import coverage, exhaustiveness, freshness, precision, source_counts, source_edges

DATA = json.loads((Path(__file__).resolve().parent.parent / "data" / "library.json").read_text())


def test_precision_flags_edges_missing_from_the_source():
    real = ("Member", "M001", "HAS_LOAN", "Loan", "L001")
    drift = ("Member", "M003", "HAS_LOAN", "Loan", "L001")
    result = precision({real, drift}, {real})
    assert result["score"] == 0.5
    assert result["not_in_source"] == [drift]


def test_exhaustiveness_finds_the_rejected_member():
    result = exhaustiveness(source_counts(DATA), {"Member": 3, "Book": 5, "Author": 2, "Genre": 3,
                                                  "Branch": 2, "Loan": 6, "AvailabilityStatement": 2,
                                                  "Perspective": 4})
    assert (result["in_graph"], result["in_source"]) == (27, 28)
    assert result["gaps"] == {"Member": (3, 4)}


def test_out_of_scope_types_are_not_counted():
    assert "Magazine" not in source_counts(DATA)


def test_freshness_counts_old_and_missing_timestamps_as_stale():
    now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).isoformat()
    old = (now - timedelta(hours=30)).isoformat()
    result = freshness([fresh, old, None], now)
    assert result["stale"] == 2
    assert round(result["oldest_hours"]) == 30


def test_coverage_reports_missing_rules():
    present = RELATIONSHIPS - {("AvailabilityStatement", "ABOUT", "Book")}
    result = coverage(present)
    assert result["present"] == 7
    assert result["missing"] == [("AvailabilityStatement", "ABOUT", "Book")]


def test_source_edges_include_every_relationship_in_the_file():
    assert len(source_edges(DATA)) == 39
