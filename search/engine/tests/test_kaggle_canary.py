"""Zero-network regression and corruption gates for the fresh hosted diagnostic."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from search.engine.kaggle_canary import POLICY_ID, run_diagnostic, seal, hosted_call, hosted_entry
from search.engine.kaggle_canary_evidence import check_evidence

SCHEMA = str(Path(__file__).resolve().parents[3] / 'schemas/aleph-run.schema.json')

class KaggleCanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'run'
        self.policy = {'policyId':POLICY_ID,'maxCalls':6,'modelVersion':'test-v1',
            'modelProxySlug':'test/model@rev','sourceCommit':'0'*40,'schemaPath':SCHEMA,'createdAt':'2026-11-27T00:00:00Z'}
        self.called = []

    def call(self, phase, prompt):
        self.called.append((phase,prompt))
        return {'output':'Give the product of seven and six, digits only.' if phase == 'proposal' else '42',
                'usage':{'inputTokens':11,'outputTokens':2,'inputCostNanodollars':0,'outputCostNanodollars':None}}

    def complete(self, call=None):
        summary = run_diagnostic(self.root, self.policy, call or self.call)
        seal(self.root)
        return summary

    def test_full_six_call_path_replays(self):
        summary = self.complete()
        self.assertEqual(summary['status'],'completed')
        self.assertEqual(len(self.called),6)
        self.assertEqual(summary['providerUsage'],{'inputTokens':66,'outputTokens':12,'inputCostNanodollars':0,'outputCostNanodollars':None})
        self.assertTrue(check_evidence(self.root)['ok'],check_evidence(self.root))
        control = json.loads((self.root/'control.json').read_text())
        self.assertNotEqual(summary['selectedCandidateId'],control['candidate']['candidateId'])

    def test_failure_closes_barrier_without_followup_calls(self):
        def call(phase,prompt):
            if len(self.called) == 2:
                self.called.append((phase,prompt))
                raise RuntimeError('provider rejected')
            return self.call(phase,prompt)
        summary = self.complete(call)
        self.assertEqual(summary['status'],'failed')
        self.assertEqual(len(self.called),3)
        self.assertEqual(summary['callCount'],3)
        self.assertTrue(check_evidence(self.root)['ok'])
        self.assertIsNone(summary['providerUsage']['inputTokens'])

    def test_blank_proposal_is_terminal_without_target_copy(self):
        self.complete(lambda phase,prompt:{'output':'','usage':{}})
        self.assertEqual(json.loads((self.root/'calls.json').read_text())[0]['output'],'')
        self.assertEqual(json.loads((self.root/'summary.json').read_text())['callCount'],1)

    def test_reusing_root_never_calls_provider(self):
        self.complete()
        with self.assertRaises(FileExistsError):
            run_diagnostic(self.root,self.policy,self.call)
        self.assertEqual(len(self.called),6)

    def test_invalid_policy_fails_before_call(self):
        for value in (True,5,7,'6'):
            with self.assertRaises(ValueError):
                run_diagnostic(self.root,{**self.policy,'maxCalls':value},self.call)
        self.assertEqual(self.called,[])

    def test_duplicate_seed_proposal_stops(self):
        r=self.complete(lambda phase,prompt:{'output':'Answer with only the integer that is six multiplied by seven.','usage':{}})
        self.assertEqual(r['callCount'],1)
        self.assertEqual(r['status'],'failed')

    def test_extra_file_is_rejected(self):
        self.complete(); (self.root/'extra').write_text('not declared')
        self.assertFalse(check_evidence(self.root)['ok'])

    def test_corrupt_call_and_resealed_hashes_still_fail(self):
        self.complete()
        calls=json.loads((self.root/'calls.json').read_text()); calls[2]['output']='41'
        (self.root/'calls.json').write_text(json.dumps(calls)); seal(self.root)
        self.assertFalse(check_evidence(self.root)['ok'])

    def test_symlink_is_rejected(self):
        self.complete(); (self.root/'link').symlink_to(self.root/'summary.json')
        self.assertFalse(check_evidence(self.root)['ok'])

    def test_manifest_duplicate_path_is_rejected(self):
        self.complete(); p=self.root/'files.json'; m=json.loads(p.read_text()); m['files'].append(m['files'][0]);p.write_text(json.dumps(m))
        self.assertFalse(check_evidence(self.root)['ok'])

    def test_preflight_rejects_unknown_transport_without_calls(self):
        r=hosted_entry(SimpleNamespace(model=self.policy['modelProxySlug']),SimpleNamespace(chats=None),self.root,self.policy)
        self.assertEqual(r['callCount'],0)
        self.assertTrue(check_evidence(self.root)['ok'])

    def test_transport_identity_retry_timeout_readback(self):
        class Client:
            def with_options(self,**kwargs):
                self.kwargs=kwargs;return SimpleNamespace(**kwargs)
        class OpenAI:
            model='test/model@rev'
            client=Client()
        OpenAI.__module__='kaggle_benchmarks.actors.proxy_openai'
        actor=OpenAI()
        fake_httpx=SimpleNamespace(HTTPTransport=lambda **kw: SimpleNamespace(**kw),
            Client=lambda **kw: SimpleNamespace(**kw))
        with patch.dict('sys.modules', {'httpx':fake_httpx}):
            hosted_call(actor,None,self.policy['modelProxySlug'],self.root)
        self.assertEqual(actor.client.max_retries,0)
        self.assertEqual(actor.client.timeout,90.0)
        with self.assertRaises(ValueError):
            hosted_call(actor,None,'wrong',self.root)

if __name__ == '__main__': unittest.main()
