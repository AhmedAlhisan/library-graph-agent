"""Inspect data/library.json against the ontology, then load it into Neo4j.

Run from the project root:
    python scripts/load_library.py --reset
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from library_agent.db import get_driver  # noqa: E402
from library_agent.loader import validate_dataset, write_to_neo4j  # noqa: E402


def describe(item: dict) -> str:
    if "label" in item:
        return f"node {item['label']} {item['props']}"
    (fl, fk), t, (tl, tk) = item["from"], item["type"], item["to"]
    return f"rel ({fl} {fk})-[:{t}]->({tl} {tk})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(PROJECT_ROOT / "data" / "library.json"))
    parser.add_argument("--reset", action="store_true",
                        help="delete EVERYTHING in the graph before loading")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text())
    report = validate_dataset(data)

    print(f"Accepted: {len(report.nodes)} nodes, {len(report.relationships)} relationships")
    print(f"Rejected: {len(report.rejected)}")
    for item, reasons in report.rejected:
        print(f"  - {describe(item)}")
        for reason in reasons:
            print(f"      reason: {reason}")

    driver = get_driver()
    try:
        write_to_neo4j(driver, report, reset=args.reset)
    finally:
        driver.close()
    print("Loaded into Neo4j. Open http://localhost:7474 to look at it.")


if __name__ == "__main__":
    main()
