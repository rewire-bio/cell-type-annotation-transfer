#!/usr/bin/env python3
"""Explicitly approved M5-only canonical/independent repair; ordinary reproduction stays fresh."""
from __future__ import annotations
import argparse
import ast
import csv
import fcntl
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import pickle
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import resource_guard as RG
import result_manifest as RM

METHODS=('M1','M2','M3','M4','M6')
VERSION='m5-seed0-v2'
ORIGINAL_RUN='29879296d87343898100c190308744a1'
FRESH_PARENT='78542e9d412548edbfe42b38d452f7a8'
PRIOR_SECONDS=7085.069447749978
CAP_SECONDS=53970.0
LIMITS={'fit':4800,'predict':1200,'cite_predict':1800,'score':7200,'protein':900,'compare':1200,'paper':1800,'env':1800}

class Stop(RuntimeError): pass

def need(value,message):
    if not value: raise Stop(message)

def sha(p): return RM.sha256_path(p)
def load(p): return json.loads(Path(p).read_text())
def dump(p,value): RM.write_json(Path(p),value)

def inventory_payload_sha256(inventory):
    """Canonical approval payload; harness separately binds complete inventory bytes."""
    value=json.loads(json.dumps(inventory))
    approval=value.pop('approval',{})
    value.get('source_controls',{}).pop(approval.get('path',''),None)
    for key in ('source_inventory_sha256','parent_config_path','parent_source_manifest_sha256',
                'canonical_manifest_sha256'):
        value.pop(key,None)
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def ordinary_output(path):
    raw=Path(path).absolute()
    need(not raw.is_symlink() and not any(p.is_symlink() for p in raw.parents),'Output aliases/ancestor links refused')
    return raw.resolve()


def inside(root,relative):
    p=Path(relative)
    need(not p.is_absolute() and '..' not in p.parts and bool(p.parts),'Unsafe study-relative path')
    result=root/p
    need(not result.is_symlink(),'Adoption/reference links are refused; use physical files')
    need(result.resolve().is_relative_to(root.resolve()),'Path escapes declared source root')
    need(not any(x.is_symlink() for x in result.parents if x != root and x.is_relative_to(root)),'Link traversal refused')
    return result


def validate_seed_delta(original,current):
    old,new=ast.parse(original),ast.parse(current)
    nodes=[n for n in new.body if isinstance(n,ast.ClassDef) and n.name=='CellTypistRetrained']
    need(len(nodes)==1,'M5 class identity differs')
    fit=[n for n in nodes[0].body if isinstance(n,ast.FunctionDef) and n.name=='fit']
    need(len(fit)==1,'M5 fit identity differs')
    calls=[n for n in ast.walk(fit[0]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
           and isinstance(n.func.value,ast.Name) and n.func.value.id=='celltypist' and n.func.attr=='train']
    need(len(calls)==1,'M5 training call identity differs')
    seed=[k for k in calls[0].keywords if k.arg=='random_state']
    need(len(seed)==1 and isinstance(seed[0].value,ast.Constant) and type(seed[0].value.value) is int
         and seed[0].value.value==0,'M5 estimator seed must be exactly zero')
    calls[0].keywords.remove(seed[0])
    need(ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False),
         'Source delta changes unaffected classes/helpers or M5 behavior beyond seed')


def validate_identity(repo,cfg):
    ident=cfg['identity']
    for relative,digest in ident['scientific_files'].items():
        p=inside(repo,relative)
        need(p.is_file() and sha(p)==digest,f'Scientific source/config/dependency/data changed: {relative}')
    original=inside(repo,ident['original_methods'])
    current=inside(repo,'companion/src/celltransfer/methods.py')
    need(sha(original)==ident['original_methods_sha256'],'Original methods record changed')
    need(sha(current)==ident['seeded_methods_sha256'],'Seeded methods bytes changed')
    validate_seed_delta(original.read_text(),current.read_text())


