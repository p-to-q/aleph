"""One six-call Kaggle engine diagnostic; no live imports in the core path.

The coordinate tokenizer is the explicitly declared UTF-8 byte tokenizer,
not the provider's hidden tokenizer. This is transport/plumbing evidence only.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
from typing import Any, Callable

from .canonical import digest
from .confirmation import ConfirmationSpec
from .contracts import (
    Candidate, Message, Placement, adapter_identity, evaluation_receipt,
    proposal_receipt,
)
from .export_aleph_run import export_aleph_run
from .hybrid_pareto import FrozenConfig, run_hybrid_search
from .ledger import CoordinateCost
from .operators import RewriteSpec
from .verify import verify_bundle

TARGET = "42"
TOKENIZER = {"id": "aleph-diagnostic/utf8-byte-v1", "encoding": "utf-8", "unit": "byte", "providerNative": False}
POLICY_ID = "aleph-kaggle-hybrid-107/2026-11-27"
MAX_CALLS = 6
MAX_OUTPUT_TOKENS = 64


def save_json(path: Path, value: Any) -> None:
    """Persist call state before dispatch, using atomic replacement + fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def coordinate_text(candidate: Candidate) -> str:
    return "\n".join(message.content for message in candidate.messages)


def surface_metrics(prompt: str, output: str) -> dict[str, float]:
    """Toy surface metrics only; one-sample stability is tautological, not estimated."""
    target = Counter(TARGET.encode())
    literal = Counter(prompt.encode())
    return {"fit": float(output.strip() == TARGET), "stability": 1.0,
            "compression": round(len(TARGET.encode()) / (len(TARGET.encode()) + len(prompt.encode())), 6),
            "leakage": round(sum(min(n, literal[k]) for k, n in target.items()) / sum(target.values()), 6)}


def resource_use(record: dict[str, Any]) -> dict[str, Any]:
    usage = record["usage"]
    return {"inputTokens": usage.get("inputTokens"), "outputTokens": usage.get("outputTokens"),
            "samples": 1, "failures": 0, "retries": 0, "cacheMisses": 0,
            "providerReportedTokens": (usage["inputTokens"] + usage["outputTokens"]
                if all(type(usage.get(k)) is int for k in ("inputTokens", "outputTokens")) else None)}


