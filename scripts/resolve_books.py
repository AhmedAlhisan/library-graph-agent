"""Link the LLM's books (Subject_Book) to the official books (Book).

Run from the project root, after load_library.py and extract_blurbs.py:
    python scripts/resolve_books.py --dry-run   # show the matches only
    python scripts/resolve_books.py             # also write CORRESPONDS_TO
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from library_agent.db import get_driver  # noqa: E402
from library_agent.resolution import (  # noqa: E402
    THRESHOLD,
    linking_metrics,
    normalize,
    read_inputs,
    resolve,
    write_resolution,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="do not write to Neo4j")
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    args = parser.parse_args()

    driver = get_driver()
    try:
        names, books = read_inputs(driver)
        matches = resolve(names, books, args.threshold)

        print(f"Threshold: {args.threshold} | {len(names)} subject books, {len(books)} official books\n")
        print(f"{'LLM wrote':<26}{'normalized':<22}{'status':<11}{'score':<7}official book")
        print("-" * 90)
        for m in matches:
            official = f"{m.title} ({m.isbn})" if m.isbn else "-"
            print(f"{m.subject:<26}{normalize(m.subject):<22}{m.status:<11}{m.score:<7}{official}")

        metrics = linking_metrics(matches)
        print("\nLinking quality (book targets in brackets):")
        print(f"  linking rate    {metrics['linking_rate']:.0%}   [> 75%]")
        print(f"  avg confidence  {metrics['avg_confidence']}    [> 0.85]")
        print(f"  ambiguous       {metrics['ambiguous_rate']:.0%}    [< 5%]")

        if args.dry_run:
            print("\nDry run: nothing written to Neo4j.")
            return
        write_resolution(driver, matches)
        print("\nWritten: CORRESPONDS_TO links from Subject_Book to Book.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
