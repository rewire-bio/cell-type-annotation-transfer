#!/usr/bin/env python3
"""CLI for frozen metadata verification and comparison-only recovery.

No source acquisition, fit, prediction, inference or scoring. A cryptographic
mismatch is unsupported, not a tolerance verdict. Public fresh-clone validation
is pending. Run this auxiliary tool separately from the verified scientific tip.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys
import tarfile
import time
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
PINS={
 'record_sha256':'4e313ab65adcf474b76578e45dd9394745dfb5fa0f0ec6755746dc0849f65e57',
 'canonical_manifest_sha256':'60cfbe955c5b9516532750c3873653e16f558528551403a087bf0b545e2dd516',
 'canonical_comparison_manifest_sha256':'9f7aedd33310ee69e426002cd54acbcc5e3f2833bc0cc3fb8de041e6f1a85683',
 'archive_sha256':'37793da3eafe3a47fa7829aeb39c2c30fdacb436baa3ec765a3ad0243bc2c5fa'}
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
C=load('compact_reference',HERE/'compact_reference.py')
W=load('compact_compare',HERE/'compact_compare_continuation.py')

def release_bindings(path,expected_sha,pins=PINS):
 path=Path(path)
 if C.sha(path)!=expected_sha:raise ValueError('Published external bindings SHA differs')
 b=json.loads(path.read_text())
 if b.get('schema')!='celltransfer-compact-release-bindings/1' or any(b.get(k)!=v for k,v in pins.items()):raise ValueError('Original release identity differs')
 return b

def check_package(directory,bindings,pins=PINS):
 directory=Path(directory).resolve();files={p.relative_to(directory).as_posix():p for p in directory.rglob('*') if p.is_file()}
 if set(files)!=set(bindings['package_files']):raise ValueError('Exact eleven-member published package coverage required')
 for rel,p in files.items():
  C.relative(rel)
  if p.is_symlink() or not p.resolve().is_relative_to(directory) or C.sha(p)!=bindings['package_files'][rel]:raise ValueError('Published package file differs')
 record=json.loads((directory/'compact-reference.json').read_text());C.validate(record)
 if C.sha(directory/'compact-reference.json')!=pins['record_sha256'] or any(record.get(k)!=pins[k] for k in ('canonical_manifest_sha256','canonical_comparison_manifest_sha256')):
  raise ValueError('Independently frozen original reference identity differs')
 checks=json.loads((directory/'checksums.json').read_text())
 if set(checks)!=set(files)-{'checksums.json'} or any(checks[k]!=C.sha(files[k]) for k in checks):raise ValueError('Packaged control checksums differ')
 return record,{k:v for k,v in bindings['package_files'].items() if k not in ('compact-reference.json','checksums.json')},{k:bindings['package_files'][k] for k in ('compact-reference.json','checksums.json')}

def unpack(archive,destination,bindings,pins=PINS):
 archive=Path(archive);destination=Path(destination)
 if C.sha(archive)!=pins['archive_sha256'] or bindings['archive_sha256']!=pins['archive_sha256']:raise ValueError('Published archive SHA differs')
 if destination.exists():raise ValueError('Extraction destination must be new')
 with tarfile.open(archive,'r:gz') as tar:
  seen=set();members=[]
  for m in tar.getmembers():
   if not m.isfile() or not m.name.startswith('baseline/'):raise ValueError('Only ordinary baseline archive members allowed')
   rel=C.relative(m.name[len('baseline/'):])
   if rel in seen:raise ValueError('Duplicate archive member')
   seen.add(rel);members.append((m,rel))
  if seen!=set(bindings['package_files']):raise ValueError('Published archive member coverage differs')
  destination.mkdir(parents=True)
  for member,rel in members:
   p=destination/rel;p.parent.mkdir(parents=True,exist_ok=True)
   with tar.extractfile(member) as source,p.open('xb') as target:
    while chunk:=source.read(1024*1024):target.write(chunk)
 check_package(destination,bindings,pins)
 return {'status':'package-verified','scientific_verdict':None}

def verify_sources(workspace,bindings,tools=HERE):
 workspace=Path(workspace).resolve();tools=Path(tools).resolve()
 for root,key in ((workspace,'scientific_files'),(tools,'auxiliary_files')):
  for rel,digest in bindings[key].items():
   p=(root/C.relative(rel)).resolve()
   if not p.is_relative_to(root) or not p.is_file() or C.sha(p)!=digest:raise ValueError('Published frozen source bytes differ: '+rel)
 required={'scripts/compare_runs.py','scripts/make_paper_assets.py','scripts/build_paper.py','scripts/resource_guard.py','configs/full.json','protocol/tolerances-v2.json'}
 if not required.issubset(bindings['scientific_files']):raise ValueError('Required frozen scripts/config/tolerance bindings missing')
 if not {'compact_cli.py','compact_reference.py','compact_compare_continuation.py'}.issubset(bindings['auxiliary_files']):raise ValueError('Required auxiliary bindings missing')
 import subprocess
 if subprocess.check_output(['git','-C',str(workspace),'rev-parse','HEAD'],text=True).strip()!=bindings.get('verified_source_commit'):
  raise ValueError('Checkout must be the published verified scientific source commit')
 if subprocess.check_output(['git','-C',str(workspace),'diff','--name-only','HEAD'],text=True).strip():raise ValueError('Verified scientific source has tracked modifications')
 return json.loads((workspace/'configs/full.json').read_text())

def sample_ids(fresh_manifest,workspace,destination):
 """Established extraction of obs only: never reads .X or creates measurements."""
 import anndata as ad
 import pandas as pd
 workspace=Path(workspace).resolve();manifest=Path(fresh_manifest).resolve();data=(manifest.parent/json.loads(manifest.read_text())['data']).resolve();destination=Path(destination).resolve()
 if not data.is_relative_to(workspace) or not destination.is_relative_to(workspace) or destination.exists():raise ValueError('New local sampled-ID output and independent data required')
 rows=[]
 for p in sorted(data.glob('query_*_F.h5ad')):
  if not p.resolve().is_relative_to(workspace):raise ValueError('Query source escapes independent workspace')
  a=ad.read_h5ad(p,backed='r')
  try:rows.extend(a.obs[['study','role','stratum','soma_joinid']].to_dict('records'))
  finally:a.file.close()
 if not rows:raise ValueError('No original-recipe query observations')
 destination.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(destination,index=False)
 return {'status':'sampled-id-metadata-prepared','scientific_verdict':None,'rows':len(rows),'sha256':C.sha(destination)}

class GuardedRunner:
 def __init__(self,workspace,failed_receipt,config,attempts,extra_cap_paths=(),guard=None,clock=time.monotonic):
  self.ws=Path(workspace).resolve();self.attempts=Path(attempts).resolve();self.clock=clock;self.started=clock();self.config=config
  old=json.loads(Path(failed_receipt).read_text());self.prior_h=old.get('h_seconds_used');self.prior_f=old.get('f_seconds_used')
  if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in (self.prior_h,self.prior_f)):raise ValueError('Actual finite prior execution runtime required')
  g=config['guard']
  if g!={'threads':4,'mem_limit_gib':12.0,'storage_cap_gib':7.0}:raise ValueError('Existing resource limits required')
  if config['budgets']['reproduction_seconds']!=54000 or config['budgets']['paper_seconds']!=1800 or config['mode_f']['stage_ceiling_s']!=50400:raise ValueError('Existing runtime budgets required')
  self.guard=guard or load('frozen_resource_guard',self.ws/'scripts/resource_guard.py');self.f_used=0.;self.paper_used=0.
  self.cap=[self.ws/p for p in ('.venv','.cache-study','runs','results','paper/build','.tools')]+[Path(p).resolve() for p in extra_cap_paths]
 def remaining(self,paper=False):
  overall=54000-self.prior_h-(self.clock()-self.started)
  pool=1800-self.paper_used if paper else 50400-self.prior_f-self.f_used
  value=min(overall,pool)
  if value<=0:raise ValueError('Existing cumulative runtime budget exhausted')
  return value
 def run(self,command,name,timeout):
  paper=name in ('paper_assets','paper_build');timeout=min(timeout,self.remaining(paper));before=self.clock()
  record=self.guard.run_guarded(command,attempt_root=self.attempts,name=name,timeout=timeout,cwd=self.ws,
   mem_limit=12*self.guard.GiB,swap_growth_limit=4*self.guard.GiB,disk_start_min=3*self.guard.GiB,disk_run_min=int(1.5*self.guard.GiB),storage_cap=7*self.guard.GiB,threads=4,
   disk_path=self.ws,cap_paths=self.cap,time_l=True)
  elapsed=self.clock()-before
  if paper:self.paper_used+=elapsed
  else:self.f_used+=elapsed
  root=Path(record['attempt_dir']);return SimpleNamespace(returncode=0 if record['status']=='ok' and record.get('returncode')==0 else (record.get('returncode') or 125),stdout=(root/'stdout.log').read_text(errors='replace'),stderr=(root/'stderr.log').read_text(errors='replace'))
 def __call__(self,command,**kw):
  names={'compare_runs.py':('compare',self.config['mode_f']['step_ceilings_s']['compare']),'make_paper_assets.py':('paper_assets',1800),'build_paper.py':('paper_build',1800)}
  name,timeout=names[Path(command[1]).name];return self.run(command,name,timeout)

def resume(args,bindings,runner_factory=GuardedRunner):
 ws=Path(args.workspace).resolve();record,metadata,controls=check_package(args.package_directory,bindings);config=verify_sources(ws,bindings)
 continuation=Path(args.continuation_directory).resolve();sample=ws/'runs'/('compact-sampled-ids-'+continuation.name)/'sampled_ids.csv'
 if continuation.exists():raise ValueError('Continuation output must be new')
 # Initial failed receipt remains untouched; immutable copies are retained before metadata work.
 receipt=json.loads(Path(args.failed_receipt).read_text())
 if receipt.get('status')!='stopped' or receipt.get('comparison',{}).get('returncode') not in (1,3):raise ValueError('Actual failed scientific comparison required')
 preservation=continuation.parent/(continuation.name+'-initial-failure')
 if preservation.exists():raise ValueError('Initial failure preservation directory must be new')
 preservation.mkdir(parents=True)
 import shutil
 shutil.copyfile(args.failed_receipt,preservation/'generation_receipt.json')
 prior_report=Path(receipt['comparison']['report']);prior_report=prior_report if prior_report.is_absolute() else ws/prior_report
 if not prior_report.is_file():raise ValueError('Actual initial failed comparison report missing')
 shutil.copyfile(prior_report,preservation/'comparison-report.json')
 runner=runner_factory(ws,args.failed_receipt,config,continuation.parent/(continuation.name+'-resource-attempts'),[args.reference_directory,continuation,preservation])
 sampled=runner.run([sys.executable,str(HERE/'compact_cli.py'),'_sample-ids','--fresh-manifest',str(args.fresh_manifest),'--workspace',str(ws),'--output',str(sample)],'sampled_ids',min(config['mode_f']['step_ceilings_s']['compare'],runner.remaining()))
 if sampled.returncode!=0:return {'status':'unsupported','scientific_verdict':None,'reason':'Bounded sampled-ID metadata preparation failed; initial failure retained'}
 mapping=C.candidate_map(record,args.fresh_manifest,ws,sampled_ids=sample)
 operational={k:v for k,v in bindings['scientific_files'].items() if k in ('scripts/compare_runs.py','scripts/make_paper_assets.py','scripts/build_paper.py','protocol/tolerances-v2.json')}
 return W.continue_comparison(record=record,mapping=mapping,workspace=ws,reference_destination=args.reference_directory,
  baseline_template=Path(args.package_directory)/'comparison_manifest.json',fresh_manifest=args.fresh_manifest,failed_receipt=args.failed_receipt,
  continuation_dir=continuation,tolerances=ws/'protocol/tolerances-v2.json',script_bindings=operational,metadata_bindings=metadata,package_controls=controls,
  python=str(ws/'.venv/bin/python'),runner=runner)

def reserve_continuation(workspace,failed_receipt):
 """Permit one bounded continuation per immutable failed receipt; keep failures."""
 workspace=Path(workspace).resolve();failed_receipt=Path(failed_receipt).resolve()
 if not failed_receipt.is_relative_to(workspace):raise ValueError('Original failed receipt must belong to fresh workspace')
 folder=workspace/'runs/compact-continuation-reservations';folder.mkdir(parents=True,exist_ok=True)
 path=folder/(C.sha(failed_receipt)+'.json')
 try:
  with path.open('x') as f:json.dump({'schema':'celltransfer-compact-continuation-reservation/1','status':'reserved','failed_receipt_sha256':C.sha(failed_receipt),'scientific_generation_repeated':False},f,indent=2)
 except FileExistsError as exc:raise ValueError('One continuation already reserved for this failed receipt; preserve its records rather than reset runtime accounting') from exc
 return path

def bounded_resume(args,bindings):
 ws=Path(args.workspace).resolve();config=verify_sources(ws,bindings)
 check_package(args.package_directory,bindings)
 runner=GuardedRunner(ws,args.failed_receipt,config,Path(args.continuation_directory).parent/(Path(args.continuation_directory).name+'-outer-guard'),[args.reference_directory,args.continuation_directory])
 command=[sys.executable,str(HERE/'compact_cli.py'),'_resume-worker']
 for key in ('release_bindings','release_bindings_sha256','package_directory','workspace','fresh_manifest','failed_receipt','reference_directory','continuation_directory'):
  command.extend(['--'+key.replace('_','-'),str(getattr(args,key))])
 timeout=min(54000-runner.prior_h,50400-runner.prior_f+1800)
 if timeout<=0:raise ValueError('Existing cumulative runtime budget exhausted')
 reservation=reserve_continuation(ws,args.failed_receipt)
 rec=runner.guard.run_guarded(command,attempt_root=runner.attempts,name='compact_continuation',timeout=timeout,cwd=ws,
  mem_limit=12*runner.guard.GiB,swap_growth_limit=4*runner.guard.GiB,disk_start_min=3*runner.guard.GiB,disk_run_min=int(1.5*runner.guard.GiB),storage_cap=7*runner.guard.GiB,
  threads=4,disk_path=ws,cap_paths=runner.cap,time_l=True)
 state=json.loads(reservation.read_text());state.update(status=rec['status'],guard_returncode=rec.get('returncode'),charged_wall_seconds=rec.get('wall_seconds'),guard_attempt_dir=rec['attempt_dir']);C.write(reservation,state)
 output=Path(rec['attempt_dir'])/'stdout.log'
 if rec['status']=='ok' and rec.get('returncode')==0:
  return json.loads(output.read_text())
 return {'status':'unsupported','scientific_verdict':None,'reason':'Resource-bounded continuation failed; original failed receipt remains retained','guard_status':rec['status'],'guard_returncode':rec.get('returncode'),'guard_evidence':str(rec['attempt_dir'])}

def parser():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 for action in ('check-package','unpack','resume','_resume-worker'):
  s=sub.add_parser(action);s.add_argument('--release-bindings',type=Path,required=True);s.add_argument('--release-bindings-sha256',required=True)
  if action!='unpack':s.add_argument('--package-directory',type=Path,required=True)
  if action=='unpack':s.add_argument('--archive',type=Path,required=True);s.add_argument('--destination',type=Path,required=True)
  if action in ('resume','_resume-worker'):
   for key in ('workspace','fresh-manifest','failed-receipt','reference-directory','continuation-directory'):s.add_argument('--'+key,type=Path,required=True)
 s=sub.add_parser('_sample-ids',help=argparse.SUPPRESS)
 for key in ('fresh-manifest','workspace','output'):s.add_argument('--'+key,type=Path,required=True)
 return p

def main(argv=None):
 args=parser().parse_args(argv)
 try:
  if args.action=='_sample-ids':result=sample_ids(args.fresh_manifest,args.workspace,args.output)
  else:
   b=release_bindings(args.release_bindings,args.release_bindings_sha256)
   if args.action=='unpack':result=unpack(args.archive,args.destination,b)
   elif args.action=='check-package':check_package(args.package_directory,b);result={'status':'package-verified','scientific_verdict':None}
   else:
    if platform.system()!='Darwin':raise ValueError('Existing macOS resource guards require separate Linux validation')
    result=resume(args,b) if args.action=='_resume-worker' else bounded_resume(args,b)
  print(json.dumps(result,indent=2));return 0 if result['status'] in ('package-verified','completed','sampled-id-metadata-prepared') else 3
 except (ValueError,KeyError,OSError) as exc:
  print(json.dumps({'status':'unsupported','scientific_verdict':None,'reason':str(exc)}));return 3
if __name__=='__main__':raise SystemExit(main())
