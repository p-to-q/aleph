"""Frontier receipts: digests, artifact<->receipt linkage, and selection mirrors."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROOT = Path(__file__).resolve().parents[1]
for candidate in (str(REPO_ROOT), str(SEARCH_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from search.engine.canonical import digest  # noqa: E402
from search.frontier_receipts import (  # noqa: E402
    SCHEMA_VERSION,
    annotate_consistency,
    compute_counts,
    expected_max_tokens,
    observation_fields,
    procedure_block,
    reuse_conflict,
    selection_status,
    stability_scalar,
    target_texts,
    verify_payloads,
    with_digest,
)
from aleph_search import observed_length_distortion_frontier  # noqa: E402


def observation(prompt: str, length: int, epsilon: float) -> dict:
    return {
        "epsilon": epsilon,
        "prompt": prompt,
        "similarity": round(1.0 - epsilon, 4),
        "stability": 0.9,
        "length": length,
        "output": f"output for {prompt}",
        "toktext": ["a", "b"],
        "toknll": [0.5, 1.5],
    }


def receipt_for(target: str, obs: dict, status: str = "displayed") -> dict:
    receipt = {
        "target": target,
        "targetDigest": digest(f"target text of {target}"),
        "promptDigest": digest(obs["prompt"]),
        "model": {"repo": "test/repo", "revision": "abc123", "weightsDigest": digest("weights")},
        "metric": {"fit": {"kind": "test"}, "trace": {"kind": "test"}},
        "procedure": {"entrypoint": "test", "generation": {"temperature": 0.0}},
        "measuredAt": "2026-10-15T00:00:00Z",
        "supersedes": {
            "epsilon": 0.5,
            "similarity": 0.5,
            "stability": 0.5,
            "length": obs["length"],
            "outputIdentical": True,
        },
        "measurement": {"generationSeconds": 1.0},
        "status": status,
    }
    receipt.update(obs)
    receipt["outputDigest"] = digest(obs["output"])
    return with_digest(receipt)


def point_from(obs: dict, role: str | None = None) -> dict:
    point = dict(obs)
    if role == "explicit":
        point["role"] = "explicit_reconstruction"
        point["label"] = "Explicit Reconstruction"
    return point


def build_fixture():
    points = [
        point_from(observation("prompt-a", 4, 0.4)),
        point_from(observation("prompt-b", 8, 0.2)),
        point_from(observation("prompt-x", 12, 0.0), role="explicit"),
    ]
    receipts = [receipt_for("demo", point) for point in points]
    for point, receipt in zip(points, receipts):
        point["receiptDigest"] = receipt["receiptDigest"]
    artifact = [
        {"key": "demo", "label": "demo", "targetTokens": 3, "evalModel": "test/repo", "points": points},
        {"key": "pitch", "label": "pitch", "targetTokens": 0, "mode": "reveal", "script": "x", "points": []},
    ]
    doc = {
        "schemaVersion": SCHEMA_VERSION,
        "run": {"complete": True, "targets": ["demo"], "counts": compute_counts(receipts)},
        "receipts": receipts,
    }
    return artifact, doc


class ReceiptDigestTests(unittest.TestCase):
    def test_with_digest_is_canonical_and_stable(self) -> None:
        receipt = receipt_for("demo", observation("p", 4, 0.4))
        self.assertEqual(receipt["receiptDigest"], digest({k: v for k, v in receipt.items() if k != "receiptDigest"}))
        self.assertEqual(with_digest(dict(receipt)), receipt)

    def test_tampered_body_fails_digest(self) -> None:
        artifact, doc = build_fixture()
        doc["receipts"][0]["output"] = "tampered output"
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("receiptDigest: mismatch" in error for error in errors), errors)

    def test_prompt_and_output_digests(self) -> None:
        artifact, doc = build_fixture()
        doc["receipts"][1]["prompt"] = "changed prompt without digest update"
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("promptDigest: mismatch" in error for error in errors), errors)


class LinkageTests(unittest.TestCase):
    def test_fixture_passes(self) -> None:
        artifact, doc = build_fixture()
        self.assertEqual(verify_payloads(artifact, doc), [])

    def test_point_measurement_must_equal_receipt(self) -> None:
        artifact, doc = build_fixture()
        artifact[0]["points"][1]["similarity"] = 0.9999
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("displayed similarity differs" in error for error in errors), errors)

    def test_missing_receipt_fails_closed(self) -> None:
        artifact, doc = build_fixture()
        doc["receipts"] = doc["receipts"][:2]
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("does not resolve to a receipt" in error for error in errors), errors)

    def test_orphan_displayed_receipt_fails(self) -> None:
        artifact, doc = build_fixture()
        extra = receipt_for("demo", observation("prompt-extra", 16, 0.1))
        doc["receipts"].append(extra)
        doc["run"]["counts"] = compute_counts(doc["receipts"])
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("is not referenced by any artifact point" in error for error in errors), errors)

    def test_referenced_filtered_receipt_fails(self) -> None:
        artifact, doc = build_fixture()
        receipt = doc["receipts"][0]
        rebuilt = with_digest({**{k: v for k, v in receipt.items() if k != "receiptDigest"}, "status": "filtered"})
        doc["receipts"][0] = rebuilt
        artifact[0]["points"][0]["receiptDigest"] = rebuilt["receiptDigest"]
        doc["run"]["counts"] = compute_counts(doc["receipts"])
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("references a receipt with status" in error for error in errors), errors)

    def test_duplicate_receipt_digest_fails(self) -> None:
        artifact, doc = build_fixture()
        doc["receipts"].append(copy.deepcopy(doc["receipts"][0]))
        doc["run"]["counts"] = compute_counts(doc["receipts"])
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("duplicate receipt digest" in error for error in errors), errors)

    def test_double_reference_fails(self) -> None:
        artifact, doc = build_fixture()
        artifact[0]["points"][0]["receiptDigest"] = doc["receipts"][1]["receiptDigest"]
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("receipt already referenced" in error for error in errors), errors)

    def test_incomplete_run_flag_fails(self) -> None:
        artifact, doc = build_fixture()
        doc["run"]["complete"] = False
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("run.complete" in error for error in errors), errors)

    def test_counts_must_match(self) -> None:
        artifact, doc = build_fixture()
        doc["run"]["counts"]["displayed"] = 17
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("counts.displayed" in error for error in errors), errors)

    def test_epsilon_similarity_consistency(self) -> None:
        artifact, doc = build_fixture()
        receipt = doc["receipts"][0]
        rebuilt = with_digest({**{k: v for k, v in receipt.items() if k != "receiptDigest"}, "epsilon": 0.9})
        doc["receipts"][0] = rebuilt
        artifact[0]["points"][0]["receiptDigest"] = rebuilt["receiptDigest"]
        artifact[0]["points"][0]["epsilon"] = 0.9
        errors = verify_payloads(artifact, doc)
        self.assertTrue(any("epsilon/similarity are inconsistent" in error for error in errors), errors)


class ObservationAndSelectionTests(unittest.TestCase):
    def test_observation_fields_allowlist(self) -> None:
        full = observation("p", 4, 0.4)
        self.assertEqual(set(observation_fields(full)), set(full))
        with_embedding = dict(full, embeddingSimilarity=0.5)
        self.assertEqual(set(observation_fields(with_embedding)), set(full) | {"embeddingSimilarity"})
        del full["output"]
        with self.assertRaises(KeyError):
            observation_fields(full)

    def test_stability_scalar_bounds(self) -> None:
        self.assertEqual(stability_scalar([]), 1.0)
        self.assertEqual(stability_scalar([0.5]), 1.0)
        self.assertEqual(stability_scalar([0.9, 0.9, 0.9]), 1.0)
        self.assertEqual(stability_scalar([0.0, 1.0]), 0.0)
        self.assertEqual(stability_scalar([0.8, 0.9, 1.0]), 0.673)

    def test_selection_status_mirrors_shared_selector(self) -> None:
        points = [
            point_from(observation("short", 4, 0.4)),
            point_from(observation("dominated", 8, 0.6)),
            point_from(observation("better", 12, 0.3)),
            point_from(observation("explicit", 20, 0.1), role="explicit"),
        ]
        kept = observed_length_distortion_frontier(points)
        status = selection_status(points)
        annotate_consistency(points, kept, status)
        self.assertEqual([status[i][0] for i in range(4)], [True, False, True, True])
        self.assertIn("does not strictly improve", status[1][1])

    def test_selection_status_drift_raises(self) -> None:
        points = [point_from(observation("short", 4, 0.4))]
        with self.assertRaises(SystemExit):
            annotate_consistency(points, [], {0: (True, None)})

    def test_duplicate_length_tiebreak(self) -> None:
        points = [point_from(observation("aaa", 4, 0.5)), point_from(observation("bbb", 4, 0.2))]
        kept = observed_length_distortion_frontier(points)
        status = selection_status(points)
        annotate_consistency(points, kept, status)
        kept_prompts = [point["prompt"] for point in kept]
        self.assertEqual(kept_prompts, ["bbb"])
        loser = 0 if kept_prompts[0] == "bbb" else 1
        self.assertFalse(status[loser][0])
        self.assertIn("tie-break", status[loser][1])


class TargetTextTests(unittest.TestCase):
    WRAPPER = (
        "Repeat the following text exactly, verbatim, with no preamble, quotes, "
        "or commentary:\n\n"
    )

    def test_english_target_recovers_wrapped_text(self) -> None:
        from targets import TARGETS

        artifact = [
            {
                "key": "borges",
                "points": [
                    {"role": "explicit_reconstruction", "prompt": self.WRAPPER + TARGETS["borges"]["text"]},
                ],
            }
        ]
        self.assertEqual(target_texts(artifact), {"borges": TARGETS["borges"]["text"]})

    def test_cjk_target_is_the_explicit_prompt(self) -> None:
        artifact = [
            {
                "key": "spring",
                "metric": "cjk_char_trigram_overlap_for_fit; something",
                "points": [
                    {"role": "explicit_reconstruction", "prompt": "完整的文本"},
                ],
            }
        ]
        self.assertEqual(target_texts(artifact), {"spring": "完整的文本"})

    def test_missing_wrapper_fails_closed(self) -> None:
        artifact = [{"key": "borges", "points": [{"role": "explicit_reconstruction", "prompt": "no wrapper"}]}]
        with self.assertRaises(SystemExit):
            target_texts(artifact)


class ReuseGuardTests(unittest.TestCase):
    def test_identical_checkpoint_can_be_reused(self) -> None:
        model = {"repo": "test/repo", "revision": "abc123", "weightsDigest": digest("weights")}
        procedure = procedure_block(64)
        receipt = {"model": model, "procedure": procedure}
        self.assertIsNone(reuse_conflict(receipt, model, procedure))

    def test_model_drift_is_refused(self) -> None:
        procedure = procedure_block(64)
        receipt = {
            "model": {"repo": "test/repo", "revision": "old-rev", "weightsDigest": digest("weights")},
            "procedure": procedure,
        }
        current = {"repo": "test/repo", "revision": "new-rev", "weightsDigest": digest("weights")}
        conflict = reuse_conflict(receipt, current, procedure)
        self.assertIsNotNone(conflict)
        self.assertIn("model", conflict)

    def test_procedure_drift_is_refused(self) -> None:
        model = {"repo": "test/repo", "revision": "abc123", "weightsDigest": digest("weights")}
        stale = procedure_block(64)
        stale["toolVersion"] = "0.0.1"
        conflict = reuse_conflict({"model": model, "procedure": stale}, model, procedure_block(64))
        self.assertIsNotNone(conflict)
        self.assertIn("procedure", conflict)

    def test_expected_max_tokens_rule(self) -> None:
        self.assertEqual(expected_max_tokens(49, False), 110)
        self.assertEqual(expected_max_tokens(83, False), 164)
        self.assertEqual(expected_max_tokens(10, True), 46)
        self.assertEqual(expected_max_tokens(0, False), 32)


if __name__ == "__main__":
    unittest.main()