def verify_inventory(source,inventory):
    files=inventory['adopted_files']
    need(files,'Empty adoption inventory')
    for relative,digest in files.items():
        need(not any(relative==prefix.rstrip('/') or relative.startswith(prefix.rstrip('/')+'/') for prefix in inventory.get('forbidden_adoption_prefixes',[])),'Forbidden prior output adoption')
        parts=Path(relative).parts
        need(not any('M5' in p or p in ('score','protein','compare','arms') or p.startswith(('score-','protein-','compare-')) for p in parts),
             f'Forbidden M5/scoring/protein/assembly adoption: {relative}')
        p=inside(source,relative)
        need(p.is_file() and sha(p)==digest,f'Adopted input missing/changed: {relative}')
    for category in ('source_controls','readonly_references'):
        for relative,digest in inventory.get(category,{}).items():
            p=inside(source,relative)
            need(p.is_file() and sha(p)==digest,f'Control/read-only reference missing/changed: {relative}')
    layout=inventory['layout']
    expected={f'{arm}:{m}' for arm in ('A','B') for m in METHODS}
    need(set(layout['fits'])==expected and set(layout['predictions'])==expected,'Adopt exactly the ten unaffected fits/prediction groups')
    need(set(layout['cite_predictions'])==set(METHODS),'Adopt exactly five unaffected CITE prediction groups')
    for category in ('fits','predictions','cite_predictions'):
        for prefix in layout[category].values():
            need(any(p.startswith(prefix.rstrip('/')+'/') for p in files),f'Layout role not bound by inventory: {prefix}')
            directory=inside(source,prefix)
            need(directory.is_dir(),f'Missing role directory: {prefix}')
            # Every source file in a role must be selected. This refuses hidden M5 links/unlisted additions.
            for p in directory.rglob('*'):
                need(not p.is_symlink(),'Unlisted/symbolic role entry refused')
                if p.is_file(): need(p.relative_to(source).as_posix() in files,'Unlisted role file refused')
    for role in ('data','cite'):
        prefix=layout[role]
        need(any(p.startswith(prefix.rstrip('/')+'/') for p in files),f'Missing hash-bound {role}')
    for role in ('data','cite'):
        directory=inside(source,layout[role])
        for p in directory.rglob('*'):
            need(not p.is_symlink(),'Data/CITE link traversal refused')
            if p.is_file():need(p.relative_to(source).as_posix() in files,'Unlisted data/CITE file refused')
    need(layout['d03_features'] in inventory['readonly_references'],'D03 must be a hash-bound reference only')
    for relative in layout['checkpoint_sidecars'].values():
        need(relative in files,'M6 checkpoint sidecar not hash bound')
    for relative in layout['equality_references'].values():
        need(relative in inventory['readonly_references'],'Equality reference must be read-only and hash bound')


