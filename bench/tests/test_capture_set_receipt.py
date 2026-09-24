from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest import mock

from bench.engine.capture_set_receipt import (
    CaptureSetReceiptError,
    MODEL_MAPPING_ARTIFACT_KIND,
    MODEL_MAPPING_SCHEMA_VERSION,
    RECEIPT_ID_PREFIX,
    SCOPE_PLAN_ARTIFACT_KIND,
    SCOPE_PLAN_SCHEMA_VERSION,
    _artifact_id,
    _eligibility_blockers,
    _load_authority_registry,
    _model_mapping_id,
    _scope_plan_id,
    _verify_scope_plan,
    assemble_capture_set_receipt,
    serialize_capture_set_receipt,
    transport_canary_scope_plan,
    verify_capture_set_receipt,
)
from bench.engine.kaggle_capture import artifact_id_for, serialize_capture_payload
from bench.engine.kaggle_capture_evidence import (
    KaggleCaptureEvidenceError,
    VerifiedCaptureBundle,
    load_verified_capture_bundle,
    write_capture_evidence_bundle,
)
from bench.tasks.kaggle.generate_v0_2_capture import OUTPUT_PATH
from bench.tests.test_kaggle_capture_evidence import (
    DATASET,
    DOWNLOADED_AT,
    GEMMA_PROXY_SLUG,
    GEMMA_SCHEDULED_SLUG,
    TASK_SLUG,
    _archive,
    _dispatch_journal_bytes,
    _run_info,
    _task_info,
    _test_source_identity,
)
from bench.tests.test_kaggle_capture_task_v0_2 import (
    OpenAI,
    RUNTIME_313,
    _Chats,
    _Clock,
    _load_generated_task,
    _write_package,
)


def _canonical_mapping(
    *, scheduled: str = "provider-model", proxy: str = "provider/model"
) -> dict[str, Any]:
    mapping = {
        "mappingSchemaVersion": MODEL_MAPPING_SCHEMA_VERSION,
        "artifactKind": MODEL_MAPPING_ARTIFACT_KIND,
        "platform": "kaggle",
        "scheduledSlug": scheduled,
        "runtimeObservedProxySlug": proxy,
        "canonicalModelId": "research/model",
        "providerRevision": None,
        "id": "",
    }
    mapping["id"] = _model_mapping_id(mapping)
    return mapping


def _reidentify_receipt(receipt: dict[str, Any]) -> None:
    receipt["id"] = _artifact_id(
        receipt,
        RECEIPT_ID_PREFIX,
        role="test capture-set receipt",
    )


def _synthetic_calls(count: int = 900) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item_index in range(30):
        item_id = f"item-{item_index:02d}"
        for prompt_index in range(6):
            prompt_id = f"{item_id}-prompt-{prompt_index}"
            prompt = f"Synthetic prompt {item_index} {prompt_index}"
            for rerun_index in range(5):
                calls.append(
                    {
                        "rowId": f"{item_id}:{prompt_id}:rerun-{rerun_index}",
                        "itemId": item_id,
                        "promptId": prompt_id,
                        "rerunIndex": rerun_index,
                        "conversationName": (
                            f"synthetic-{item_index}-{prompt_index}-{rerun_index}"
                        ),
                        "promptText": prompt,
                        "promptUtf8Sha256": hashlib.sha256(
                            prompt.encode("utf-8")
                        ).hexdigest(),
                        "promptCodePointCount": len(prompt),
                    }
                )
    if count > len(calls):
        extra = copy.deepcopy(calls[0])
        extra.update(
            {
                "rowId": "item-extra:item-extra-prompt:rerun-0",
                "itemId": "item-extra",
                "promptId": "item-extra-prompt",
                "conversationName": "synthetic-extra",
            }
        )
        calls.append(extra)
    return calls[:count]


