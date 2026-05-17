#!/usr/bin/env python3
"""Publish a raw frontier JSON as a monotone L̂ frontier.

L̂ is a *best known upper bound*: more search can only improve it, never
regress it. So by default this UNIONS the new run's points with whatever is
already published (per target) before taking the monotone lower envelope —
a worse run can never lose a better prior result. `--no-merge` to override.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from aleph_search import monotone  # noqa: E402

SITE = "/Users/simonsun/Desktop/Repositories/aleph/web/public/aleph-frontier.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(Path(__file__).parent / "frontier.json"))
    ap.add_argument("--out", default=SITE)
    ap.add_argument("--no-merge", action="store_true",
                    help="ignore existing output (do not union with prior runs)")
    a = ap.parse_args()

    incoming = json.loads(Path(a.inp).read_text())
    new_by_key = {t["key"]: t for t in incoming}
    outp = Path(a.out)

    prior = []
    if not a.no_merge and outp.exists():
        try:
            prior = json.loads(outp.read_text())
        except Exception:
            prior = []

    # Additive + never-regress: start from the prior published list (keep ALL
    # prior targets and order), union new points per key, append new-only keys.
    # A partial input never drops other targets; more search only improves L̂.
    result, seen = [], set()
    for t in prior:
        seen.add(t["key"])
        nt = new_by_key.get(t["key"])
        if nt and nt.get("points"):
            merged = {**t, **nt}
            merged["points"] = monotone(list(nt["points"]) + list(t.get("points", [])))
            result.append(merged)
        else:
            if t.get("points"):
                t["points"] = monotone(t["points"])
            result.append(t)
    for t in incoming:
        if t["key"] not in seen:
            t["points"] = monotone(t["points"])
            result.append(t)

    outp.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    mode = "fresh (--no-merge)" if a.no_merge else "additive · union with prior"
    print(f"finalized → {len(result)} target(s) [{mode}] -> {a.out}")
    for t in result:
        eps = [round(p["epsilon"], 3) for p in t["points"]]
        ln = [p["length"] for p in t["points"]]
        print(f"  {t['key']:<11} pts={len(t['points'])}  len={ln}  eps={eps}")


if __name__ == "__main__":
    main()
