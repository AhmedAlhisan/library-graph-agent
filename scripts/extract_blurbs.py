"""Read the book blurbs, let the LLM extract sequels, check them
against the ontology, and write the lexical + subject graphs to Neo4j.

Run from the project root (Ollama must be running):
    python scripts/extract_blurbs.py --dry-run   # LLM + checks only, no database
    python scripts/extract_blurbs.py             # also write to Neo4j
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from library_agent.extraction import (  # noqa: E402
    build_prompt,
    parse_llm_output,
    split_into_chunks,
    validate_triples,
    write_extraction,
)
from library_agent.llm import ask, model_name  # noqa: E402


def show(t) -> str:
    return f"({t.subject})-[:{t.predicate}]->({t.object})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(PROJECT_ROOT / "data" / "blurbs.txt"))
    parser.add_argument("--dry-run", action="store_true", help="do not write to Neo4j")
    args = parser.parse_args()

    path = Path(args.data)
    chunks = split_into_chunks(path.read_text())
    print(f"Model: {model_name()} | {len(chunks)} chunks from {path.name}\n")

    results, n_ok, n_bad, n_failed = [], 0, 0, 0
    for i, chunk in enumerate(chunks):
        chunk_id = f"{path.stem}-{i}"
        print(f"--- {chunk_id} ---")
        print(f"TEXT: {chunk}")
        started = time.time()
        raw = ask(build_prompt(chunk))
        try:
            triples = parse_llm_output(raw)
        except ValueError as exc:
            print(f"  !! could not read the LLM answer: {exc}\n")
            n_failed += 1
            results.append({"chunk_id": chunk_id, "index": i, "text": chunk, "accepted": []})
            continue

        accepted, rejected = validate_triples(triples)
        for t in accepted:
            print(f"  ACCEPTED  {show(t)}")
        for t, reasons in rejected:
            print(f"  REJECTED  {show(t)}  <- {'; '.join(reasons)}")
        if not triples:
            print("  (no facts extracted)")
        print(f"  [{time.time() - started:.1f}s]\n")

        n_ok, n_bad = n_ok + len(accepted), n_bad + len(rejected)
        results.append({"chunk_id": chunk_id, "index": i, "text": chunk, "accepted": accepted})

    print(f"Summary: {n_ok} accepted, {n_bad} rejected, {n_failed} chunks unreadable")

    if args.dry_run:
        print("Dry run: nothing written to Neo4j.")
        return

    from library_agent.db import get_driver  # only needed when writing

    driver = get_driver()
    try:
        write_extraction(driver, path.stem, results, model_name())
    finally:
        driver.close()
    print("Written: lexical graph (Document, Chunk) + subject graph (Subject_Book).")
    print("Domain graph (Book, Member, ...) was not touched.")


if __name__ == "__main__":
    main()
