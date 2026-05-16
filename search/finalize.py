#!/usr/bin/env python3
"""Clean a raw frontier JSON into a monotone L̂ frontier and publish it to the
site's public/ (no model needed — pure post-processing, so we can refresh the
demo data without re-running the slow search)."""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aleph_search import monotone  # noqa: E402

SITE = "/Users/simonsun/Desktop/Repositories/aleph/web/public/aleph-frontier.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(Path(__file__).parent / "frontier.json"))
    ap.add_argument("--out", default=SITE)
    a = ap.parse_args()
    data = json.loads(Path(a.inp).read_text())
    for t in data:
        t["points"] = monotone(t["points"])
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"finalized {len(data)} target(s) -> {a.out}")
    for t in data:
        eps = [round(p["epsilon"], 3) for p in t["points"]]
        ln = [p["length"] for p in t["points"]]
        print(f"  {t['key']:<11} pts={len(t['points'])}  len={ln}  eps={eps}")


if __name__ == "__main__":
    main()