class Ledger:
    def __init__(self,path,repair_id): self.path,self.repair_id=Path(path),repair_id
    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.with_suffix('.m5-lock').open('a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            doc=load(self.path) if self.path.exists() else {}
            state=doc.setdefault('m5_seed_repair',{'repair_id':self.repair_id,'fit_invocations':[],
                                                 'score_invocations':[],'driver_stage_seconds':{}})
            need(state['repair_id']==self.repair_id,'Shared repair ledger identity differs')
            yield state
            dump(self.path,doc)
    def reserve(self,kind,stage,arm=None):
        need(kind in ('fit','score'),'Unknown reservation kind')
        with self.locked() as state:
            records=state[kind+'_invocations']
            need(len(records)<(4 if kind=='fit' else 2),f'{kind} invocation cap exhausted')
            need(not any(x['stage']==stage and x.get('arm')==arm for x in records),'Stage/arm already invoked; retry refused')
            if stage=='reproduction':
                need(len([x for x in state['fit_invocations'] if x['stage']=='canonical'])==2,'Canonical fits must precede independent fits')
            records.append({'stage':stage,'arm':arm,'reserved_utc':RG.utc(),'status':'reserved before invocation'})
    def charge(self,stage,seconds):
        with self.locked() as state:
            need(math.isfinite(seconds) and seconds>=0,'Invalid runtime charge')
            state['driver_stage_seconds'][stage]=max(seconds,state['driver_stage_seconds'].get(stage,0))
            need(PRIOR_SECONDS+sum(state['driver_stage_seconds'].values())<=CAP_SECONDS,'Cumulative runtime exhausted')


def equal_non_m5(new,reference):
    def rows(path):
        with Path(path).open(newline='') as f:
            return [r for r in csv.DictReader(f) if r.get('method')!='M5']
    for name in ('summary_test.csv','thresholds_validation.csv','cell_counts.csv','bootstrap_ids.csv'):
        a,b=rows(new/name),rows(reference[name])
        need(sorted(json.dumps(r,sort_keys=True) for r in a)==sorted(json.dumps(r,sort_keys=True) for r in b),
             f'Non-M5 equality failed: {name}')
    need(sha(new/'bootstrap_weights.npy')==sha(reference['bootstrap_weights.npy']),'T1 bootstrap weights differ')


class Repair:
    def __init__(self,repo,cfg,config_path,output,runner=None,clock=time.monotonic,preflight=False):
        self.repo,self.cfg,self.output=Path(repo).resolve(),cfg,ordinary_output(output)
        self.clock=clock; self.started=clock(); self.runner=runner or self.guarded
        env=os.environ
        need(env.get('RESEARCH_ADOPTION_STAGE') in ('canonical','reproduction'),'Explicit harness adoption stage required')
        self.stage=env['RESEARCH_ADOPTION_STAGE']
        self.source=Path(env['RESEARCH_ADOPTION_SOURCE_ROOT']).resolve()
        self.inventory_path=Path(env['RESEARCH_ADOPTION_INVENTORY'])
        self.inventory=load(self.inventory_path)
        self.approval_path=Path(env['RESEARCH_ADOPTION_APPROVAL'])
        self.approval=load(self.approval_path)
        self.prior=float(env['RESEARCH_ADOPTION_PRIOR_SECONDS'])
        need(cfg.get('execution_ready') is True,'Draft repair configuration is not active')
        need(self.inventory['stage']==self.stage and self.inventory['parent_id']==FRESH_PARENT,'Wrong repair parent/stage')
        a=self.approval
        need(sha(self.approval_path)==self.inventory['approval']['sha256'],'Approval record hash differs')
        need(a.get('status')=='approved' and a.get('repair_id')==self.inventory['repair_id']
             and a.get('protocol_hash')==self.inventory['target_protocol_hash']
             and a.get('option')=='R' and a.get('user_reply') and a.get('approved_by'),'Explicit scientific Option R approval required')
        required={'version':VERSION,'original_run_id':ORIGINAL_RUN,'parent_reproduction_id':FRESH_PARENT,
                  'fit_invocations':4,'score_invocations':2,'worker_call_cap':24,
                  'total_seconds':CAP_SECONDS,'prior_seconds':PRIOR_SECONDS,'ledger_choice':'existing-cumulative'}
        need(all(a.get(k)==v for k,v in required.items()),'Approval changes design, invocation counts or ledger')
        need(a['proposal_sha256']==sha(inside(self.repo,cfg['proposal'])) and
             a['execution_note_sha256']==sha(inside(self.repo,cfg['execution_note'])) and
             a['repair_config_sha256']==sha(config_path),'Approval plan/config binding differs')
        for key in ('target_protocol_hash','target_science_hash'):
            need(a[key]==self.inventory[key],'Target approval/source identity differs')
        need(a['inventory_payload_sha256'][self.stage]==inventory_payload_sha256(self.inventory),'Inventory approval binding differs')
        need(cfg['guard']=={'threads':4,'mem_limit_gib':12,'storage_cap_gib':7} and cfg['step_ceilings_s']==LIMITS,
             'Resources/step ceilings changed')
        need(cfg['stage_seconds']=={'canonical':21900,'reproduction':26700} and cfg['version']==VERSION,'Repair stage/config changed')
        need(math.isfinite(self.prior) and PRIOR_SECONDS<=self.prior<CAP_SECONDS,'Invalid prior runtime charge')
        need(not self.output.is_symlink() and (not self.output.exists() or (self.output.is_dir() and not any(self.output.iterdir()))),'Repair output must be new or empty ordinary harness directory')
        validate_identity(self.repo,cfg); verify_inventory(self.source,self.inventory)
        runtime_ledger=Path(env['RESEARCH_ADOPTION_LEDGER'])
        self.ledger=Ledger(runtime_ledger.with_name(runtime_ledger.stem+'.m5-invocations.json'),self.inventory['repair_id'])
        if not preflight:self.output.mkdir(parents=True,exist_ok=True)
        self.receipt={'schema_version':1,'version':VERSION,'stage':self.stage,'status':'running',
                      'parent_run':ORIGINAL_RUN,'parent_reproduction':FRESH_PARENT,'mode':'R' if self.stage=='canonical' else 'F',
                      'scope':'approved selective adoption; only M5 recomputed independently',
                      'approval_sha256':sha(self.approval_path),'inventory_sha256':sha(self.inventory_path),
                      'prior_seconds':self.prior,'adopted_files':self.inventory['adopted_files'],'steps':[]}
        self.env={'UV_CACHE_DIR':str(self.repo/'.cache-study/uv'),'UV_PROJECT_ENVIRONMENT':str(self.repo/'.venv'),
                  'HF_HOME':str(self.repo/'.cache-study/hf'),'MPLCONFIGDIR':str(self.repo/'.cache-study/mpl'),
                  'PYTHONDONTWRITEBYTECODE':'1','PYTHONWARNINGS':'ignore','PYTHONOPTIMIZE':'0'}
        self.python=str(self.repo/'.venv/bin/python')
        self.step_used={};self.paper_used=0

    def save(self):
        elapsed=self.clock()-self.started
        self.ledger.charge(self.stage,elapsed)
        self.receipt.update(wall_seconds=elapsed,cumulative_seconds=self.prior+elapsed)
        dump(self.output/'generation_receipt.json',self.receipt)
    def left(self):
        elapsed=self.clock()-self.started
        remaining=min(CAP_SECONDS-self.prior-elapsed,self.cfg['stage_seconds'][self.stage]-elapsed)
        need(remaining>0,'Stage/cumulative budget exhausted')
        return remaining
    def guarded(self,argv,name,timeout):
        return RG.run_guarded(argv,attempt_root=self.output/'attempts',name=name,timeout=timeout,
            extra_env=self.env,cwd=self.repo,mem_limit=12*RG.GiB,swap_growth_limit=4*RG.GiB,
            disk_start_min=(4 if name.endswith('_fit') or name.endswith('_cite') else 3)*RG.GiB,
            disk_run_min=int(1.5*RG.GiB),storage_cap=7*RG.GiB,threads=4,disk_path=self.repo,
            cap_paths=[self.repo/x for x in ('.venv','.cache-study','runs','results','paper/build','.tools')]+[self.output],time_l=True)
    def step(self,name,kind,argv_fn):
        need(kind!='fit' or name in ('A_M5_fit','B_M5_fit'),'Non-M5 fitting refused')
        need(not name.endswith('_fit') or kind=='fit','Fit step must reserve fit budget')
        if kind=='fit':self.ledger.reserve('fit',self.stage,name[0])
        if kind=='score':self.ledger.reserve('score',self.stage)
        attempts=1 if kind in ('fit','score') else 2
        for attempt in range(1,attempts+1):
            timeout=min(self.left(),LIMITS[kind]-self.step_used.get(name,0))
            if kind=='paper':timeout=min(timeout,1800-self.paper_used)
            need(timeout>0,'Step/paper budget exhausted')
            out=self.output/VERSION/'out'/f'{name}-{attempt}';out.parent.mkdir(parents=True,exist_ok=True)
            argv=argv_fn(out);started=self.clock();rec=self.runner(argv,name,timeout);elapsed=self.clock()-started
            self.step_used[name]=self.step_used.get(name,0)+elapsed
            if kind=='paper':self.paper_used+=elapsed
            self.receipt['steps'].append({'name':name,'kind':kind,'attempt':attempt,'command':argv,'out_dir':str(out),
                'status':rec['status'],'returncode':rec.get('returncode'),'wall_seconds':elapsed,'timeout_s':timeout,
                'executed':True,'provenance':'recomputed seed-controlled M5 repair'})
            self.save()
            if rec['status']=='ok':return out
            need(rec['status'] in RG.INFRA_STATUSES and attempt<attempts,'Scientific step failed; preserve and stop')
        raise Stop('Step allowance exhausted')
    def copy_inputs(self):
        dest=self.output/VERSION/'adopted';dest.mkdir(parents=True)
        for relative,digest in self.inventory['adopted_files'].items():
            self.left();source=inside(self.source,relative);target=(inside(self.repo,relative) if relative in self.inventory['layout'].get('materialize',[]) else dest/relative);target.parent.mkdir(parents=True,exist_ok=True)
            need(not target.is_symlink(),'Materialization target may not be a link')
            need(not target.exists() or sha(target)==digest,'Existing materialization target differs')
            if source.resolve()!=target.resolve():shutil.copyfile(source,target)
            need(sha(target)==digest and sha(source)==digest,'Adopted bytes changed during copy')
        verify_inventory(self.source,self.inventory);self.save()
        self.adopted=dest
        for arm,relative in self.inventory['layout']['checkpoint_sidecars'].items():
            fit=self.role('fits',arm+':M6')/'scanvi'
            expected=load(dest/relative)
            actual={p.relative_to(fit).as_posix():sha(p) for p in fit.rglob('*') if p.is_file()}
            need(expected==actual and bool(actual),'Adopted M6 checkpoint contents differ from sidecar')
    def role(self,name,key=None):
        prefix=self.inventory['layout'][name]
        return self.adopted/(prefix[key] if key is not None else prefix)
    def checked_python(self,code,args):
        result=subprocess.run([self.python,'-c',code]+args,cwd=self.repo,env=os.environ|self.env,
                              capture_output=True,text=True,timeout=min(120,self.left()))
        need(result.returncode==0,'Clone environment/model validation failed: '+result.stderr[-1000:])
        return json.loads(result.stdout)
    def environment_check(self,persist=True):
        code="""import ast,hashlib,importlib,importlib.metadata,json,pathlib,sys
cfg=json.loads(sys.argv[1]);assert '.'.join(map(str,sys.version_info[:3]))==cfg['python_version'];versions={p:importlib.metadata.version(p) for p in cfg['package_versions']}
assert versions==cfg['package_versions'], 'Dependency versions changed'
p=pathlib.Path(importlib.metadata.distribution('celltypist').locate_file('celltypist/train.py'))
assert hashlib.sha256(p.read_bytes()).hexdigest()==cfg['celltypist_train_sha256']
calls=[n for n in ast.walk(ast.parse(p.read_text())) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='LogisticRegression']
assert any(any(k.arg is None and isinstance(k.value,ast.Name) and k.value.id=='kwargs' for k in c.keywords) for c in calls)
print(json.dumps({'versions':versions,'train_sha256':cfg['celltypist_train_sha256']}))"""
        self.receipt['environment']=self.checked_python(code,[json.dumps(self.cfg)])
        if persist:self.save()
    def model_check(self,directory,arm):
        code="""import hashlib,json,pickle,sys
sys.path.insert(0,sys.argv[1]);model=pickle.load(open(sys.argv[2],'rb'));c=model.model.classifier;s=model.model.scaler
assert c.random_state==0 and c.solver=='sag' and c.max_iter==500 and c.n_jobs==4 and c.tol==.0001 and c.C==1.0 and c.multi_class=='ovr'
h=lambda values:hashlib.sha256(json.dumps(list(values),default=str,separators=(',',':')).encode()).hexdigest()
observed={'genes_sha256':h(model.genes),'classes_sha256':h(model.classes)}
for key in ('mean_','scale_','var_'):observed['scaler_'+key.rstrip('_')+'_sha256']=hashlib.sha256(getattr(s,key).tobytes()).hexdigest()
assert observed==json.loads(sys.argv[3]), 'Scaler/genes/classes changed'
print(json.dumps(observed))"""
        identity=self.checked_python(code,[str(self.repo/'companion/src'),str(directory/'model.pkl'),json.dumps(self.cfg['historical_m5_identity'][arm])])
        self.receipt.setdefault('models',{})[arm]={'random_state':0,'solver':'sag','identity':identity,
                                                  'model_sha256':sha(directory/'model.pkl')};self.save()
    def run(self):
        self.copy_inputs()
        self.step('env','env',lambda _:[ 'uv','sync','--frozen'])
        self.environment_check()
        D,ci=self.role('data'),self.role('cite')
        elig=RM.parse_eligibility(ci/RM.ELIGIBILITY_FILE)
        need(elig['n_eligible']==2,'Approved eligible CITE inputs changed')
        py=self.python;sc=self.repo/'companion/scripts';rm=[py,str(sc/'run_matched.py'),'--workspace',str(self.repo)]
        fits,preds={},{}
        for arm in ('A','B'):
            fits[arm]=self.step(arm+'_M5_fit','fit',lambda out,arm=arm:rm+['--data',str(D),'--arm',arm,'--method','M5','--stage','fit','--out',str(out)])
            self.model_check(fits[arm],arm)
            preds[arm]=self.step(arm+'_M5_predict','predict',lambda out,arm=arm:rm+['--data',str(D),'--arm',arm,'--method','M5','--stage','predict','--model-dir',str(fits[arm]),'--out',str(out)])
        cite5=self.step('A_M5_cite','cite_predict',lambda out:rm+['--data',str(ci),'--arm','A','--method','M5','--stage','predict','--model-dir',str(fits['A']),'--out',str(out)])
        arms={}
        for arm in ('A','B'):
            source={m:[self.role('predictions',arm+':'+m),self.role('fits',arm+':'+m)] for m in METHODS}
            # Combined historical fit+prediction directories must only be listed once.
            source={m:list(dict.fromkeys(paths)) for m,paths in source.items()}
            source['M5']=[preds[arm],fits[arm]]
            arms[arm]=RM.assemble_arm(self.output/'arms'/arm,source)
        citearm=RM.assemble_arm(self.output/'armA_cite',{m:[self.role('cite_predictions',m)] for m in METHODS}|{'M5':[cite5]})
        score=self.step('score','score',lambda out:[py,str(sc/'score_all.py'),'--workspace',str(self.repo),'--data',str(D),
            '--matched','A='+str(arms['A']),'B='+str(arms['B']),'--reps','1000','--natural-unknown-scope','natural','--out',str(out)])
        refs={k:inside(self.source,v) for k,v in self.inventory['layout']['equality_references'].items()}
        equal_non_m5(score,refs)
        self.receipt['non_m5_equality']={'status':'passed','references_sha256':{k:sha(v) for k,v in refs.items()}}
        protein=self.step('protein','protein',lambda out:[py,str(sc/'protein_check.py'),'--workspace',str(self.repo),'--cite',str(ci),
            '--matched','A='+str(citearm),'--thresholds',str(score/'thresholds_validation.csv'),'--out',str(out)])
        pc=RM.protein_check_summary(elig,protein)
        prov={'version':VERSION,'stage':self.stage,'adopted_unaffected_methods':list(METHODS),
              'adoption_inventory_sha256':sha(self.inventory_path),'M5_execution':'independent seed0 process',
              'source_parent':self.inventory['parent_id'],
              'adopted_source_run':ORIGINAL_RUN if self.stage=='canonical' else FRESH_PARENT,
              'fresh_scope':('M5 only; unaffected canonical outputs adopted from original run' if self.stage=='canonical'
                             else 'M5 only; unaffected outputs independently fitted in failed fresh parent')}
        man=self.output/'comparison_manifest.json'
        RM.write_compare_manifest(man,mode='R' if self.stage=='canonical' else 'F',data=D,cite=ci,arms={'A':[arms['A'],citearm],'B':[arms['B']]},
            score={'primary':score},protein=protein,fresh=self.stage=='reproduction',
            d03_features=inside(self.source,self.inventory['layout']['d03_features']),provenance=prov,
            eligibility=ci/RM.ELIGIBILITY_FILE,amendment=RM.AMENDMENT_ID,protein_status=pc['status'],**RM.find_optional_evidence(score,protein))
        results=RM.aggregate_results(score,protein,extra={'protein_check':pc,'result_version':VERSION})
        dump(self.output/'results.json',results)
        if self.stage=='reproduction':
            baseline=Path(os.environ['CELLTRANSFER_BASELINE_MANIFEST']).resolve()
            need(sha(baseline)==self.approval['canonical_manifest_sha256'],'Corrected canonical baseline hash differs')
            report=self.output/'compare/report.json';report.parent.mkdir()
            self.step('compare','compare',lambda out:[py,str(self.repo/'scripts/compare_runs.py'),'--original',str(baseline),
                '--reproduction',str(man),'--tolerances',str(self.repo/'protocol/tolerances-v2.json'),'--out',str(report)])
            dump(self.repo/'results/full/results.json',results)
            self.step('paper_assets','paper',lambda out:[py,str(self.repo/'scripts/make_paper_assets.py'),'--root',str(self.repo),
                '--score',str(score),'--protein',str(protein),'--eligibility',str(ci/RM.ELIGIBILITY_FILE),
                '--comparison',str(report),'--output',str(self.repo/'paper')])
            self.step('paper_build','paper',lambda out:[py,str(self.repo/'scripts/build_paper.py')])
            need((self.repo/'paper/build/main.pdf').is_file(),'PDF missing after build')
        self.receipt['status']='complete';self.save()
        dump(self.output/'provenance.json',self.receipt)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stage',choices=('canonical','reproduction'),required=True)
    ap.add_argument('--config',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--preflight',action='store_true')
    args=ap.parse_args();r=None
    try:
        need(os.environ.get('RESEARCH_ADOPTION_STAGE')==args.stage,'CLI/harness stage differs')
        r=Repair(HERE.parent,load(args.config),args.config,args.output,preflight=args.preflight)
        if args.preflight:
            r.python=str(r.source/'.venv/bin/python')
            need(Path(r.python).is_file(),'Pinned source clone interpreter missing for read-only preflight')
            r.environment_check(persist=False)
            print(json.dumps({'status':'preflight passed; no output or scientific invocations','inventory_payload_sha256':inventory_payload_sha256(r.inventory)}));return 0
        r.run();return 0
    except (Stop,RM.ManifestError,OSError,ValueError,KeyError) as exc:
        if r is not None and not args.preflight:
            r.receipt.update(status='stopped',blocker=str(exc));r.save()
        print(f'STOPPED: {exc}',file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
