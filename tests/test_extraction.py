"""Milestone 5 tests: LLM extraction. No LLM and no Neo4j needed:
we feed in text that looks like what qwen3 returns."""

import pytest

from library_agent.extraction import (
    Triple,
    build_prompt,
    parse_llm_output,
    split_into_chunks,
    validate_triples,
)


def t(subject, predicate, obj):
    return Triple(subject=subject, predicate=predicate, object=obj)


def test_split_into_chunks_one_per_paragraph():
    text = "First paragraph.\n\nSecond paragraph.\n\n\n  Third one.  \n"
    assert split_into_chunks(text) == ["First paragraph.", "Second paragraph.", "Third one."]


def test_prompt_uses_ontology_predicates_and_the_text():
    prompt = build_prompt("Book 2 continues Book 1.")
    assert "SEQUEL_OF" in prompt
    assert "Book 2 continues Book 1." in prompt


def test_parse_clean_json():
    raw = '{"triples": [{"subject": "The Desert Star 2", "predicate": "SEQUEL_OF", "object": "The Desert Star 1"}]}'
    assert parse_llm_output(raw) == [t("The Desert Star 2", "SEQUEL_OF", "The Desert Star 1")]


def test_parse_removes_think_block_and_code_fence():
    raw = (
        "<think>\nLooking for sequels...\n</think>\n"
        "```json\n"
        '{"triples": [{"subject": " Dunes Reborn ", "predicate": "sequel_of", "object": "Code of the Dunes"}]}\n'
        "```"
    )
    assert parse_llm_output(raw) == [t("Dunes Reborn", "SEQUEL_OF", "Code of the Dunes")]


def test_parse_garbage_raises_value_error():
    with pytest.raises(ValueError):
        parse_llm_output("Sorry, I cannot help with that.")


def test_valid_sequel_is_accepted():
    accepted, rejected = validate_triples([t("The Desert Star 2", "SEQUEL_OF", "The Desert Star 1")])
    assert accepted == [t("The Desert Star 2", "SEQUEL_OF", "The Desert Star 1")]
    assert rejected == []


def test_predicate_not_in_ontology_is_rejected():
    accepted, rejected = validate_triples([t("Khalid Al-Otaibi", "WROTE", "Riyadh Nights")])
    assert accepted == []
    assert rejected[0][1] == ["Relationship not allowed: (Book)-[:WROTE]->(Book)"]


def test_book_cannot_be_its_own_sequel():
    accepted, rejected = validate_triples([t("Riyadh Nights", "SEQUEL_OF", "riyadh nights")])
    assert accepted == []
    assert rejected[0][1] == ["A book cannot be a sequel of itself: Riyadh Nights"]


def test_wrong_fact_with_right_shape_is_still_accepted():
    # "Readers who enjoyed X will love Y" is NOT a sequel. The shape is valid,
    # so the ontology cannot catch it. Shape is guaranteed, truth is not.
    wrong = t("Riyadh Nights", "SEQUEL_OF", "The Desert Star 1")
    accepted, _ = validate_triples([wrong])
    assert accepted == [wrong]
