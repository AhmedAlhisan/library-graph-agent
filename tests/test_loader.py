"""Milestone 3 acceptance tests: the inspector. No Neo4j needed."""

import json
from pathlib import Path

from library_agent.loader import validate_dataset

DATA = Path(__file__).resolve().parent.parent / "data" / "library.json"

SARA = {"label": "Member", "props": {"member_id": "M001", "name": "Sara"}}
LOAN = {"label": "Loan", "props": {"loan_id": "L001", "status": "returned"}}


def dataset(nodes, relationships):
    return {"nodes": nodes, "relationships": relationships}


def test_valid_node_and_relationship_are_accepted():
    data = dataset(
        [SARA, LOAN],
        [{"from": ["Member", "M001"], "type": "HAS_LOAN", "to": ["Loan", "L001"]}],
    )
    report = validate_dataset(data)
    assert len(report.nodes) == 2
    assert len(report.relationships) == 1
    assert report.rejected == []


def test_node_missing_property_is_rejected():
    report = validate_dataset(dataset([{"label": "Member", "props": {"member_id": "M004"}}], []))
    assert report.nodes == []
    assert report.rejected[0][1] == ["Member is missing required property 'name'"]


def test_relationship_to_missing_node_is_rejected():
    data = dataset(
        [SARA],
        [{"from": ["Member", "M001"], "type": "HAS_LOAN", "to": ["Loan", "L999"]}],
    )
    report = validate_dataset(data)
    assert report.relationships == []
    assert report.rejected[0][1] == ["Endpoint not found: Loan L999"]


def test_relationship_to_a_rejected_node_is_also_rejected():
    # M004 is rejected (no name), so an arrow from it has no valid start
    bad_member = {"label": "Member", "props": {"member_id": "M004"}}
    data = dataset(
        [bad_member, LOAN],
        [{"from": ["Member", "M004"], "type": "HAS_LOAN", "to": ["Loan", "L001"]}],
    )
    report = validate_dataset(data)
    assert report.relationships == []
    assert report.rejected[-1][1] == ["Endpoint not found: Member M004"]


def test_full_library_dataset():
    report = validate_dataset(json.loads(DATA.read_text()))
    assert len(report.nodes) == 27
    assert len(report.relationships) == 37
    reasons = sorted(r for _, rs in report.rejected for r in rs)
    assert reasons == sorted([
        "Unknown node type: Magazine",
        "Member is missing required property 'name'",
        "Relationship not allowed: (Book)-[:WROTE]->(Author)",
        "Endpoint not found: Book 978-9999",
    ])
