"""Offline replay of retained MLX smoke measurements; never loads a model.

This supplements structural bundle verification with metric/usage arithmetic.
It does not prove the model executed honestly or re-tokenize without its pinned
external tokenizer. Historical 0.1.0 bundles have no per-sample records and
remain explicitly structural-only. No scheduler or MLX runtime is imported.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters.mlx import canary_metrics
from .archive import read_bundle
from .ledger import LEGACY_LEDGER_SCHEMA_VERSION
from .verify import verify_bundle


def _tokens(value):
    if not isinstance(value, list) or any(type(v) is not int or v < 0 for v in value):
        raise ValueError("token ids must be a list of non-negative integers")
    return value


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("usage must be a non-negative integer")
    return value


def check_canary_evidence(root: Path) -> dict:
    report = verify_bundle(root)
    result = {"ok": report.ok, "errors": list(report.errors), "evaluationsReplayed": 0,
              "measurementReplay": "retained_tokens_and_usage", "bundle": report.payload()}
    if not report.ok:
        return result
    snapshot = read_bundle(root)
    if snapshot.manifest.ledger_schema_version == LEGACY_LEDGER_SCHEMA_VERSION:
        result["measurementReplay"] = "unavailable_legacy_structural_only"
        return result
    for event in snapshot.events:
        if event.event_type != "evaluation_completed":
            continue
        try:
            receipt = json.loads(snapshot.blobs[event.blob_digests[0]])
            output, usage = receipt["outputs"], receipt["resourceUse"]
            samples = output["samples"]
            if not isinstance(samples, list) or not samples:
                raise ValueError("missing nonempty retained samples")
            if any(not isinstance(s["text"], str) for s in samples):
                raise ValueError("sample text must be a string")
            expected = canary_metrics(
                target_tokens=_tokens(output["targetTokenIds"]),
                coordinate_tokens=_tokens(output["coordinateTokenIds"]),
                continuation_token_lists=[_tokens(s["tokenIds"]) for s in samples],
            )
            if expected != receipt["metrics"]:
                raise ValueError("surface metrics do not match retained token records")
            inputs = sum(_count(s["promptTokens"]) for s in samples)
            outputs = sum(_count(s["generationTokens"]) for s in samples)
            expected_usage = {"samples": len(samples), "inputTokens": inputs,
                              "outputTokens": outputs, "providerReportedTokens": inputs + outputs}
            for key, value in expected_usage.items():
                if _count(usage[key]) != value:
                    raise ValueError(f"{key} does not sum across retained samples")
            if output["text"] != samples[0]["text"].strip():
                raise ValueError("selected output differs from the first sample")
            result["evaluationsReplayed"] += 1
        except (KeyError, ValueError, TypeError, IndexError) as error:
            result["errors"].append(f"{event.event_id}: {error}")
    if not result["evaluationsReplayed"]:
        result["errors"].append("no retained canary evaluations were replayed")
    result["ok"] = not result["errors"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    result = check_canary_evidence(parser.parse_args().bundle)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
