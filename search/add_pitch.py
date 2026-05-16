#!/usr/bin/env python3
"""Prepend the pitch (reveal-mode) target to the published frontier JSON, so the
page defaults to the read-along pitch. Edit search/pitch.txt (one reveal step
per line) and re-run this — no model needed."""
import json
from pathlib import Path

HERE = Path(__file__).parent
SITE = "/Users/simonsun/Desktop/Repositories/aleph/web/public/aleph-frontier.json"

segs = [l.strip() for l in (HERE / "pitch.txt").read_text().splitlines() if l.strip()]
pitch = {
    "key": "pitch",
    "label": "the Aleph pitch — read along",
    "targetTokens": 0,
    "mode": "reveal",
    "script": "\n".join(segs),
    "points": [],
}
data = json.loads(Path(SITE).read_text())
data = [t for t in data if t.get("key") != "pitch"]
data.insert(0, pitch)
Path(SITE).write_text(json.dumps(data, ensure_ascii=False, indent=2))
print(f"pitch prepended ({len(segs)} segments). targets: {[t['key'] for t in data]}")
