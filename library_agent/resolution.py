"""Entity resolution: link what the LLM wrote (Subject_Book) to the
official books (Book) with CORRESPONDS_TO.

The book's three-stage linking pipeline (chapter 3), applied to titles:
  1. Property key correlation  -> Subject_Book.name is compared with Book.title
  2. Value similarity matching -> normalize both titles, then Jaro-Winkler (0.0-1.0)
  3. Validation                -> volume numbers must match ("Desert Star 1" is
                                  NOT "Desert Star 2", even though they look alike)

A subject is "linked" when exactly one book passes, "ambiguous" when two books
pass with almost the same score, and "unmatched" when none pass (a possible
new book: a gap in the catalog).
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from rapidfuzz.distance import JaroWinkler

THRESHOLD = 0.85        # the book's recommended default (0.95 high-stakes, 0.75 exploratory)
AMBIGUITY_GAP = 0.02    # two candidates closer than this = we cannot choose safely


# ---------------------------------------------------------------------------
# Stage 2: make titles comparable, then score them
# ---------------------------------------------------------------------------
def normalize(title: str) -> str:
    """'  The Desert Star 2 (2nd ed.)!' -> 'desert star 2'"""
    t = title.lower()
    t = re.sub(r"\(.*?\)", " ", t)       # drop anything in parentheses
    t = re.sub(r"[^a-z0-9\s]", " ", t)   # drop punctuation
    t = re.sub(r"\s+", " ", t).strip()   # collapse spaces
    t = re.sub(r"^the ", "", t)          # drop a leading "the"
    return t


def similarity(a: str, b: str) -> float:
    """Jaro-Winkler similarity of the normalized titles: 1.0 = identical."""
    return JaroWinkler.similarity(normalize(a), normalize(b))


# ---------------------------------------------------------------------------
# Stage 3: validation that string similarity alone gets wrong
# ---------------------------------------------------------------------------
def same_volume_numbers(a: str, b: str) -> bool:
    """'desert star 2' vs 'desert star 1' look 97% alike, but are different books."""
    return re.findall(r"\d+", normalize(a)) == re.findall(r"\d+", normalize(b))


# ---------------------------------------------------------------------------
# Resolve every subject name against the official books
# ---------------------------------------------------------------------------
@dataclass
class Match:
    subject: str
    status: str                 # "linked", "ambiguous" or "unmatched"
    isbn: str | None = None
    title: str | None = None
    score: float = 0.0          # best score found (for unmatched: how close it got)


def resolve(subject_names: list[str], books: dict[str, str],
            threshold: float = THRESHOLD) -> list[Match]:
    """books: {isbn: title} from the domain graph."""
    matches = []
    for name in subject_names:
        candidates = sorted(
            (
                (similarity(name, title), isbn, title)
                for isbn, title in books.items()
                if same_volume_numbers(name, title)
            ),
            reverse=True,
        )
        passing = [c for c in candidates if c[0] >= threshold]
        best = candidates[0][0] if candidates else 0.0

        if not passing:
            matches.append(Match(name, "unmatched", score=round(best, 3)))
        elif len(passing) > 1 and passing[0][0] - passing[1][0] < AMBIGUITY_GAP:
            matches.append(Match(name, "ambiguous", score=round(passing[0][0], 3)))
        else:
            score, isbn, title = passing[0]
            matches.append(Match(name, "linked", isbn, title, round(score, 3)))
    return matches


def linking_metrics(matches: list[Match]) -> dict:
    """The book's targets: linking rate > 75%, avg confidence > 0.85, ambiguous < 5%."""
    total = len(matches) or 1
    linked = [m for m in matches if m.status == "linked"]
    return {
        "linking_rate": round(len(linked) / total, 3),
        "avg_confidence": round(sum(m.score for m in linked) / len(linked), 3) if linked else 0.0,
        "ambiguous_rate": round(sum(m.status == "ambiguous" for m in matches) / total, 3),
    }


# ---------------------------------------------------------------------------
# Neo4j: read both sides, write the links
# ---------------------------------------------------------------------------
def read_inputs(driver) -> tuple[list[str], dict[str, str]]:
    with driver.session() as session:
        names = [r["name"] for r in session.run("MATCH (s:Subject_Book) RETURN s.name AS name ORDER BY name")]
        books = {r["isbn"]: r["title"] for r in session.run("MATCH (b:Book) RETURN b.isbn AS isbn, b.title AS title")}
    return names, books


def write_resolution(driver, matches: list[Match]) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with driver.session() as session:
        # Re-running starts clean: old links are removed, nothing else is touched
        session.run("MATCH (:Subject_Book)-[c:CORRESPONDS_TO]->(:Book) DELETE c").consume()
        for m in matches:
            session.run(
                "MATCH (s:Subject_Book {name: $name}) SET s.resolution = $status, s.best_score = $score",
                name=m.subject, status=m.status, score=m.score,
            ).consume()
            if m.status == "linked":
                session.run(
                    """
                    MATCH (s:Subject_Book {name: $name}), (b:Book {isbn: $isbn})
                    MERGE (s)-[c:CORRESPONDS_TO]->(b)
                    SET c.score = $score, c.method = 'jaro_winkler', c.resolved_at = $now
                    """,
                    name=m.subject, isbn=m.isbn, score=m.score, now=now,
                ).consume()
