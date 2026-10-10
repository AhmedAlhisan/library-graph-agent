"""Measure the library graph's quality: precision, exhaustiveness, freshness, coverage.

Run from the project root:
    python scripts/quality_report.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from library_agent.db import get_driver  # noqa: E402
from library_agent.quality import (  # noqa: E402
    MAX_AGE_HOURS,
    coverage,
    exhaustiveness,
    freshness,
    now_utc,
    precision,
    read_graph,
    source_counts,
    source_edges,
)


def verdict(ok: bool) -> str:
    return "OK" if ok else "ALERT"


def main() -> None:
    source = json.loads((PROJECT_ROOT / "data" / "library.json").read_text())
    driver = get_driver()
    try:
        graph = read_graph(driver)
    finally:
        driver.close()

    p = precision(graph["edges"], source_edges(source))
    e = exhaustiveness(source_counts(source), graph["counts"])
    f = freshness(graph["stamps"], now_utc())
    c = coverage(graph["rules"])
    claims = graph["claims"]

    print(f"Knowledge graph quality report ({now_utc():%Y-%m-%d %H:%M} UTC)\n")

    print(f"1. Precision       {p['score']:6.1%}  {p['checked']} edges checked against the source"
          f"   [target >= 95%]  {verdict(p['score'] >= 0.95)}")
    for edge in p["not_in_source"]:
        fl, fk, t, tl, tk = edge
        print(f"     not in source: ({fl} {fk})-[:{t}]->({tl} {tk})")
    resolvable = claims.get("confirmed", 0) + claims.get("conflict", 0)
    if resolvable:
        print(f"   LLM claims      {claims.get('confirmed', 0) / resolvable:6.1%}  "
              f"{claims.get('confirmed', 0)}/{resolvable} confirmed, {claims.get('new', 0)} new (not checkable)")

    print(f"\n2. Exhaustiveness  {e['score']:6.1%}  {e['in_graph']}/{e['in_source']} source items reached the graph"
          f"   [target 100%]  {verdict(e['score'] == 1.0)}")
    for label, (in_graph, in_source) in e["gaps"].items():
        print(f"     gap: {label} {in_graph}/{in_source}")

    if f["avg_hours"] is None:
        print(f"\n3. Freshness       no timestamps   [target < {MAX_AGE_HOURS} h]  ALERT")
    else:
        print(f"\n3. Freshness       avg {f['avg_hours']:.1f} h, oldest {f['oldest_hours']:.1f} h, "
              f"{f['stale']}/{f['total']} stale   [target < {MAX_AGE_HOURS} h]  {verdict(f['stale'] == 0)}")

    print(f"\n4. Coverage        {c['score']:6.1%}  {c['present']}/{c['defined']} relationship rules appear"
          f"   [target 100%]  {verdict(c['score'] == 1.0)}")
    for fl, t, tl in c["missing"]:
        print(f"     missing: ({fl})-[:{t}]->({tl})")


if __name__ == "__main__":
    main()
