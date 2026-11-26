"""Read-only closed-world replay of one hosted diagnostic, with no model runtime."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from .verify import verify_bundle


def check_evidence(root: Path) -> dict:
    root = Path(root)
    errors = []
    summary = {}
    calls = []
    def fail(message):
        errors.append(message)
    try:
        manifest = json.loads((root / 'files.json').read_text())
        if manifest.get('schemaVersion') != 'aleph-kaggle-107-files/1':
            raise ValueError('file manifest schema mismatch')
        expected = {}
        for row in manifest['files']:
            path = row['path']
            posix = PurePosixPath(path)
            if not path or posix.is_absolute() or '..' in posix.parts or str(posix) != path or path == 'files.json' or path in expected:
                raise ValueError('unsafe or duplicate manifest path')
            expected[path] = row
        actual = {}
        for path in root.rglob('*'):
            if path.is_symlink():
                raise ValueError('symlink in evidence')
            if path.is_file() and path != root / 'files.json':
                content = path.read_bytes()
                actual[path.relative_to(root).as_posix()] = {'bytes':len(content), 'sha256': hashlib.sha256(content).hexdigest()}
        if set(expected) != set(actual):
            fail('closed-world file set mismatch')
        for path, value in actual.items():
            if path in expected and any(value[k] != expected[path].get(k) for k in ('bytes','sha256')):
                fail(f'file hash/size mismatch: {path}')
        policy = json.loads((root / 'policy.json').read_text())
        summary = json.loads((root / 'summary.json').read_text())
        calls = json.loads((root / 'calls.json').read_text())
        if policy.get('policyId') != 'aleph-kaggle-hybrid-107/2026-11-27' or policy.get('maxCalls') != 6:
            fail('policy identity mismatch')
        if summary.get('status') not in {'completed','failed'}:
            fail('unknown terminal summary state')
        if summary.get('diagnosticOnly') is not True or summary.get('benchmarkEligible') is not False:
            fail('diagnostic publication flags changed')
        if len(calls) > 6 or summary.get('callCount') != len(calls):
            fail('call bound or summary mismatch')
        failed = False
        for i, row in enumerate(calls, 1):
            if row.get('index') != i or failed:
                fail('call order or failure barrier violated')
            failed = row.get('state') != 'completed'
        totals = {}
        for name in ('inputTokens','outputTokens','inputCostNanodollars','outputCostNanodollars'):
            values = [r.get('usage', {}).get(name) for r in calls]
            totals[name] = sum(values) if values and all(type(x) is int and x >= 0 for x in values) else None
        if summary.get('providerUsage') != totals and calls:
            fail('provider arithmetic mismatch')
        if (root / 'envelope-ledger.json').exists():
            outer = json.loads((root / 'envelope-ledger.json').read_text())
            if outer.get('calls') != len(calls) or outer.get('totals') != totals:
                fail('outer ledger mismatch')
        if summary.get('status') == 'completed':
            if len(calls) != 6 or [r.get('phase') for r in calls] != ['proposal','discovery-control','discovery','discovery','discovery','confirmation'] or failed:
                fail('successful path is not exactly six complete isolated calls')
            report = verify_bundle(root / 'bundle')
            if not report.ok:
                fail('canonical replay: ' + '; '.join(report.errors))
            if summary.get('streamDigest') != report.stream_digest:
                fail('stream identity differs')
            if summary.get('confirmationOutcome') != report.confirmation_outcome:
                fail('confirmation outcome differs')
            control = json.loads((root / 'control.json').read_text())
            if control.get('selectionEligible') is not False or control['callIndex'] != 2:
                fail('control inclusion policy mismatch')
            if summary.get('selectedCandidateId') == control['candidate']['candidateId']:
                fail('explicit reconstruction selected')
            linked = set()
            for path in (root / 'bundle/blobs').rglob('*'):
                if not path.is_file():
                    continue
                try:
                    blob = json.loads(path.read_text())
                except (ValueError, UnicodeError):
                    continue
                output = blob.get('outputs') if isinstance(blob,dict) else None
                if not isinstance(output,dict) or 'callIndex' not in output:
                    continue
                index = output['callIndex']
                if type(index) is not int or not 3 <= index <= 6 or index in linked:
                    fail('invalid or repeated evaluation call linkage')
                    continue
                linked.add(index)
                row = calls[index-1]
                if output.get('text') != row.get('output') or blob.get('candidateId') != row.get('candidateId') or blob.get('requestId') != row.get('requestId'):
                    fail('raw call and engine receipt differ')
                literal = Counter(row['prompt'].encode())
                target = Counter(b'42')
                metrics = {'fit':float(row['output'].strip() == '42'), 'stability':1.0,
                    'compression':round(2 / (2 + len(row['prompt'].encode())),6),
                    'leakage':round(sum(min(n,literal[k]) for k,n in target.items())/2,6)}
                if blob.get('metrics') != metrics:
                    fail('metric replay differs from raw calls')
                resource = blob.get('resourceUse',{})
                for key in ('inputTokens','outputTokens'):
                    if resource.get(key) != row['usage'].get(key):
                        fail('provider usage and canonical ledger receipt differ')
            if linked != {3,4,5,6}:
                fail('incomplete canonical call linkage')
    except (OSError, ValueError, KeyError, TypeError) as error:
        fail(f'{type(error).__name__}: {error}')
    return {'schemaVersion':'aleph-kaggle-107-replay/1','ok':not errors,'errors':errors,
            'modelCalls':0, 'hostedStatus':summary.get('status'), 'hostedCallCount':len(calls),
            'confirmationOutcome':summary.get('confirmationOutcome'), 'scope':'diagnostic_only_not_benchmark_eligibility'}
