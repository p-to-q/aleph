"""Preparation, budget admission and archive-negative checks, no Kaggle calls."""
import ast
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

REPO=Path(__file__).resolve().parents[3]
SPEC=importlib.util.spec_from_file_location('kaggle_hybrid_once',REPO/'scripts/kaggle-hybrid-once.py')
once=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(once)

class KaggleOnceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'prepared'

    def prepare(self):
        names=[x.relative_to(REPO).as_posix() for x in (REPO/'search/engine').rglob('*.py') if '/tests/' not in str(x)]
        names+=['LICENSE','schemas/aleph-run.schema.json']
        def git(*args):
            return '' if args[0]=='status' else '0'*40 if args[0]=='rev-parse' else '\n'.join(names)
        with patch.object(once,'git',git):
            return once.prepare(self.root)

    def listing(self, pages):
        requests=[]
        class Result:
            def __init__(self, row): self.row=row
            def __str__(self): return json.dumps(self.row)
        def read(request):
            requests.append(request)
            return Result(pages[len(requests)-1])
        result=once.require_task_absence(SimpleNamespace(list_benchmark_tasks=read),'owner',SimpleNamespace)
        return result,requests

    def test_owned_listing_absence_requires_complete_pagination(self):
        def row(name): return {'slug':{'ownerSlug':'owner','taskSlug':name}}
        result,requests=self.listing([
            {'tasks':[row('old')],'totalResults':2,'nextPageToken':'page2'},
            {'tasks':[row('other')],'totalResults':2,'nextPageToken':''}])
        self.assertTrue(result['absent'])
        self.assertEqual([r.page_token for r in requests],['','page2'])
        self.assertTrue(all(r.owner_slug=='owner' and r.page_size==100 for r in requests))
        result,_=self.listing([{'tasks':[],'totalResults':0,'nextPageToken':''}])
        self.assertTrue(result['absent'])

    def test_owned_listing_never_admits_existing_or_incomplete_state(self):
        def row(name,owner='owner'): return {'slug':{'ownerSlug':owner,'taskSlug':name}}
        cases=[
            [{'tasks':[row(once.TASK)],'totalResults':1,'nextPageToken':''}],
            [{'tasks':[],'totalResults':1,'nextPageToken':''}],
            [{'tasks':[row('a','other')],'totalResults':1,'nextPageToken':''}],
            [{'tasks':[row('a'),row('a')],'totalResults':2,'nextPageToken':''}],
            [{'tasks':[row('a')],'totalResults':True,'nextPageToken':''}],
            [{'tasks':[row('a')],'totalResults':1}],
            [{'tasks':[row('a')],'totalResults':2,'nextPageToken':'p2'},
             {'tasks':[row('b')],'totalResults':3,'nextPageToken':''}],
            [{'tasks':[row('a')],'totalResults':3,'nextPageToken':'p2'},
             {'tasks':[row('b')],'totalResults':3,'nextPageToken':'p2'}],
        ]
        for pages in cases:
            with self.subTest(pages=pages),self.assertRaises(ValueError): self.listing(pages)

    def test_owned_listing_access_error_propagates(self):
        def denied(request): raise PermissionError('403 denied')
        with self.assertRaises(PermissionError):
            once.require_task_absence(SimpleNamespace(list_benchmark_tasks=denied),'owner',SimpleNamespace)

    def test_creation_visibility_never_labels_unknown_as_private(self):
        keys=('isPublic','isBackingNotebookPublished','areRunArtifactsPublic')
        self.assertEqual(once.creation_visibility({}), 'pending_readback')
        private=dict.fromkeys(keys,False)
        self.assertEqual(once.creation_visibility(private), 'private')
        for key in keys:
            self.assertEqual(once.creation_visibility({**private,key:None}), 'pending_readback')
            for value in (True,0,'false'):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    once.creation_visibility({**private,key:value})

    def test_prepared_notebook_binds_exact_source_tree(self):
        plan=self.prepare()
        self.assertEqual(once.artifact_check(self.root),plan)
        notebook=json.loads((self.root/'task.ipynb').read_text())
        ast.parse(''.join(notebook['cells'][0]['source']))
        policy=json.loads((self.root/'policy.json').read_text())
        with zipfile.ZipFile(self.root/'source.zip') as archive:
            self.assertEqual(archive.namelist(),[r['path'] for r in policy['sourceFiles']])
            self.assertIn('search/engine/kaggle_canary.py',archive.namelist())
            for row in policy['sourceFiles']:
                self.assertEqual(once.sha(archive.read(row['path'])),row['sha256'])

    def test_mutated_notebook_is_rejected_before_authentication(self):
        self.prepare();(self.root/'task.ipynb').write_text('{}')
        with patch.object(once,'authenticate',side_effect=AssertionError('must not authenticate')):
            with self.assertRaises(ValueError):once.dispatch(self.root)

    def test_exclusive_existing_journal_blocks_dispatch(self):
        self.prepare();(self.root/'dispatch.json').write_text('{}')
        with patch.object(once,'authenticate',side_effect=AssertionError('must not authenticate')):
            with self.assertRaises(ValueError):once.dispatch(self.root)

    def test_quota_reserve_rejects_exhaustion_nan_and_unknown(self):
        quota={'quotaBalances':[{'refillPeriod':'DAILY','quotaUsed':0,'totalQuotaAllowed':10},
                                {'refillPeriod':'MONTHLY','quotaUsed':0,'totalQuotaAllowed':100}]}
        self.assertEqual(once.require_reserve(quota)['DAILY']['minimumReserve'],2)
        for value in (9,float('nan'),None,True):
            quota['quotaBalances'][0]['quotaUsed']=value
            with self.assertRaises((ValueError,TypeError)):once.require_reserve(quota)

    def test_dirty_source_is_rejected(self):
        with patch.object(once,'git',return_value=' M changed'):
            with self.assertRaises(ValueError):once.prepare(self.root)
        self.assertFalse(self.root.exists())

    def test_archive_traversal_rejected_without_writing_escape(self):
        self.prepare();target=self.root/'bad.zip'
        with zipfile.ZipFile(target,'w') as archive:archive.writestr('../escape','bad')
        with self.assertRaises(ValueError):once.unpack_and_verify(self.root,target)
        self.assertFalse((self.root.parent/'escape').exists())

    def test_archive_source_mismatch_rejected(self):
        self.prepare();target=self.root/'bad.zip'
        with zipfile.ZipFile(target,'w') as archive:
            archive.writestr('__notebook_source__.ipynb',json.dumps({'cells':[{'cell_type':'code','source':['print("different")']}]}))
        with self.assertRaises(ValueError):once.unpack_and_verify(self.root,target)

if __name__=='__main__':unittest.main()
