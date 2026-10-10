"""The inspector: load library.json into Neo4j, but only what follows the rules.

Two steps, kept separate on purpose:
  1. validate_dataset  -> checks every node and relationship against the
                          ontology. Pure Python, no database, easy to test.
  2. write_to_neo4j    -> writes only what passed step 1.

Nothing reaches the graph without passing the ontology first.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from library_agent.ontology import NODE_TYPES, validate_node, validate_relationship


@dataclass
class ValidationReport:
    nodes: list = field(default_factory=list)          # accepted nodes
    relationships: list = field(default_factory=list)  # accepted relationships
    rejected: list = field(default_factory=list)       # (item, [reasons])


# ---------------------------------------------------------------------------
# Step 1: inspect (no database)
# ---------------------------------------------------------------------------
def validate_dataset(data: dict) -> ValidationReport:
    report = ValidationReport()
    known = set()  # (label, key value) of every accepted node, e.g. ("Book", "978-0001")

    # 1a. Nodes: does each one follow its node type?
    for node in data["nodes"]:
        label, props = node["label"], node["props"]
        errors = validate_node(label, props)
        if errors:
            report.rejected.append((node, errors))
            continue
        report.nodes.append(node)
        key = NODE_TYPES[label]["key"]
        known.add((label, props[key]))

    # 1b. Relationships: is the rule allowed, and do both ends exist?
    for rel in data["relationships"]:
        (from_label, from_key), rel_type, (to_label, to_key) = rel["from"], rel["type"], rel["to"]
        errors = validate_relationship(from_label, rel_type, to_label)
        if not errors:
            for label, key_value in ((from_label, from_key), (to_label, to_key)):
                if (label, key_value) not in known:
                    errors.append(f"Endpoint not found: {label} {key_value}")
        if errors:
            report.rejected.append((rel, errors))
            continue
        report.relationships.append(rel)

    return report


# ---------------------------------------------------------------------------
# Step 2: write (only what passed)
# ---------------------------------------------------------------------------
# Safety note: Cypher cannot take a label or relationship type as a
# $parameter, so they go into the query text. That is safe ONLY because
# each one already passed the ontology whitelist above (like protecting
# against SQL injection). Values (names, ids, titles) always go in as
# $parameters.

def write_to_neo4j(driver, report: ValidationReport, reset: bool = False) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")  # for the freshness metric
    with driver.session() as session:
        if reset:
            session.run("MATCH (n) DETACH DELETE n").consume()

        # One uniqueness constraint per node type: the graph's "primary key"
        for label, spec in NODE_TYPES.items():
            key = spec["key"]
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_{key}_unique IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
            ).consume()

        # Nodes: MERGE = create if missing, reuse if it already exists.
        # loaded_at records when this node was last refreshed from the source.
        for node in report.nodes:
            label, props = node["label"], node["props"]
            key = NODE_TYPES[label]["key"]
            session.run(
                f"MERGE (n:{label} {{{key}: $key_value}}) SET n += $props, n.loaded_at = $now",
                key_value=props[key],
                props=props,
                now=now,
            ).consume()

        # Relationships: find both ends by their key, then MERGE the arrow
        for rel in report.relationships:
            (from_label, from_key), rel_type, (to_label, to_key) = rel["from"], rel["type"], rel["to"]
            fk = NODE_TYPES[from_label]["key"]
            tk = NODE_TYPES[to_label]["key"]
            session.run(
                f"MATCH (a:{from_label} {{{fk}: $from_key}}), (b:{to_label} {{{tk}: $to_key}}) "
                f"MERGE (a)-[:{rel_type}]->(b)",
                from_key=from_key,
                to_key=to_key,
            ).consume()
