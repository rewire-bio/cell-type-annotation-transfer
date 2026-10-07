"""Synthetic CLI boundaries. No scientific computation or real guarded process."""
import importlib.util,json,csv,subprocess,sys,tarfile,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace,ModuleType
from unittest.mock import patch
S=importlib.util.spec_from_file_location('cli',Path(__file__).with_name('compact_cli.py'));M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class CLITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.meta=self.root/'metadata';self.meta.mkdir();self.pkg=self.root/'package';self.archive=self.root/'baseline.tar.gz'
  for rel in ('comparison_manifest.json','d03_features.json','cite/eligibility.json','cite/features_and_classes.json','cite/coverage.json','protein/gates.json','arms/A/M4/fit_info.json','arms/B/M4/fit_info.json'):
   p=self.meta/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
  p=self.meta/'protein/protein_agreement.csv';p.write_text('file,arm,method\nfixture,A,M1\n')
  self.record={'schema':M.C.SCHEMA,'canonical_manifest_sha256':'a'*64,'canonical_comparison_manifest_sha256':'b'*64,'slots':[{'target':'data/predictions_fixture.parquet','role':'synthetic','sha256':'c'*64,'size_bytes':5}]}
  metadata={p.relative_to(self.meta).as_posix():M.C.sha(p) for p in self.meta.rglob('*') if p.is_file()};M.C.package_metadata(self.record,self.meta,metadata,self.pkg,self.archive)
  self.pins={'record_sha256':M.C.sha(self.pkg/'compact-reference.json'),'archive_sha256':M.C.sha(self.archive),'canonical_manifest_sha256':'a'*64,'canonical_comparison_manifest_sha256':'b'*64}
  self.b={'schema':'celltransfer-compact-release-bindings/1',**self.pins,'package_files':{p.relative_to(self.pkg).as_posix():M.C.sha(p) for p in self.pkg.rglob('*') if p.is_file()}}
  self.bind=self.root/'release-bindings.json';self.bind.write_text(json.dumps(self.b))
 def test_package_reserved_controls_are_bound_and_separated_from_nine_metadata(self):
  record,meta,control=M.check_package(self.pkg,self.b,self.pins);self.assertEqual(record,self.record);self.assertEqual(len(meta),9);self.assertEqual(set(control),{'compact-reference.json','checksums.json'})
 def test_independent_original_record_cannot_be_swapped_by_fresh_values(self):
  x=json.loads((self.pkg/'compact-reference.json').read_text());x['slots'][0]['sha256']='f'*64;(self.pkg/'compact-reference.json').write_text(json.dumps(x));self.b['package_files']['compact-reference.json']=M.C.sha(self.pkg/'compact-reference.json')
  with self.assertRaisesRegex(ValueError,'original reference identity'):M.check_package(self.pkg,self.b,self.pins)
 def test_modified_reserved_checksums_refused(self):
  (self.pkg/'checksums.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'package file differs'):M.check_package(self.pkg,self.b,self.pins)
 def test_external_binding_sha_and_pinned_original_identities_required(self):
  self.assertEqual(M.release_bindings(self.bind,M.C.sha(self.bind),self.pins),self.b)
  with self.assertRaisesRegex(ValueError,'external bindings SHA'):M.release_bindings(self.bind,'forged',self.pins)
  wrong=dict(self.pins,canonical_manifest_sha256='f'*64)
  with self.assertRaisesRegex(ValueError,'Original release identity'):M.release_bindings(self.bind,M.C.sha(self.bind),wrong)
 def test_unpack_success_checks_all_published_members_without_arrays(self):
  dest=self.root/'unpacked';result=M.unpack(self.archive,dest,self.b,self.pins);self.assertEqual(result['status'],'package-verified');self.assertEqual(len([p for p in dest.rglob('*') if p.is_file()]),11);self.assertFalse(any(p.suffix=='.parquet' for p in dest.rglob('*')))
 def test_unpack_rejects_links_or_path_traversal_even_if_archive_hash_rebound(self):
  bad=self.root/'bad.tar.gz'
  with tarfile.open(bad,'w:gz') as tar:
   info=tarfile.TarInfo('baseline/../../escaped');info.type=tarfile.SYMTYPE;info.linkname='/tmp/private';tar.addfile(info)
  pins=dict(self.pins,archive_sha256=M.C.sha(bad));bindings=dict(self.b,archive_sha256=pins['archive_sha256'])
  with self.assertRaisesRegex(ValueError,'ordinary'):M.unpack(bad,self.root/'bad-out',bindings,pins)
 def test_real_cli_check_command_accepts_only_correct_external_sha(self):
  with patch.dict(M.PINS,self.pins,clear=True):
   with patch('builtins.print'):
    self.assertEqual(M.main(['check-package','--package-directory',str(self.pkg),'--release-bindings',str(self.bind),'--release-bindings-sha256',M.C.sha(self.bind)]),0)
    self.assertEqual(M.main(['check-package','--package-directory',str(self.pkg),'--release-bindings',str(self.bind),'--release-bindings-sha256','bad']),3)
 def test_sampler_reads_only_obs_in_sorted_query_order_closes_files(self):
  ws=self.root/'fresh';data=ws/'data';data.mkdir(parents=True);(data/'query_b_F.h5ad').write_text('synthetic');(data/'query_a_F.h5ad').write_text('synthetic');manifest=ws/'manifest.json';manifest.write_text('{"data":"data"}');closed=[];seen=[]
  class Obs:
   def __init__(self,name):self.name=name
   def __getitem__(self,keys):self.assertkeys=keys;self.keys=keys;return self
   def to_dict(self,kind):
    self_outer.assertEqual(self.keys,['study','role','stratum','soma_joinid']);return [{'study':self.name,'role':'natural','stratum':'test','soma_joinid':1}]
  class A:
   def __init__(self,p):self.obs=Obs(p.name);self.file=SimpleNamespace(close=lambda:closed.append(p.name))
   @property
   def X(self):raise AssertionError('Scientific matrix must never be read')
  self_outer=self
  ad=ModuleType('anndata');ad.read_h5ad=lambda p,backed:(seen.append((p.name,backed)) or A(p))
  pd=ModuleType('pandas')
  class Frame:
   def __init__(self,rows):self.rows=rows
   def to_csv(self,p,index):
    self_outer.assertFalse(index)
    with Path(p).open('w',newline='') as f:
     writer=csv.DictWriter(f,fieldnames=list(self.rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(self.rows)
  pd.DataFrame=Frame
  with patch.dict(sys.modules,{'anndata':ad,'pandas':pd}):result=M.sample_ids(manifest,ws,ws/'derived/sampled_ids.csv')
  self.assertEqual(result['rows'],2);self.assertEqual(seen,[('query_a_F.h5ad','r'),('query_b_F.h5ad','r')]);self.assertEqual(closed,['query_a_F.h5ad','query_b_F.h5ad']);self.assertEqual(manifest.read_text(),'{"data":"data"}')
 def test_existing_resource_limits_and_runtime_exhaustion_fail_closed(self):
  ws=self.root/'fresh';ws.mkdir();receipt=ws/'receipt.json';receipt.write_text(json.dumps({'h_seconds_used':53999,'f_seconds_used':50000}));config={'guard':{'threads':4,'mem_limit_gib':12.0,'storage_cap_gib':7.0},'budgets':{'reproduction_seconds':54000,'paper_seconds':1800},'mode_f':{'stage_ceiling_s':50400}}
  clockvals=iter([0,2]);r=M.GuardedRunner(ws,receipt,config,self.root/'attempts',guard=SimpleNamespace(),clock=lambda:next(clockvals))
  with self.assertRaisesRegex(ValueError,'runtime budget exhausted'):r.remaining()
  config['guard']['threads']=8
  with self.assertRaisesRegex(ValueError,'resource limits'):M.GuardedRunner(ws,receipt,config,self.root/'attempts',guard=SimpleNamespace())
 def test_guard_propagates_existing_cpu_memory_storage_timeout_and_nonzero(self):
  ws=self.root/'fresh';ws.mkdir();receipt=ws/'receipt.json';receipt.write_text(json.dumps({'h_seconds_used':10,'f_seconds_used':10}));config={'guard':{'threads':4,'mem_limit_gib':12.0,'storage_cap_gib':7.0},'budgets':{'reproduction_seconds':54000,'paper_seconds':1800},'mode_f':{'stage_ceiling_s':50400,'step_ceilings_s':{'compare':1800}}};log=self.root/'attempt';log.mkdir();(log/'stdout.log').write_text('');(log/'stderr.log').write_text('guard fixture');seen=[]
  def guard(command,**kwargs):seen.append(kwargs);return {'attempt_dir':str(log),'status':'memory-stop','returncode':None}
  r=M.GuardedRunner(ws,receipt,config,self.root/'attempts',guard=SimpleNamespace(GiB=1024**3,run_guarded=guard));result=r(['python',str(ws/'scripts/compare_runs.py')]);self.assertEqual(result.returncode,125);self.assertEqual(seen[0]['threads'],4);self.assertEqual(seen[0]['mem_limit'],12*1024**3);self.assertEqual(seen[0]['storage_cap'],7*1024**3);self.assertLessEqual(seen[0]['timeout'],1800)
 def test_verified_scientific_git_commit_and_clean_tracked_source_required(self):
  ws=self.root/'source';ws.mkdir();required=('scripts/compare_runs.py','scripts/make_paper_assets.py','scripts/build_paper.py','scripts/resource_guard.py','configs/full.json','protocol/tolerances-v2.json')
  for rel in required:
   p=ws/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
  (ws/'README.md').write_text('synthetic')
  for args in [('init','-q'),('config','user.name','Engineering Fixture'),('config','user.email','fixture@example.invalid'),('add','.'),('commit','-qm','Synthetic source binding')]:subprocess.run(['git','-C',str(ws),*args],check=True,capture_output=True)
  tip=subprocess.check_output(['git','-C',str(ws),'rev-parse','HEAD'],text=True).strip()
  b={'verified_source_commit':tip,'scientific_files':{r:M.C.sha(ws/r) for r in required},'auxiliary_files':{r:M.C.sha(M.HERE/r) for r in ('compact_cli.py','compact_reference.py','compact_compare_continuation.py')}}
  self.assertEqual(M.verify_sources(ws,b),{})
  (ws/'README.md').write_text('changed operational documentation')
  with self.assertRaisesRegex(ValueError,'tracked modifications'):M.verify_sources(ws,b)
  (ws/'README.md').write_text('synthetic');b['verified_source_commit']='forged'
  with self.assertRaisesRegex(ValueError,'verified scientific source commit'):M.verify_sources(ws,b)
 def test_resume_success_preserves_actual_failure_and_only_requests_metadata_compare_pdf(self):
  ws=self.root/'fresh';ws.mkdir();data=ws/'data';data.mkdir();payload=data/'predictions_fixture.parquet';payload.write_bytes(b'FIXED ORIGINAL')
  self.record['slots'][0].update(sha256=M.C.sha(payload),size_bytes=payload.stat().st_size)
  manifest=ws/'fresh.json';manifest.write_text(json.dumps({'mode':'F','fresh_execution':True,'data':'data','score':{'primary':'score'},'protein':'protein','eligibility':'cite/eligibility.json'}))
  baseline=self.meta/'comparison_manifest.json';baseline.write_text(json.dumps({'mode':'R','data':'data','arms':{},'score':{'primary':'score'},'protein':'protein','cite':'cite'}))
  (self.meta/'compact-reference.json').write_text(json.dumps(self.record));(self.meta/'checksums.json').write_text('{}')
  metadata={p.relative_to(self.meta).as_posix():M.C.sha(p) for p in self.meta.rglob('*') if p.is_file() and p.name not in ('compact-reference.json','checksums.json')};controls={n:M.C.sha(self.meta/n) for n in ('compact-reference.json','checksums.json')}
  report=ws/'initial-failed-report.json';report.write_text('{"initial_failure":true}');failed=ws/'failed.json';failed.write_text(json.dumps({'status':'stopped','comparison':{'returncode':1,'report':str(report)},'steps':[{'name':'score','status':'ok','returncode':0},{'name':'compare','status':'failed','returncode':1}]}));original=failed.read_bytes()
  for rel in ('scripts/compare_runs.py','scripts/make_paper_assets.py','scripts/build_paper.py','protocol/tolerances-v2.json'):
   p=ws/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic source')
  bindings={'scientific_files':{rel:M.C.sha(ws/rel) for rel in ('scripts/compare_runs.py','scripts/make_paper_assets.py','scripts/build_paper.py','protocol/tolerances-v2.json')}};calls=[]
  class Runner:
   def __init__(self,*a,**k):pass
   def remaining(self):return 100
   def run(self,command,name,timeout):
    calls.append(name);p=Path(command[command.index('--output')+1]);p.parent.mkdir(parents=True);p.write_text('synthetic metadata');return SimpleNamespace(returncode=0)
   def __call__(self,command,**kw):
    name=Path(command[1]).name;calls.append(name)
    if name=='compare_runs.py':Path(command[command.index('--out')+1]).write_text(json.dumps({'schema':'celltransfer-compare-report/1','counts':{'gated_breaches_or_structural':0,'unsupported':0},'failures':[],'unsupported':[]}))
    if name=='build_paper.py':
     p=ws/'paper/build/main.pdf';p.parent.mkdir(parents=True);p.write_bytes(b'%PDF-synthetic-fixture')
    return SimpleNamespace(returncode=0,stdout='',stderr='')
  args=SimpleNamespace(workspace=ws,package_directory=self.meta,failed_receipt=failed,fresh_manifest=manifest,reference_directory=self.root/'reference',continuation_directory=self.root/'continuation')
  with patch.object(M,'check_package',return_value=(self.record,metadata,controls)),patch.object(M,'verify_sources',return_value={'mode_f':{'step_ceilings_s':{'compare':1800}}}):result=M.resume(args,bindings,runner_factory=Runner)
  self.assertEqual(result['status'],'completed');self.assertEqual(calls,['sampled_ids','compare_runs.py','make_paper_assets.py','build_paper.py']);self.assertEqual(failed.read_bytes(),original);self.assertEqual((self.root/'continuation-initial-failure/generation_receipt.json').read_bytes(),original)

 def test_second_continuation_cannot_reset_existing_runtime_pool(self):
  ws=self.root/'fresh';ws.mkdir();p=ws/'failed.json';p.write_text('{"status":"stopped"}')
  reservation=M.reserve_continuation(ws,p);original=reservation.read_bytes()
  with self.assertRaisesRegex(ValueError,'already reserved'):M.reserve_continuation(ws,p)
  self.assertEqual(reservation.read_bytes(),original);self.assertEqual(p.read_text(),'{"status":"stopped"}')