def run_diagnostic(root: Path, policy: dict[str, Any], call: Callable[[str, str], dict[str, Any]]) -> dict[str, Any]:
    """Run a fixed four-candidate search and one fresh confirmation.

    A model proposal is obtained once, then frozen as a seed. Zero adaptive
    operator rounds are intentional for this six-call diagnostic. Failed calls
    permanently trip this run's dispatch barrier; the scheduler cannot retry.
    """
    root = Path(root)
    if policy.get("policyId") != POLICY_ID or type(policy.get("maxCalls")) is not int or policy["maxCalls"] != MAX_CALLS:
        raise ValueError("unsupported canary policy")
    for key in ("modelVersion", "modelProxySlug", "sourceCommit", "createdAt", "schemaPath"):
        if not isinstance(policy.get(key), str) or not policy[key]:
            raise ValueError(f"missing frozen policy field: {key}")
    if not Path(policy["schemaPath"]).is_file():
        raise ValueError("frozen schema is unavailable")
    root.mkdir(parents=True, exist_ok=False)
    save_json(root / "policy.json", policy)
    rows: list[dict[str, Any]] = []
    failed = False
    def ask(phase: str, prompt: str) -> dict[str, Any]:
        nonlocal failed
        if failed or len(rows) >= MAX_CALLS:
            raise RuntimeError("one-shot model dispatch barrier is closed")
        row = {"index": len(rows) + 1, "phase": phase, "prompt": prompt, "state": "dispatching"}
        rows.append(row)
        save_json(root / "calls.json", rows)
        try:
            result = call(phase, prompt)
            if not isinstance(result.get("output"), str) or len(result["output"].encode()) > 32768:
                raise ValueError("invalid or oversized output")
            if not isinstance(result.get("usage"), dict):
                raise ValueError("usage must be an explicit mapping")
            row.update(result)
            row["state"] = "completed"
            return row
        except Exception as error:
            failed = True
            row.update(state="failed", error={"type": type(error).__name__, "message": str(error)[:1000]})
            raise
        finally:
            save_json(root / "calls.json", rows)
    summary: dict[str, Any] = {"diagnosticOnly": True, "benchmarkEligible": False,
                              "status": "failed", "policyId": POLICY_ID}
    try:
        proposed = ask("proposal", 'Write one short instruction whose answer is exactly the number 42. Return only the instruction, not its answer.')
        proposed_text = proposed["output"].strip()
        if not proposed_text or len(proposed_text.encode()) > 4096:
            raise ValueError("proposal is empty or exceeds frozen coordinate bound; no target-copy fallback")
        placement = Placement("kaggle-107-isolated-user", digest(TOKENIZER), "messages[*]", "utf8-byte-v1")
        seeds = tuple(Candidate(messages=(Message("user", text),), placement=placement,
                                proposal_mode=mode, role=role) for text, mode, role in [
            ('Return exactly this text and nothing else: 42', 'reference', 'explicit_reconstruction'),
            ('Answer with only the integer that is six multiplied by seven.', 'seed', 'candidate'),
            ('', 'seed', 'candidate'),
            (proposed_text, 'seed', 'candidate'),
        ])
        if len({x.candidate_id for x in seeds}) != 4:
            raise ValueError("proposal duplicated a frozen seed; no replacement request")
        # The canonical scheduler excludes explicit reconstruction from selection.
        # Measure it separately without weakening that rule; the outer call ledger
        # accounts for this additional control evaluation and its provider usage.
        control = ask("discovery-control", coordinate_text(seeds[0]))
        control["candidateId"] = seeds[0].candidate_id
        save_json(root / "calls.json", rows)
        save_json(root / "control.json", {"candidate": seeds[0].to_canonical(),
            "callIndex": control["index"], "metrics": surface_metrics(control["prompt"], control["output"]),
            "selectionEligible": False, "accountingScope": "outer_envelope_not_canonical_engine"})
        proposal_identity = adapter_identity("kaggle-107/proposer", policy["modelVersion"], "proposal",
                                             manifest={"model": policy["modelProxySlug"], "policyDigest": digest(policy)})
        evaluation_identity = adapter_identity("kaggle-107/evaluator", policy["modelVersion"], "evaluation",
                                               manifest={"model": policy["modelProxySlug"], "policyDigest": digest(policy)})
        class Proposer:
            identity = proposal_identity
            def propose(self, request):
                return proposal_receipt(request_id=request.request_id, adapter=self.identity,
                                        candidates=seeds, resource_use=resource_use(proposed))
        class Evaluator:
            identity = evaluation_identity
            def evaluate(self, request):
                phase = "discovery" if len(rows) < 5 else "confirmation"
                row = ask(phase, coordinate_text(request.candidate))
                row["candidateId"] = request.candidate.candidate_id
                row["requestId"] = request.request_id
                save_json(root / "calls.json", rows)
                return evaluation_receipt(request_id=request.request_id, adapter=self.identity,
                    candidate_id=request.candidate.candidate_id,
                    metrics=surface_metrics(row["prompt"], row["output"]),
                    resource_use=resource_use(row), outputs={"text": row["output"], "callIndex": row["index"], "metricScope": "toy_exact_match_byte_length_literal_byte_leakage_one_sample"})
        config = FrozenConfig(seeds=seeds, operator_specs=(RewriteSpec(index=0, transform="lowercase"),),
            operator_weights=(("rewrite", 1.0),), exploration_share=0.5, exploit_top_k=1,
            parent_rule="uniform_promoted", metric="fit", promote_threshold=0.0,
            max_proposal_rounds=0, max_promoted=4, stop_rule="rounds", racing_rule="evaluate_all",
            retries=0, rng_seed=107, control_arm=True, confirmation_checks=())
        confirmation = ConfirmationSpec(digest({"phase": "discovery", "policy": digest(policy)}),
            digest({"phase": "fresh-confirmation", "policy": digest(policy)}), "107-fresh-1", "fit", 1.0, 1, 1.0, 0.5)
        def cost(candidate):
            size = len(coordinate_text(candidate).encode("utf-8"))
            return CoordinateCost(TOKENIZER["id"], digest(TOKENIZER), size, size, size, size, len(TARGET.encode()), 0)
        result = run_hybrid_search(root / "bundle", "aleph-kaggle-hybrid-107-20261127", config,
            confirmation, Proposer(), Evaluator(), target_digest=digest(TARGET), known_metrics=("fit", "stability", "compression", "leakage"),
            nesting_rule="t_dec_nested_in_w_search", scheduler_model="kaggle-hybrid-107",
            model_manifest={"model": policy["modelProxySlug"], "revision": policy["modelVersion"],
                "mode": "unrestricted", "observationMode": "black_box",
                "decoding": {"temperature": 0.0, "maxOutputTokens": MAX_OUTPUT_TOKENS, "transportRetries": 0},
                "tokenizer": TOKENIZER, "sourceCommit": policy["sourceCommit"], "diagnosticOnly": True},
            coordinate_cost=cost, target_content=TARGET, run_created_at=policy["createdAt"])
        exported = export_aleph_run(root / "bundle", schema_path=Path(policy["schemaPath"]))
        report = verify_bundle(root / "bundle")
        summary.update(status="completed" if len(rows) == 6 and not failed and report.ok else "failed",
            confirmationOutcome=result.confirmation_outcome, selectedCandidateId=exported.projection.get("selectedCandidateId"),
            streamDigest=report.stream_digest, verificationErrors=list(report.errors))
    except Exception as error:
        summary["error"] = {"type": type(error).__name__, "message": str(error)[:1500]}
    summary.update(callCount=len(rows), completedCalls=sum(r["state"] == "completed" for r in rows),
                   coordinateTokenizer=TOKENIZER, providerNativeTokenizer=None)
    # Unknown provider usage remains unknown, including failed dispatches. The
    # canonical engine ledger excludes the separately measured control by design.
    fields = ("inputTokens", "outputTokens", "inputCostNanodollars", "outputCostNanodollars")
    totals = {}
    for name in fields:
        values = [r.get("usage", {}).get(name) for r in rows]
        totals[name] = sum(values) if values and all(type(x) is int and x >= 0 for x in values) else None
    summary["providerUsage"] = totals
    save_json(root / "envelope-ledger.json", {"schemaVersion": "aleph-kaggle-107-envelope-ledger/1",
        "scope": "all_model_dispatches_including_control", "calls": len(rows), "totals": totals,
        "phases": [{"index": r["index"], "phase": r["phase"], "state": r["state"],
                    "usage": r.get("usage")} for r in rows],
        "canonicalEngineLedgerScope": "proposal_three_ordinary_discoveries_one_confirmation_excludes_control",
        "localSelectionVerificationReplayProviderCalls": 0})
    save_json(root / "summary.json", summary)
    return summary


