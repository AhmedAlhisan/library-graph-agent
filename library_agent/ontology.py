"""Library ontology: the rulebook for the library graph.

Derived from design.md. Anything not listed here is rejected
before it reaches Neo4j.
"""

# ---------------------------------------------------------------------------
# Node types (design.md, section 4)
# ---------------------------------------------------------------------------
# key      -> the property that identifies a node uniquely (like a primary key)
# required -> properties a node must have for our questions to work
NODE_TYPES: dict[str, dict] = {
    "Book": {"key": "isbn", "required": ["isbn", "title"]},
    "Author": {"key": "name", "required": ["name"]},
    "Genre": {"key": "name", "required": ["name"]},
    "Member": {"key": "member_id", "required": ["member_id", "name"]},
    # Contextual boundary: where a loan happened
    "Branch": {"key": "name", "required": ["name"]},
    # Event-centric: a borrowing has its own details and can repeat
    "Loan": {"key": "loan_id", "required": ["loan_id", "status"]},
    # Multiperspective: two systems may report different available copies
    "AvailabilityStatement": {"key": "statement_id", "required": ["statement_id"]},
    "Perspective": {"key": "perspective_id", "required": ["perspective_id", "source", "value"]},
}

# ---------------------------------------------------------------------------
# Relationships (design.md, section 5)
# ---------------------------------------------------------------------------
# Each rule is (from_label, relationship_type, to_label). Direction matters.
RELATIONSHIPS: set[tuple[str, str, str]] = {
    ("Author", "WROTE", "Book"),
    ("Book", "IN_GENRE", "Genre"),
    ("Book", "SEQUEL_OF", "Book"),
    ("Member", "HAS_LOAN", "Loan"),
    ("Loan", "FOR_BOOK", "Book"),
    ("Loan", "AT_BRANCH", "Branch"),
    ("AvailabilityStatement", "ABOUT", "Book"),
    ("AvailabilityStatement", "ACCORDING_TO", "Perspective"),
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_node(label: str, properties: dict) -> list[str]:
    """Check one node. An empty list means it is valid."""
    if label not in NODE_TYPES:
        return [f"Unknown node type: {label}"]

    errors = []
    for prop in NODE_TYPES[label]["required"]:
        if properties.get(prop) in (None, ""):
            errors.append(f"{label} is missing required property '{prop}'")
    return errors


def validate_relationship(from_label: str, rel_type: str, to_label: str) -> list[str]:
    """Check one relationship. An empty list means it is valid."""
    if from_label not in NODE_TYPES:
        return [f"Unknown node type: {from_label}"]
    if to_label not in NODE_TYPES:
        return [f"Unknown node type: {to_label}"]
    if (from_label, rel_type, to_label) not in RELATIONSHIPS:
        return [f"Relationship not allowed: ({from_label})-[:{rel_type}]->({to_label})"]
    return []