def _synthetic_scope_plan(count: int = 900) -> dict[str, Any]:
    calls = _synthetic_calls(count)
    request_policy = {
        "conversationIsolation": "oneNamedChatPerPromptAndRerun",
        "transportRetries": 0,
        "maxAttemptsPerCall": 1,
        "temperature": 0,
        "maxOutputTokens": 512,
        "nearCapMarginTokens": 4,
        "seed": 0,
        "reasoning": None,
    }
    plan = {
        "scopePlanSchemaVersion": SCOPE_PLAN_SCHEMA_VERSION,
        "artifactKind": SCOPE_PLAN_ARTIFACT_KIND,
        "targetProtocolVersion": "0.2.0",
        "scopeKind": "canonicalFull",
        "datasetIdentity": {
            "id": "synthetic-dataset",
            "itemCount": 30,
            "sha256": "1" * 64,
            "hashAlgorithm": "synthetic-test-only",
        },
        "packageIdentity": {
            "id": "synthetic-package",
            "manifestPath": "manifest.json",
            "sha256": "2" * 64,
            "bytes": 1,
        },
        "callPlanIdentity": {
            "id": "synthetic-call-plan",
            "sha256": "3" * 64,
            "fullShardPlanSha256": "4" * 64,
            "totalPlannedCallCount": 900,
            "rerunsPerPrompt": 5,
        },
        "requestPolicy": request_policy,
        "orderedCalls": calls,
        "id": "",
    }
    plan["id"] = _scope_plan_id(plan)
    return plan


def _fake_snapshot(
    plan: dict[str, Any],
    *,
    shard_id: str,
    run_id: int,
    start: int,
    stop: int,
) -> tuple[VerifiedCaptureBundle, tuple[dict[str, Any], dict[str, Any]]]:
    evidence_id = f"evidence-{run_id}"
    payload_id = f"payload-{run_id}"
    evidence_name = f"synthetic-task-v1-run-{run_id}-evidence.json"
    evidence = {
        "id": evidence_id,
        "assemblyEligible": True,
        "task": {
            "owner": "owner",
            "slug": "synthetic-task",
            "version": 1,
            "sourceKernelId": 1,
            "datasets": ["owner/synthetic-dataset"],
        },
        "run": {"id": run_id, "modelVersionSlug": "provider-model"},
        "archive": {"file": f"archive-{run_id}.zip"},
        "payload": {"file": f"payload-{run_id}.json"},
        "source": {"file": f"source-{run_id}.py"},
    }
    payload = {
        "id": payload_id,
        "datasetIdentity": copy.deepcopy(plan["datasetIdentity"]),
        "packageIdentity": copy.deepcopy(plan["packageIdentity"]),
        "callPlanIdentity": copy.deepcopy(plan["callPlanIdentity"]),
        "requestPolicy": copy.deepcopy(plan["requestPolicy"]),
        "taskIdentity": {
            "name": "synthetic-task-source",
            "version": "1",
            "sourcePath": "task.py",
            "definitionSha256": "5" * 64,
            "implementationSha256": "6" * 64,
        },
        "modelObservation": {
            "platform": "kaggle",
            "slug": "provider/model",
            "pythonType": "example.Model",
            "mappingStatus": "unmapped",
            "canonicalModelId": None,
            "providerRevision": None,
        },
        "runtimeObservation": {
            "pythonVersion": "3.12",
            "pythonFullVersion": "3.12.10",
            "unicodeDatabaseVersion": "15.0.0",
            "platform": "test-linux",
        },
        "shard": {
            "id": shard_id,
            "fullShardPlanSha256": plan["callPlanIdentity"][
                "fullShardPlanSha256"
            ],
            "coverageSha256": str(run_id).zfill(64),
            "plannedCalls": copy.deepcopy(plan["orderedCalls"][start:stop]),
        },
    }
    bundle = VerifiedCaptureBundle(
        evidence_path=Path(evidence_name),
        evidence={},
        payload={},
        evidence_bytes=f"evidence-{run_id}".encode(),
        archive_bytes=f"archive-{run_id}".encode(),
        payload_bytes=f"payload-{run_id}".encode(),
        source_bytes=f"source-{run_id}".encode(),
        dispatch_journal_bytes=None,
    )
    return bundle, (evidence, payload)


