#!/usr/bin/env python3
"""Prepare, dispatch once, inspect, and replay the private #107 diagnostic.

There is deliberately no command to retry, schedule a second run, or publish.
Use a fresh external output directory. Dispatch fixes the task slug permanently.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from search.engine.kaggle_canary import POLICY_ID, TOKENIZER, save_json
from search.engine.kaggle_canary_evidence import check_evidence

TASK = 'aleph-hybrid-107-20261127'
MODEL = 'anthropic/claude-haiku-4-5@20251001'
MODEL_VERSION = 'claude-haiku-4-5-20251001'
CLIENT = {'kaggle':'2.2.5','kagglesdk':'0.1.38','nbformat':'5.11.1','jupytext':'1.19.5'}
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).strip()


def sdk_dict(value):
    return json.loads(str(value))


def require_reserve(quota):
    balances = {x['refillPeriod']:x for x in quota['quotaBalances']}
    result = {}
    for period in ('DAILY','MONTHLY'):
        row = balances[period]
        total, used = row['totalQuotaAllowed'], row['quotaUsed']
        if any(type(x) not in (float,int) or not math.isfinite(x) or x < 0 for x in (total,used)):
            raise ValueError('quota must contain finite nonnegative numbers')
        reserve = max(2.0,total*.2) if period == 'DAILY' else total*.2
        # 0.10 USD is a conservative admission allowance, not measured cost.
        if total - used - .10 < reserve:
            raise ValueError(f'{period} free-allocation reserve is insufficient')
        result[period] = {'available':total-used,'minimumReserve':reserve,'admissionAllowanceUsd':.10}
    return result


def artifact_check(directory):
    plan = json.loads((directory/'prepared.json').read_text())
    for name, expected in plan['files'].items():
        if name not in {'source.zip','task.ipynb','policy.json'}:
            raise ValueError('unknown prepared artifact')
        if sha((directory/name).read_bytes()) != expected:
            raise ValueError(f'prepared artifact changed: {name}')
    if plan['task'] != TASK or plan['modelProxySlug'] != MODEL or plan['modelVersion'] != MODEL_VERSION:
        raise ValueError('prepared identity changed')
    return plan


def prepare(directory):
    if git('status','--porcelain'):
        raise ValueError('prepare requires an entirely clean source checkout')
    commit = git('rev-parse','HEAD')
    policy = {'policyId':POLICY_ID, 'createdAt':now(), 'maxCalls':6, 'maxOutputTokens':64,
        'modelProxySlug':MODEL,'modelVersion':MODEL_VERSION,'sourceCommit':commit,
        'sourceDirty':False,'schemaPath':'/tmp/aleph107-source/schemas/aleph-run.schema.json',
        'diagnosticOnly':True,'benchmarkEligible':False,'coordinateTokenizer':TOKENIZER,
        'transportRetries':0,'requestTimeoutSeconds':90,'cache':'uncached_httpx_transport',
        'discoverySeed':107,'confirmationSeed':108,'adaptiveOperatorRounds':0,
        'controlAccounting':'outer_envelope_control_excluded_from_engine_selection',
        'metricScope':'toy_exact_match_byte_length_literal_byte_leakage_one_sample',
        'compute':'cpu_default_no_accelerator_requested','paidOverageAuthorized':False}
    names = git('ls-files','search/engine','search/__init__.py','schemas/aleph-run.schema.json','LICENSE','NOTICE').splitlines()
    names = [x for x in names if x in {'LICENSE','NOTICE','schemas/aleph-run.schema.json','search/__init__.py'} or
             (x.endswith('.py') and '/tests/' not in x)]
    source = io.BytesIO()
    source_manifest = []
    with zipfile.ZipFile(source,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            data = (REPO/name).read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2026,11,27,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG | 0o644) << 16
            archive.writestr(info,data)
            source_manifest.append({'path':name,'bytes':len(data),'sha256':sha(data)})
    data = source.getvalue()
    policy['sourceArchiveSha256'] = sha(data)
    policy['sourceFiles'] = source_manifest
    code = f'''# Frozen source {commit}; private diagnostic only, no benchmark promotion.
import base64, hashlib, io, json, sys, zipfile
from pathlib import Path
import kaggle_benchmarks as kbench
_DATA = base64.b64decode({base64.b64encode(data).decode()!r})
_POLICY = json.loads({json.dumps(policy,sort_keys=True)!r})
assert hashlib.sha256(_DATA).hexdigest() == _POLICY['sourceArchiveSha256']
_ROOT = Path('/tmp/aleph107-source')
_ROOT.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(_DATA)) as _z:
    assert _z.namelist() == [r['path'] for r in _POLICY['sourceFiles']]
    for _r in _POLICY['sourceFiles']:
        _b = _z.read(_r['path'])
        assert len(_b) == _r['bytes'] and hashlib.sha256(_b).hexdigest() == _r['sha256']
        _p = _ROOT / _r['path']
        _p.parent.mkdir(parents=True,exist_ok=True)
        _p.write_bytes(_b)
sys.path.insert(0,str(_ROOT))
from search.engine.kaggle_canary import hosted_entry
assert Path(sys.modules[hosted_entry.__module__].__file__).resolve() == _ROOT / 'search/engine/kaggle_canary.py'

@kbench.task(name={TASK!r})
def aleph_hybrid_107(llm):
    result = hosted_entry(llm,kbench,Path('/kaggle/working/aleph107'),_POLICY)
    print(json.dumps(result,sort_keys=True))
    assert result['status'] == 'completed', 'Diagnostic stopped; inspect retained failure receipt; do not retry.'

aleph_hybrid_107.run(llm=kbench.llms[{MODEL!r}])
'''
    notebook = {'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},
        'cells':[{'cell_type':'code','execution_count':None,'id':'aleph107-source-v1','metadata':{},'outputs':[],'source':code.splitlines(keepends=True)}]}
    directory.mkdir(parents=True,exist_ok=False)
    (directory/'source.zip').write_bytes(data)
    save_json(directory/'policy.json',policy)
    save_json(directory/'task.ipynb',notebook)
    plan = {'schemaVersion':'aleph-kaggle-107-prepared/1','sourceCommit':commit,'sourceDirty':False,
        'createdAt':now(),'task':TASK,'modelProxySlug':MODEL,'modelVersion':MODEL_VERSION,'client':CLIENT,
        'files':{x:sha((directory/x).read_bytes()) for x in ('source.zip','task.ipynb','policy.json')}}
    save_json(directory/'prepared.json',plan)
    return plan


def authenticate():
    for name, expected in CLIENT.items():
        if importlib.metadata.version(name) != expected:
            raise ValueError(f'client runtime drift: {name}')
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi();api.authenticate();return api


def read_quota(api,client):
    from kagglesdk.models.types.model_proxy_api_service import ApiGetModelProxyQuotasRequest
    quota=sdk_dict(client.models.model_proxy_api_client.get_model_proxy_quotas(ApiGetModelProxyQuotasRequest()))
    result={'observedAt':now(),'modelProxy':quota,'accelerator':sdk_dict(api.quota_view())}
    try: result['admission']=require_reserve(quota)
    except (ValueError, KeyError, TypeError) as error: result['admissionError']=str(error)
    return result


def dispatch(directory):
    plan=artifact_check(directory)
    if (directory/'dispatch.json').exists():
        raise ValueError('one-shot journal exists; use status, never dispatch again')
    # Keep all retired Aleph schedules paused. Absence of a matching local file
    # is recorded rather than claimed as proof about unknown remote schedulers.
    import tomllib
    automations=[]
    for path in (Path.home()/'.codex/automations').glob('*/automation.toml'):
        row=tomllib.loads(path.read_text())
        if 'aleph' in json.dumps(row).lower():
            automations.append({'name':row.get('name'),'status':row.get('status')})
            if row.get('status') != 'PAUSED':
                raise ValueError('an Aleph automation is not paused')
    from requests.exceptions import HTTPError
    from kagglesdk.benchmarks.types.benchmark_tasks_api_service import (ApiBenchmarkTaskSlug,ApiGetBenchmarkTaskRequest,
        ApiCreateBenchmarkTaskRequest,BenchmarkTaskOptions,ApiTaskCreationValidationConfig,ApiValidationStage,BenchmarkTaskValidationStage)
    api=authenticate()
    with api.build_kaggle_client() as client:
        tasks=client.benchmarks.benchmark_tasks_api_client
        slug=ApiBenchmarkTaskSlug();slug.task_slug=TASK
        get=ApiGetBenchmarkTaskRequest();get.slug=slug
        try:
            existing=tasks.get_benchmark_task(get)
        except HTTPError as error:
            if error.response is None or error.response.status_code != 404:
                raise
        else:
            save_json(directory/'existing-task.json',sdk_dict(existing))
            raise ValueError('fixed task already exists; no further creation is allowed')
        before=read_quota(api,client)
        if 'admissionError' in before:
            save_json(directory/'quota-before.json',before)
            raise ValueError(before['admissionError'])
        for name in ('gpuQuota','tpuQuota'):
            if before['accelerator'].get(name,{}).get('isPayToScaleEnabled') is not False:
                raise ValueError('paid accelerator overage is not explicitly disabled')
        models=[sdk_dict(x) for x in api._fetch_all_benchmark_models(client)]
        selected=[x for x in models if x.get('version',{}).get('modelProxySlug')==MODEL]
        if len(selected)!=1:
            raise ValueError('exact catalog model not uniquely available')
        version=selected[0]['version']
        if version['slug']!=MODEL_VERSION or version.get('published') is not True or version.get('allowModelProxy') is not True or version.get('license',{}).get('agreementRequired'):
            raise ValueError('model catalog identity or availability drift')
        save_json(directory/'quota-before.json',before)
        save_json(directory/'model-catalog-selected.json',selected[0])
        save_json(directory/'automation-preflight.json',{'observedAt':now(),'matchingLocalSchedules':automations,'legacyControllerExecuted':False})
        request=ApiCreateBenchmarkTaskRequest();request.slug=TASK;request.text=(directory/'task.ipynb').read_text()
        options=BenchmarkTaskOptions();options.dataset_data_sources=[];request.options=options
        validation=ApiTaskCreationValidationConfig();stage=ApiValidationStage()
        stage.type=BenchmarkTaskValidationStage.BENCHMARK_TASK_VALIDATION_STAGE_DEFAULT_CANDIDATE
        stage.default_model_version_slug=MODEL_VERSION
        validation.validation_stages=[stage];request.validation_config=validation
        save_json(directory/'create-request-public.json',{'slug':TASK,'notebookSha256':plan['files']['task.ipynb'],
            'datasetDataSources':[],'validationStages':[{'type':stage.type.name,'defaultModelVersionSlug':MODEL_VERSION}]})
        journal={'schemaVersion':'aleph-kaggle-107-dispatch/1','task':TASK,'state':'dispatching','createdAt':now(),
            'sourceCommit':plan['sourceCommit'],'notebookSha256':plan['files']['task.ipynb'],'createAttempts':1,'automaticRetry':False}
        path=directory/'dispatch.json'
        with path.open('xb') as handle:
            import os
            handle.write((json.dumps(journal,sort_keys=True,indent=2)+'\n').encode());handle.flush();os.fsync(handle.fileno())
        descriptor=os.open(directory,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
        try:
            # Call directly: KaggleApi.with_retry is intentionally not used.
            response=tasks.create_benchmark_task(request)
            row=sdk_dict(response);save_json(directory/'create-response.json',row)
            journal.update(state='acknowledged',response=row,updatedAt=now())
        except BaseException as error:
            journal.update(state='outcome_unknown_do_not_retry',error={'type':type(error).__name__,'message':str(error)[:1500]},updatedAt=now())
            save_json(path,journal)
            raise
        save_json(path,journal)
        if row.get('isPublic') is not False or row.get('isBackingNotebookPublished') is True:
            raise ValueError('unexpected task visibility; stop and inspect')
        return journal


def status(directory, download=False):
    artifact_check(directory)
    journal=json.loads((directory/'dispatch.json').read_text())
    identity=journal.get('response',{}).get('slug')
    if not identity or not identity.get('versionNumber'):
        raise ValueError('missing exact acknowledged task version; reconcile fixed slug read-only')
    from kagglesdk.benchmarks.types.benchmark_tasks_api_service import (ApiBenchmarkTaskSlug,ApiGetBenchmarkTaskRequest,
        ApiListBenchmarkTaskRunsRequest,ApiDownloadBenchmarkTaskRunOutputRequest)
    api=authenticate()
    with api.build_kaggle_client() as client:
        tasks=client.benchmarks.benchmark_tasks_api_client
        slug=ApiBenchmarkTaskSlug();slug.owner_slug=identity['ownerSlug'];slug.task_slug=identity['taskSlug'];slug.version_number=identity['versionNumber']
        get=ApiGetBenchmarkTaskRequest();get.slug=slug;get.include_definition=True
        task=sdk_dict(tasks.get_benchmark_task(get))
        if task['slug']!=identity or task.get('isPublic') is not False:
            raise ValueError('exact task/version/visibility mismatch')
        runs_request=ApiListBenchmarkTaskRunsRequest();runs_request.task_slug=slug;runs_request.page_size=20
        runs=sdk_dict(tasks.list_benchmark_task_runs(runs_request))
        result={'observedAt':now(),'task':task,'runs':runs,'quota':read_quota(api,client)}
        save_json(directory/'status-latest.json',result)
        if runs.get('nextPageToken') or len(runs.get('runs',[]))>1:
            raise ValueError('unexpected multiple runs; stop without creating anything')
        for run in runs.get('runs',[]):
            if run.get('taskSlug')!=identity or run.get('modelVersionSlug')!=MODEL_VERSION:
                raise ValueError('run task/model identity mismatch')
            if download:
                if not run.get('endTime'):
                    raise ValueError('run is not terminal; inspect status later')
                target=directory/f"run-{run['id']}.zip"
                if not target.exists():
                    req=ApiDownloadBenchmarkTaskRunOutputRequest();req.run_id=run['id'];req.include_source=True
                    response=tasks.download_benchmark_task_run_output(req)
                    with target.open('xb') as handle:
                        total=0
                        for chunk in response.iter_content(chunk_size=1024*1024):
                            total+=len(chunk)
                            if total>MAX_ARCHIVE_BYTES: raise ValueError('run archive exceeds bound')
                            handle.write(chunk)
                result['download']={'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target.read_bytes())}
        save_json(directory/'status-latest.json',result)
        return result


def unpack_and_verify(directory, archive_path):
    plan=artifact_check(directory)
    destination=directory/'extracted'
    destination.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive_path) as archive:
        rows=archive.infolist()
        if len(rows)>512 or sum(x.file_size for x in rows)>MAX_ARCHIVE_BYTES:
            raise ValueError('archive file count/size exceeds bound')
        names=[x.filename for x in rows]
        if len(names)!=len(set(names)):
            raise ValueError('duplicate ZIP members')
        for row in rows:
            path=PurePosixPath(row.filename)
            if path.is_absolute() or '..' in path.parts or str(path) != row.filename.rstrip('/') or '\\' in row.filename or stat.S_ISLNK(row.external_attr>>16):
                raise ValueError('unsafe ZIP member')
        expected_code=json.loads((directory/'task.ipynb').read_text())['cells'][0]['source']
        source_proven=False
        for name in names:
            if name.endswith('__notebook_source__.ipynb') or name.endswith('__notebook__.ipynb'):
                notebook=json.loads(archive.read(name))
                code=[''.join(c['source']) for c in notebook.get('cells',[]) if c.get('cell_type')=='code']
                if code==[''.join(expected_code)]:source_proven=True
                (destination/Path(name).name).write_bytes(archive.read(name))
        if not source_proven:
            raise ValueError('downloaded notebook source differs from prepared exact source')
        members=[x for x in names if x.startswith('aleph107/') and not x.endswith('/')]
        if not members:
            raise ValueError('no hosted evidence root; raw archive retained for terminal failure inspection')
        for name in members:
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(name))
    report=check_evidence(destination/'aleph107')
    hosted_policy=json.loads((destination/'aleph107/policy.json').read_text())
    if hosted_policy!=json.loads((directory/'policy.json').read_text()):
        report['ok']=False;report['errors'].append('hosted policy differs from frozen local policy')
    report.update(sourceCommit=plan['sourceCommit'],exactNotebookSourceReadback=source_proven,archiveSha256=sha(archive_path.read_bytes()))
    save_json(directory/'independent-replay.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','dispatch','status','download','verify']);p.add_argument('--directory',type=Path,required=True);p.add_argument('--archive',type=Path)
    a=p.parse_args();directory=a.directory.resolve()
    if a.command=='prepare':result=prepare(directory)
    elif a.command=='dispatch':result=dispatch(directory)
    elif a.command in ('status','download'):result=status(directory,a.command=='download')
    else:
        if not a.archive:p.error('verify requires --archive')
        result=unpack_and_verify(directory,a.archive)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result.get('ok',True) else 1

if __name__=='__main__':raise SystemExit(main())
