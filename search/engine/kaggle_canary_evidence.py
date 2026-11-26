"""Read-only closed-world replay of one hosted diagnostic, with no model runtime."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from .verify import verify_bundle


def replay_metrics(prompt: str, output: str) -> dict:
    literal = Counter(prompt.encode())
    target = Counter(b'42')
    return {'fit':float(output.strip() == '42'), 'stability':1.0,
        'compression':round(2 / (2 + len(prompt.encode())),6),
        'leakage':round(sum(min(n,literal[k]) for k,n in target.items())/2,6)}


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
        phases = ['proposal','discovery-control','discovery','discovery','discovery','confirmation']
        for i, row in enumerate(calls, 1):
            if type(row.get('index')) is not int or row.get('index') != i or failed or i > len(phases) or row.get('phase') != phases[i-1]:
                fail('call order, phase or failure barrier violated')
            if row.get('state') not in {'completed','failed'}:
                fail('call has no terminal state')
            failed = row.get('state') != 'completed'
        if 'completedCalls' in summary and summary['completedCalls'] != sum(row.get('state') == 'completed' for row in calls):
            fail('completed call count mismatch')
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
        if summary.get('status') == 'completed' and (len(calls) != 6 or failed):
            fail('successful path is not exactly six complete isolated calls')
        completed_evaluations = {r['index'] for r in calls if r.get('state') == 'completed' and r['index'] >= 3}
        has_bundle = (root / 'bundle').is_dir()
        if not has_bundle and (summary.get('status') == 'completed' or completed_evaluations or summary.get('streamDigest')):
            fail('canonical bundle is missing')
        if len(calls) >= 2 and calls[1].get('state') == 'completed':
            control = json.loads((root / 'control.json').read_text())
            candidate = control['candidate']
            if (control.get('selectionEligible') is not False or control.get('callIndex') != 2
                    or candidate.get('candidateRole') != 'explicit_reconstruction'
                    or candidate.get('candidateId') != calls[1].get('candidateId')
                    or candidate.get('messages') != [{'role':'user','content':calls[1]['prompt']}]):
                fail('control identity or inclusion policy mismatch')
            if control.get('metrics') != replay_metrics(calls[1]['prompt'], calls[1]['output']):
                fail('control metric replay differs from raw call')
            if summary.get('selectedCandidateId') == candidate['candidateId']:
                fail('explicit reconstruction selected')
        if has_bundle:
            # Partial failures still contain completed evaluations and canonical
            # artifacts. Replay those rather than trusting freshly resealed hashes.
            report = verify_bundle(root / 'bundle')
            if not report.ok:
                fail('canonical replay: ' + '; '.join(report.errors))
            if ('streamDigest' in summary or summary.get('status') == 'completed') and summary.get('streamDigest') != report.stream_digest:
                fail('stream identity differs')
            if ('confirmationOutcome' in summary or summary.get('status') == 'completed') and summary.get('confirmationOutcome') != report.confirmation_outcome:
                fail('confirmation outcome differs')
            linked = set()
            proposals = 0
            for path in (root / 'bundle/blobs').rglob('*'):
                if not path.is_file():
                    continue
                try:
                    blob = json.loads(path.read_text())
                except (ValueError, UnicodeError):
                    continue
                if isinstance(blob,dict) and blob.get('adapter',{}).get('role') == 'proposal' and 'candidates' in blob:
                    proposals += 1
                    candidates = blob['candidates']
                    if (len(candidates) != 4 or not calls or calls[0].get('state') != 'completed'
                            or candidates[-1].get('messages') != [{'role':'user','content':calls[0]['output'].strip()}]):
                        fail('raw proposal and canonical seed differ')
                    for key in ('inputTokens','outputTokens'):
                        if blob.get('resourceUse',{}).get(key) != calls[0].get('usage',{}).get(key):
                            fail('proposal usage and canonical receipt differ')
                output = blob.get('outputs') if isinstance(blob,dict) else None
                if not isinstance(output,dict) or 'callIndex' not in output:
                    continue
                index = output['callIndex']
                if type(index) is not int or index not in completed_evaluations or index in linked:
                    fail('invalid or repeated evaluation call linkage')
                    continue
                linked.add(index)
                row = calls[index-1]
                if output.get('text') != row.get('output') or blob.get('candidateId') != row.get('candidateId') or blob.get('requestId') != row.get('requestId'):
                    fail('raw call and engine receipt differ')
                metrics = replay_metrics(row['prompt'], row['output'])
                if blob.get('metrics') != metrics:
                    fail('metric replay differs from raw calls')
                resource = blob.get('resourceUse',{})
                for key in ('inputTokens','outputTokens'):
                    if resource.get(key) != row['usage'].get(key):
                        fail('provider usage and canonical ledger receipt differ')
            if proposals != 1:
                fail('canonical proposal receipt is missing or repeated')
            if linked != completed_evaluations:
                fail('incomplete canonical call linkage')
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        fail(f'{type(error).__name__}: {error}')
    return {'schemaVersion':'aleph-kaggle-107-replay/1','ok':not errors,'errors':errors,
            'modelCalls':0, 'hostedStatus':summary.get('status'), 'hostedCallCount':len(calls),
            'confirmationOutcome':summary.get('confirmationOutcome'), 'scope':'diagnostic_only_not_benchmark_eligibility'}
