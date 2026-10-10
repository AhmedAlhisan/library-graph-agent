"""Entity resolution tests. No Neo4j needed."""

from library_agent.resolution import (
    linking_metrics,
    normalize,
    resolve,
    same_volume_numbers,
    similarity,
)

BOOKS = {
    "978-0001": "The Desert Star 1",
    "978-0002": "The Desert Star 2",
    "978-0003": "The Desert Star 3",
    "978-0004": "Riyadh Nights",
    "978-0005": "Code of the Dunes",
}


def test_normalize_removes_case_the_punctuation_and_parentheses():
    assert normalize("  The Desert Star 2 (2nd ed.)!") == "desert star 2"
    assert normalize("Desert Star 2") == "desert star 2"


def test_normalization_is_what_makes_the_match():
    # Raw strings score 0.79 (below 0.85); normalized they are identical
    from rapidfuzz.distance import JaroWinkler
    assert JaroWinkler.similarity("Desert Star 2", "The Desert Star 2") < 0.85
    assert similarity("Desert Star 2", "The Desert Star 2") == 1.0


def test_jaro_winkler_tolerates_typos():
    assert similarity("The Dessert Star 3", "The Desert Star 3") > 0.85


def test_similar_titles_with_different_numbers_are_different_books():
    assert similarity("Desert Star 2", "The Desert Star 1") > 0.95   # looks alike...
    assert not same_volume_numbers("Desert Star 2", "The Desert Star 1")  # ...but isn't


def test_resolve_links_both_spellings_to_the_same_book():
    matches = {m.subject: m for m in resolve(["Desert Star 2", "The Desert Star 2"], BOOKS)}
    assert matches["Desert Star 2"].isbn == "978-0002"
    assert matches["The Desert Star 2"].isbn == "978-0002"


def test_new_book_is_unmatched():
    [m] = resolve(["Dunes Reborn"], BOOKS)
    assert m.status == "unmatched"
    assert m.isbn is None


def test_two_equally_good_candidates_are_ambiguous():
    twins = {"111": "Desert Star", "222": "Desert Stars"}
    [m] = resolve(["Desert Star."], twins, threshold=0.85)
    assert m.status == "ambiguous"


def test_full_library_resolution():
    llm_names = ["Code of the Dunes", "Desert Star 2", "Dunes Reborn",
                 "The Desert Star 1", "The Desert Star 2", "The Desert Star 3"]
    matches = resolve(llm_names, BOOKS)
    linked = {m.subject: m.isbn for m in matches if m.status == "linked"}
    assert linked == {
        "Code of the Dunes": "978-0005",
        "Desert Star 2": "978-0002",
        "The Desert Star 1": "978-0001",
        "The Desert Star 2": "978-0002",
        "The Desert Star 3": "978-0003",
    }
    metrics = linking_metrics(matches)
    assert metrics["linking_rate"] == round(5 / 6, 3)
    assert metrics["ambiguous_rate"] == 0.0