class CaptureSetPureContractTests(unittest.TestCase):
    def test_synthetic_exact_900_remains_ineligible_without_registry(self) -> None:
        plan = _verify_scope_plan(_synthetic_scope_plan())
        mapping = _canonical_mapping()
        registry, _registry_bytes = _load_authority_registry()
        self.assertEqual(registry["canonicalScoringAuthorities"], [])
        blockers = _eligibility_blockers(
            scope_kind="canonicalFull",
            request_policy=plan["requestPolicy"],
            call_plan=plan["callPlanIdentity"],
            mapping=mapping,
            authority_matched=False,
        )
        self.assertEqual(blockers, ["canonicalAuthorityNotRegistered"])

    def test_899_901_and_duplicate_rows_never_form_canonical_scope(self) -> None:
        for count in (899, 901):
            with self.subTest(count=count), self.assertRaises(
                CaptureSetReceiptError
            ):
                _verify_scope_plan(_synthetic_scope_plan(count))

        duplicate = _synthetic_scope_plan()
        duplicate["orderedCalls"][-1] = copy.deepcopy(
            duplicate["orderedCalls"][0]
        )
        duplicate["id"] = _scope_plan_id(duplicate)
        with self.assertRaisesRegex(CaptureSetReceiptError, "duplicate row id"):
            _verify_scope_plan(duplicate)

    def test_argument_order_does_not_change_synthetic_receipt(self) -> None:
        plan = _synthetic_scope_plan()
        first, first_snapshot = _fake_snapshot(
            plan, shard_id="shard-a", run_id=100, start=0, stop=450
        )
        second, second_snapshot = _fake_snapshot(
            plan, shard_id="shard-b", run_id=200, start=450, stop=900
        )
        snapshots = {
            first.evidence_path.name: first_snapshot,
            second.evidence_path.name: second_snapshot,
        }

        def reverify(bundle: VerifiedCaptureBundle) -> tuple[dict[str, Any], dict[str, Any]]:
            return copy.deepcopy(snapshots[bundle.evidence_path.name])

        with mock.patch(
            "bench.engine.capture_set_receipt._reverify_bundle",
            side_effect=reverify,
        ):
            ordered = assemble_capture_set_receipt(
                [first, second], scope_plan=plan
            )
            reversed_receipt = assemble_capture_set_receipt(
                [second, first], scope_plan=plan
            )
        self.assertEqual(ordered, reversed_receipt)
        self.assertFalse(ordered["canonicalScoringInputEligible"])
        self.assertEqual(
            ordered["canonicalScoringInputBlockers"],
            [
                "canonicalModelMappingMissing",
                "canonicalAuthorityNotRegistered",
            ],
        )

    def test_request_policy_numeric_representation_drift_fails_closed(self) -> None:
        plan = _synthetic_scope_plan()
        first, first_snapshot = _fake_snapshot(
            plan, shard_id="shard-a", run_id=100, start=0, stop=450
        )
        second, second_snapshot = _fake_snapshot(
            plan, shard_id="shard-b", run_id=200, start=450, stop=900
        )
        second_snapshot[1]["requestPolicy"]["temperature"] = -0.0
        snapshots = {
            first.evidence_path.name: first_snapshot,
            second.evidence_path.name: second_snapshot,
        }

        def reverify(
            bundle: VerifiedCaptureBundle,
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            return copy.deepcopy(snapshots[bundle.evidence_path.name])

        with mock.patch(
            "bench.engine.capture_set_receipt._reverify_bundle",
            side_effect=reverify,
        ), self.assertRaisesRegex(CaptureSetReceiptError, "request policy drifted"):
            assemble_capture_set_receipt([first, second], scope_plan=plan)

    def test_scope_plan_numeric_representation_drift_fails_closed(self) -> None:
        plan = _synthetic_scope_plan()
        first, first_snapshot = _fake_snapshot(
            plan, shard_id="shard-a", run_id=100, start=0, stop=450
        )
        second, second_snapshot = _fake_snapshot(
            plan, shard_id="shard-b", run_id=200, start=450, stop=900
        )
        first_snapshot[1]["requestPolicy"]["temperature"] = -0.0
        second_snapshot[1]["requestPolicy"]["temperature"] = -0.0
        snapshots = {
            first.evidence_path.name: first_snapshot,
            second.evidence_path.name: second_snapshot,
        }

        def reverify(
            bundle: VerifiedCaptureBundle,
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            return copy.deepcopy(snapshots[bundle.evidence_path.name])

        with mock.patch(
            "bench.engine.capture_set_receipt._reverify_bundle",
            side_effect=reverify,
        ), self.assertRaisesRegex(
            CaptureSetReceiptError, "differs from scope-plan requestPolicy"
        ):
            assemble_capture_set_receipt([first, second], scope_plan=plan)

    def test_serialized_synthetic_receipt_rejects_duplicate_member_ids(self) -> None:
        plan = _synthetic_scope_plan()
        first, first_snapshot = _fake_snapshot(
            plan, shard_id="shard-a", run_id=100, start=0, stop=450
        )
        second, second_snapshot = _fake_snapshot(
            plan, shard_id="shard-b", run_id=200, start=450, stop=900
        )
        snapshots = {
            first.evidence_path.name: first_snapshot,
            second.evidence_path.name: second_snapshot,
        }

        def reverify(
            bundle: VerifiedCaptureBundle,
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            return copy.deepcopy(snapshots[bundle.evidence_path.name])

        with mock.patch(
            "bench.engine.capture_set_receipt._reverify_bundle",
            side_effect=reverify,
        ):
            receipt = assemble_capture_set_receipt(
                [first, second], scope_plan=plan
            )
        receipt["members"][1]["evidence"]["id"] = receipt["members"][0][
            "evidence"
        ]["id"]
        _reidentify_receipt(receipt)
        with self.assertRaisesRegex(CaptureSetReceiptError, "duplicate evidence id"):
            serialize_capture_set_receipt(receipt)

    def test_model_policy_task_and_source_drift_fail_closed(self) -> None:
        plan = _synthetic_scope_plan()
        first, first_snapshot = _fake_snapshot(
            plan, shard_id="shard-a", run_id=100, start=0, stop=450
        )
        second, second_snapshot = _fake_snapshot(
            plan, shard_id="shard-b", run_id=200, start=450, stop=900
        )
        mutations = {
            "model identity": lambda e, p: p["modelObservation"].update(
                {"slug": "provider/drift"}
            ),
            "request policy": lambda e, p: p["requestPolicy"].update(
                {"nearCapMarginTokens": 8}
            ),
            "Task platform version": lambda e, p: e["task"].update(
                {"version": 2}
            ),
            "task source identity": lambda e, p: p["taskIdentity"].update(
                {"definitionSha256": "9" * 64}
            ),
        }
        for message, mutate in mutations.items():
            drifted = copy.deepcopy(second_snapshot)
            mutate(*drifted)

            def reverify(bundle: VerifiedCaptureBundle) -> tuple[dict[str, Any], dict[str, Any]]:
                return copy.deepcopy(
                    first_snapshot
                    if bundle.evidence_path.name == first.evidence_path.name
                    else drifted
                )

            with self.subTest(message=message), mock.patch(
                "bench.engine.capture_set_receipt._reverify_bundle",
                side_effect=reverify,
            ), self.assertRaisesRegex(CaptureSetReceiptError, message):
                assemble_capture_set_receipt([first, second], scope_plan=plan)

    def test_union_gap_overlap_and_unplanned_row_fail_closed(self) -> None:
        plan = _synthetic_scope_plan()
        first, first_snapshot = _fake_snapshot(
            plan, shard_id="shard-a", run_id=100, start=0, stop=450
        )
        cases: list[
            tuple[str, VerifiedCaptureBundle, tuple[dict[str, Any], dict[str, Any]]]
        ] = []
        gap_bundle, gap_snapshot = _fake_snapshot(
            plan, shard_id="shard-gap", run_id=201, start=450, stop=899
        )
        cases.append(("gap or extra row", gap_bundle, gap_snapshot))
        overlap_bundle, overlap_snapshot = _fake_snapshot(
            plan, shard_id="shard-overlap", run_id=202, start=449, stop=900
        )
        cases.append(("duplicate or overlapping row", overlap_bundle, overlap_snapshot))
        extra_bundle, extra_snapshot = _fake_snapshot(
            plan, shard_id="shard-extra", run_id=203, start=450, stop=900
        )
        extra_call = copy.deepcopy(plan["orderedCalls"][0])
        extra_call.update(
            {
                "rowId": "item-extra:item-extra-prompt:rerun-0",
                "itemId": "item-extra",
                "promptId": "item-extra-prompt",
                "conversationName": "synthetic-extra",
            }
        )
        extra_snapshot[1]["shard"]["plannedCalls"].append(extra_call)
        cases.append(("unplanned or drifted call", extra_bundle, extra_snapshot))

        for message, second, second_snapshot in cases:
            def reverify(
                bundle: VerifiedCaptureBundle,
            ) -> tuple[dict[str, Any], dict[str, Any]]:
                return copy.deepcopy(
                    first_snapshot
                    if bundle.evidence_path.name == first.evidence_path.name
                    else second_snapshot
                )

            with self.subTest(message=message), mock.patch(
                "bench.engine.capture_set_receipt._reverify_bundle",
                side_effect=reverify,
            ), self.assertRaisesRegex(CaptureSetReceiptError, message):
                assemble_capture_set_receipt([first, second], scope_plan=plan)


class CaptureSetReceiptIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_identity_patch = mock.patch(
            "bench.engine.kaggle_capture_evidence.current_capture_source_identity",
            return_value=_test_source_identity(),
        )
        cls.source_identity_patch.start()
        cls.addClassCleanup(cls.source_identity_patch.stop)
        cls.generated, cls.previous_kaggle_module = _load_generated_task()
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.package_root = cls.root / "package"
        cls.package_root.mkdir()
        _write_package(cls.package_root)
        cls.source_bytes = OUTPUT_PATH.read_bytes()
        cls.payload_bytes = cls._make_payload_bytes()
        cls.bundle_dir = cls.root / "bundle"
        cls.evidence = cls._write_bundle(
            cls.payload_bytes,
            cls.bundle_dir,
        )
        cls.evidence_path = cls.bundle_dir / (
            f"{TASK_SLUG}-v3-run-24680-evidence.json"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()
        import sys

        if cls.previous_kaggle_module is None:
            sys.modules.pop("kaggle_benchmarks", None)
        else:
            sys.modules["kaggle_benchmarks"] = cls.previous_kaggle_module

    @classmethod
    def _make_payload_bytes(cls) -> bytes:
        capture = cls.root / "capture.json"
        llm = OpenAI()
        llm.model = GEMMA_PROXY_SLUG
        cls.generated.run_capture_canary(
            llm,
            chats=_Chats(),
            package_root=cls.package_root,
            capture_path=capture,
            observed_runtime=RUNTIME_313,
            clock=_Clock(),
        )
        return capture.read_bytes()

    @classmethod
    def _write_bundle(
        cls, payload_bytes: bytes, output_dir: Path
    ) -> dict[str, Any]:
        return write_capture_evidence_bundle(
            task_info=_task_info(),
            run_info=_run_info(model=GEMMA_SCHEDULED_SLUG),
            requested_task=f"owner/{TASK_SLUG}",
            expected_version=3,
            expected_source_kernel_id=12345,
            expected_run_id=24680,
            expected_datasets=(DATASET,),
            archive_bytes=_archive(payload_bytes, cls.source_bytes),
            output_dir=output_dir,
            downloaded_at=DOWNLOADED_AT,
            dispatch_journal_bytes=_dispatch_journal_bytes(),
        )

    def _copy_bundle(self, name: str) -> tuple[Path, Path]:
        destination = self.root / name
        shutil.copytree(self.bundle_dir, destination)
        return destination, destination / self.evidence_path.name

    def test_exact_canary_is_deterministic_and_score_free(self) -> None:
        bundle = load_verified_capture_bundle(self.evidence_path)
        plan = transport_canary_scope_plan()
        first = assemble_capture_set_receipt([bundle], scope_plan=plan)
        second = assemble_capture_set_receipt([bundle], scope_plan=plan)
        self.assertEqual(first, second)
        self.assertEqual(
            serialize_capture_set_receipt(first),
            serialize_capture_set_receipt(second),
        )
        self.assertFalse(first["canonicalScoringInputEligible"])
        self.assertFalse(first["leaderboardEligible"])
        self.assertFalse(first["resultEligible"])
        self.assertFalse(first["publicationEligible"])
        self.assertEqual(first["coverage"]["callCount"], 6)
        self.assertEqual(first["coverage"]["completeCanonicalItemCount"], 0)
        self.assertEqual(
            verify_capture_set_receipt(
                first,
                [bundle],
                scope_plan=plan,
            ),
            first,
        )

    def test_assembler_reverifies_bytes_and_rejects_duplicate_member(self) -> None:
        bundle = load_verified_capture_bundle(self.evidence_path)
        corrupted = replace(bundle, payload_bytes=bundle.payload_bytes + b" ")
        with self.assertRaises(KaggleCaptureEvidenceError):
            assemble_capture_set_receipt(
                [corrupted], scope_plan=transport_canary_scope_plan()
            )
        with self.assertRaisesRegex(CaptureSetReceiptError, "duplicate evidence id"):
            assemble_capture_set_receipt(
                [bundle, bundle], scope_plan=transport_canary_scope_plan()
            )

    def test_near_cap_bundle_is_not_assembly_eligible(self) -> None:
        payload = json.loads(self.payload_bytes)
        row_id = payload["rows"][0]["rowId"]
        payload["rows"][0]["usage"]["outputTokens"] = 2016
        payload["diagnostics"]["nearCapOutputRowIds"] = [row_id]
        payload["diagnostics"]["replayBlockedReasons"] = ["nearCapOutput"]
        payload["canonicalReplayEligible"] = False
        payload["id"] = artifact_id_for(payload)
        payload_bytes = serialize_capture_payload(payload)
        output_dir = self.root / "near-cap"
        evidence = self._write_bundle(payload_bytes, output_dir)
        self.assertFalse(evidence["assemblyEligible"])
        bundle = load_verified_capture_bundle(
            output_dir / f"{TASK_SLUG}-v3-run-24680-evidence.json"
        )
        with self.assertRaisesRegex(
            CaptureSetReceiptError, "not assembly eligible"
        ):
            assemble_capture_set_receipt(
                [bundle], scope_plan=transport_canary_scope_plan()
            )

    def test_scope_gap_extra_duplicate_and_order_drift_fail_closed(self) -> None:
        bundle = load_verified_capture_bundle(self.evidence_path)
        plan = transport_canary_scope_plan()
        cases: list[tuple[str, dict[str, Any]]] = []
        missing = copy.deepcopy(plan)
        missing["orderedCalls"].pop()
        missing["id"] = _scope_plan_id(missing)
        cases.append(("incomplete or over-complete", missing))
        duplicate = copy.deepcopy(plan)
        duplicate["orderedCalls"][-1] = copy.deepcopy(
            duplicate["orderedCalls"][0]
        )
        duplicate["id"] = _scope_plan_id(duplicate)
        cases.append(("duplicate row id", duplicate))
        reordered = copy.deepcopy(plan)
        reordered["orderedCalls"][0], reordered["orderedCalls"][1] = (
            reordered["orderedCalls"][1],
            reordered["orderedCalls"][0],
        )
        reordered["id"] = _scope_plan_id(reordered)
        cases.append(("frozen generated authority", reordered))
        for message, candidate in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                CaptureSetReceiptError, message
            ):
                assemble_capture_set_receipt([bundle], scope_plan=candidate)

    def test_loader_rejects_extra_symlink_hardlink_duplicate_and_nonfinite(self) -> None:
        directory_alias = self.root / "bundle-directory-alias"
        directory_alias.symlink_to(self.bundle_dir, target_is_directory=True)
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "must not contain a symlink"
        ):
            load_verified_capture_bundle(directory_alias / self.evidence_path.name)

        extra_dir, extra_evidence = self._copy_bundle("extra")
        (extra_dir / "unexpected.txt").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "closed-world file set"
        ):
            load_verified_capture_bundle(extra_evidence)

        symlink_dir, symlink_evidence = self._copy_bundle("symlink")
        payload_name = self.evidence["payload"]["file"]
        payload_path = symlink_dir / payload_name
        payload_copy = symlink_dir / "outside-payload"
        payload_copy.write_bytes(payload_path.read_bytes())
        payload_path.unlink()
        payload_path.symlink_to(payload_copy.name)
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "closed-world file set|single-link regular"
        ):
            load_verified_capture_bundle(symlink_evidence)

        hardlink_dir, hardlink_evidence = self._copy_bundle("hardlink")
        hardlink_payload = hardlink_dir / payload_name
        outside = self.root / "hardlink-target"
        outside.write_bytes(hardlink_payload.read_bytes())
        hardlink_payload.unlink()
        os.link(outside, hardlink_payload)
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "single-link regular"
        ):
            load_verified_capture_bundle(hardlink_evidence)

        duplicate_dir, duplicate_evidence = self._copy_bundle("duplicate-json")
        original = duplicate_evidence.read_bytes()
        duplicate_evidence.write_bytes(
            b'{"evidenceSchemaVersion":"1.1.0",' + original[1:]
        )
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "duplicate JSON key"
        ):
            load_verified_capture_bundle(duplicate_evidence)

        nonfinite_dir, nonfinite_evidence = self._copy_bundle("nonfinite-json")
        del nonfinite_dir
        original = nonfinite_evidence.read_bytes()
        nonfinite_evidence.write_bytes(
            original.replace(b'"assemblyEligible": true', b'"assemblyEligible": NaN')
        )
        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "non-finite JSON constant"
        ):
            load_verified_capture_bundle(nonfinite_evidence)

    def test_loader_rejects_symlink_in_intermediate_ancestor(self) -> None:
        real_parent = self.root / "real-parent"
        nested_bundle = real_parent / "nested-bundle"
        shutil.copytree(self.bundle_dir, nested_bundle)
        intermediate_alias = self.root / "intermediate-alias"
        intermediate_alias.symlink_to(real_parent, target_is_directory=True)

        with self.assertRaisesRegex(
            KaggleCaptureEvidenceError, "must not contain a symlink"
        ):
            load_verified_capture_bundle(
                intermediate_alias / nested_bundle.name / self.evidence_path.name
            )

    def test_score_result_and_metric_fields_are_structurally_forbidden(self) -> None:
        bundle = load_verified_capture_bundle(self.evidence_path)
        receipt = assemble_capture_set_receipt(
            [bundle], scope_plan=transport_canary_scope_plan()
        )
        for field in (
            "score",
            "scores",
            "metric",
            "metrics",
            "BenchManifest",
            "BenchResult",
        ):
            mutated = copy.deepcopy(receipt)
            mutated[field] = 0
            with self.subTest(field=field), self.assertRaisesRegex(
                CaptureSetReceiptError, "cannot contain"
            ):
                serialize_capture_set_receipt(mutated)

        nested = copy.deepcopy(receipt)
        nested["identities"]["runtime"]["metrics"] = []
        with self.assertRaisesRegex(CaptureSetReceiptError, "cannot contain"):
            serialize_capture_set_receipt(nested)

        forged = copy.deepcopy(receipt)
        forged["canonicalScoringInputEligible"] = True
        forged["canonicalScoringInputBlockers"] = []
        with self.assertRaisesRegex(CaptureSetReceiptError, "blockers were not derived"):
            serialize_capture_set_receipt(forged)

    def test_serialized_receipt_rejects_cross_field_forgery(self) -> None:
        bundle = load_verified_capture_bundle(self.evidence_path)
        receipt = assemble_capture_set_receipt(
            [bundle], scope_plan=transport_canary_scope_plan()
        )

        cases = (
            (
                "scope coverage",
                lambda value: value["coverage"].update({"callCount": 900}),
                "coverage disagrees",
            ),
            (
                "scope plan count",
                lambda value: value["scopePlan"].update(
                    {"orderedCallCount": 900}
                ),
                "scope-plan count disagrees",
            ),
            (
                "member row order",
                lambda value: value["members"][0]["shard"].update(
                    {
                        "rowIds": list(
                            reversed(value["members"][0]["shard"]["rowIds"])
                        )
                    }
                ),
                "member rows disagree",
            ),
            (
                "full shard plan",
                lambda value: value["members"][0]["shard"].update(
                    {"fullShardPlanSha256": "f" * 64}
                ),
                "full-shard-plan binding drifted",
            ),
            (
                "model catalog identity",
                lambda value: value["identities"]["model"].update(
                    {"benchmarkModelVersionId": None}
                ),
                "model catalog identity is inconsistent",
            ),
            (
                "member model catalog binding",
                lambda value: value["members"][0].update({"operationId": None}),
                "member model-catalog binding is inconsistent",
            ),
            (
                "frozen scope id",
                lambda value: value["scopePlan"].update(
                    {
                        "id": (
                            "aleph-bench-capture-scope-plan-v1-artifact-"
                            + "0" * 64
                        )
                    }
                ),
                "scope id is not frozen",
            ),
            (
                "frozen dataset identity",
                lambda value: value["identities"]["dataset"].update(
                    {"sha256": "0" * 64}
                ),
                "identity differs from frozen authority",
            ),
        )
        for role, mutate, message in cases:
            forged = copy.deepcopy(receipt)
            mutate(forged)
            _reidentify_receipt(forged)
            with self.subTest(role=role), self.assertRaisesRegex(
                CaptureSetReceiptError, message
            ):
                serialize_capture_set_receipt(forged)

    def test_content_addressed_mapping_cannot_promote_canary(self) -> None:
        bundle = load_verified_capture_bundle(self.evidence_path)
        mapping = _canonical_mapping(
            scheduled=GEMMA_SCHEDULED_SLUG,
            proxy=GEMMA_PROXY_SLUG,
        )
        receipt = assemble_capture_set_receipt(
            [bundle],
            scope_plan=transport_canary_scope_plan(),
            canonical_model_mapping=mapping,
        )
        self.assertFalse(receipt["canonicalScoringInputEligible"])
        self.assertIn(
            "canonicalAuthorityNotRegistered",
            receipt["canonicalScoringInputBlockers"],
        )
        tampered = copy.deepcopy(mapping)
        tampered["canonicalModelId"] = "research/other"
        with self.assertRaisesRegex(CaptureSetReceiptError, "artifact id mismatch"):
            assemble_capture_set_receipt(
                [bundle],
                scope_plan=transport_canary_scope_plan(),
                canonical_model_mapping=tampered,
            )

        stale_mapping = copy.deepcopy(receipt)
        stale_mapping["canonicalModelMapping"]["canonicalModelId"] = (
            "research/other"
        )
        _reidentify_receipt(stale_mapping)
        with self.assertRaisesRegex(CaptureSetReceiptError, "artifact id mismatch"):
            serialize_capture_set_receipt(stale_mapping)

        drifted_mapping = _canonical_mapping(
            scheduled="other-scheduled-model",
            proxy=GEMMA_PROXY_SLUG,
        )
        drifted_receipt = copy.deepcopy(receipt)
        for field in drifted_receipt["canonicalModelMapping"]:
            drifted_receipt["canonicalModelMapping"][field] = drifted_mapping[field]
        _reidentify_receipt(drifted_receipt)
        with self.assertRaisesRegex(
            CaptureSetReceiptError, "differs from its observed model identities"
        ):
            serialize_capture_set_receipt(drifted_receipt)


if __name__ == "__main__":
    unittest.main()