def seal(root: Path) -> None:
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError("symlinks cannot enter diagnostic evidence")
        if p.is_file() and p != root / "files.json":
            data = p.read_bytes()
            files.append({"path": p.relative_to(root).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    save_json(root / "files.json", {"schemaVersion": "aleph-kaggle-107-files/1", "files": files})


def hosted_call(llm: Any, chats: Any, expected_model: str, root: Path):
    """Use only the supported OpenAI actor with explicit no-retry readback."""
    if getattr(llm, "model", None) != expected_model:
        raise ValueError("hosted model identity differs from frozen catalog mapping")
    if f"{type(llm).__module__}.{type(llm).__name__}" not in {"kaggle_benchmarks.actors.llms.OpenAI", "kaggle_benchmarks.actors.proxy_openai.OpenAI"}:
        raise ValueError("unsupported hosted transport type")
    # Kaggle's default httpx client caches POST responses. Replace it through
    # OpenAI's public option so confirmation is a new network request.
    import httpx
    transport = httpx.HTTPTransport(retries=0)
    uncached = httpx.Client(transport=transport, timeout=90.0)
    configured = llm.client.with_options(max_retries=0, timeout=90.0, http_client=uncached)
    if configured.max_retries != 0 or configured.timeout != 90.0:
        raise ValueError("transport timeout/retry policy readback failed")
    llm.client = configured
    count = 0
    def call(phase, prompt):
        nonlocal count
        count += 1
        with chats.new(f"aleph107-{count}-{phase}") as chat:
            output = llm.prompt(prompt, seed=108 if phase == "confirmation" else 107, temperature=0.0, extra_api_params={"max_tokens": MAX_OUTPUT_TOKENS})
            usage = chat.usage
            def number(name):
                value = getattr(usage, name, None)
                return value if type(value) is int and value >= 0 else None
            return {"output": output, "usage": {"inputTokens": number("input_tokens"),
                "outputTokens": number("output_tokens"), "inputCostNanodollars": number("input_tokens_cost_nanodollars"),
                "outputCostNanodollars": number("output_tokens_cost_nanodollars")}}
    return call


def hosted_entry(llm: Any, kbench: Any, root: Path, policy: dict[str, Any]):
    runtime = {"python": platform.python_version(), "platform": platform.platform(), "packages": {}}
    for name in ("kaggle-benchmarks", "openai", "kaggle"):
        try:
            runtime["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            runtime["packages"][name] = None
    try:
        if runtime["packages"]["kaggle-benchmarks"] is None or runtime["packages"]["openai"] is None:
            raise ValueError("hosted package identity unavailable")
        call = hosted_call(llm, kbench.chats, policy["modelProxySlug"], root)
        summary = run_diagnostic(root, policy, call)
    except Exception as error:
        if root.exists():
            raise
        root.mkdir(parents=True, exist_ok=False)
        save_json(root / "policy.json", policy)
        save_json(root / "calls.json", [])
        summary = {"status": "failed", "callCount": 0, "diagnosticOnly": True, "benchmarkEligible": False,
                   "error": {"type": type(error).__name__, "message": str(error)[:1500]}}
        save_json(root / "summary.json", summary)
    save_json(root / "runtime.json", runtime)
    seal(root)
    return summary
