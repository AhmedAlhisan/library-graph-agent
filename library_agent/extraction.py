"""LLM extraction: book blurbs -> lexical graph + subject graph.

The three graphs (book, chapter 3):
  Domain graph   (:Book, :Member, ...)   trusted data from library.json
  Lexical graph  (:Document)-[:HAS_CHUNK]->(:Chunk)   the original text, never changed
  Subject graph  (:Subject_Book)-[:SEQUEL_OF]->(:Subject_Book)
                 what the LLM *thinks* the text says, linked to its chunk
                 with EXTRACTED_FROM. Kept apart from the domain graph.

Flow for every chunk:
  build_prompt -> ask the LLM -> parse_llm_output -> validate_triples -> write
"""

import json
import re
from datetime import datetime, timezone

from pydantic import BaseModel, ValidationError

from library_agent.ontology import RELATIONSHIPS, validate_relationship


# ---------------------------------------------------------------------------
# 1. Lexical graph: split the document into chunks
# ---------------------------------------------------------------------------
def split_into_chunks(text: str) -> list[str]:
    """One chunk per paragraph (paragraphs are separated by a blank line)."""
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


# ---------------------------------------------------------------------------
# 2. Prompt: the ontology tells the LLM which predicates it may use
# ---------------------------------------------------------------------------
def allowed_book_predicates() -> list[str]:
    """Relationship types the ontology allows between two books."""
    return sorted(rel for (src, rel, dst) in RELATIONSHIPS if src == "Book" and dst == "Book")


def build_prompt(chunk: str) -> str:
    predicates = ", ".join(allowed_book_predicates())
    return f"""You extract book series facts from library book descriptions.

Allowed predicates (use ONLY these): {predicates}
Meaning: (A, SEQUEL_OF, B) means book A continues the story of book B.

Rules:
- Write each book title exactly as it appears in the text.
- Only extract facts the text states. Do not guess.
- If the text has no such facts, return an empty list.

Return JSON only, in exactly this format:
{{"triples": [{{"subject": "...", "predicate": "...", "object": "..."}}]}}

Text:
\"\"\"{chunk}\"\"\"
/no_think"""


# ---------------------------------------------------------------------------
# 3. Parse: turn the LLM's raw text into checked Python objects
# ---------------------------------------------------------------------------
class Triple(BaseModel):
    subject: str
    predicate: str
    object: str


class Extraction(BaseModel):
    triples: list[Triple]


def parse_llm_output(raw: str) -> list[Triple]:
    """Small models add extra text around the JSON. Remove it, then validate.

    Raises ValueError if no valid JSON can be found.
    """
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)  # qwen3 reasoning
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in LLM output: {raw[:200]!r}")
    try:
        data = json.loads(text[start:end + 1])
        triples = Extraction.model_validate(data).triples
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"LLM output is not valid extraction JSON: {exc}") from exc
    for t in triples:  # light clean-up only: spaces and letter case
        t.subject, t.object = t.subject.strip(), t.object.strip()
        t.predicate = t.predicate.strip().upper()
    return triples


# ---------------------------------------------------------------------------
# 4. Validate: the inspector for the LLM's lane
# ---------------------------------------------------------------------------
def validate_triples(triples: list[Triple]) -> tuple[list[Triple], list[tuple[Triple, list[str]]]]:
    """Split triples into (accepted, rejected). Every triple is about two books."""
    accepted, rejected = [], []
    for t in triples:
        # Rule 1: ask the ontology
        errors = validate_relationship("Book", t.predicate, "Book")
        # Rule 2: a book cannot be a sequel of itself
        if not errors and t.subject.lower() == t.object.lower():
            errors = [f"A book cannot be a sequel of itself: {t.subject}"]
        if errors:
            rejected.append((t, errors))
        else:
            accepted.append(t)
    return accepted, rejected


# ---------------------------------------------------------------------------
# 5. Write: lexical + subject graph. The domain graph is never touched.
# ---------------------------------------------------------------------------
def write_extraction(driver, doc_name: str, results: list[dict], model: str) -> None:
    """results: one dict per chunk -> {"chunk_id", "index", "text", "accepted"}."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with driver.session() as session:
        # Re-extraction starts clean, but ONLY for lexical + subject nodes
        session.run(
            "MATCH (n) WHERE n:Document OR n:Chunk OR n:Subject_Book DETACH DELETE n"
        ).consume()
        for label, key in (("Document", "name"), ("Chunk", "chunk_id"), ("Subject_Book", "name")):
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_{key}_unique IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
            ).consume()

        session.run("MERGE (:Document {name: $name})", name=doc_name).consume()
        previous = None
        for r in results:
            # Lexical graph: the original text, exactly as received
            session.run(
                """
                MATCH (d:Document {name: $doc})
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.text = $text, c.index = $index
                MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                doc=doc_name, chunk_id=r["chunk_id"], text=r["text"], index=r["index"],
            ).consume()
            if previous:
                session.run(
                    "MATCH (a:Chunk {chunk_id: $a}), (b:Chunk {chunk_id: $b}) MERGE (a)-[:NEXT_CHUNK]->(b)",
                    a=previous, b=r["chunk_id"],
                ).consume()
            previous = r["chunk_id"]

            # Subject graph: what the LLM extracted, with provenance.
            # t.predicate is safe in the query text only because it passed
            # validate_triples (the ontology whitelist).
            for t in r["accepted"]:
                session.run(
                    f"""
                    MATCH (c:Chunk {{chunk_id: $chunk_id}})
                    MERGE (a:Subject_Book {{name: $subject}})
                    MERGE (b:Subject_Book {{name: $object}})
                    MERGE (a)-[rel:{t.predicate}]->(b)
                    SET rel.chunk_id = $chunk_id, rel.model = $model, rel.extracted_at = $now
                    MERGE (a)-[:EXTRACTED_FROM]->(c)
                    MERGE (b)-[:EXTRACTED_FROM]->(c)
                    """,
                    chunk_id=r["chunk_id"], subject=t.subject, object=t.object,
                    model=model, now=now,
                ).consume()
