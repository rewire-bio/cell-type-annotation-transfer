"""Synthetic operational wrapper checks. No scientific code execution."""
import importlib.util,json
from pathlib import Path
import tempfile,unittest
from types import SimpleNamespace
S=importlib.util.spec_from_file_location('wrapper',Path(__file__).with_name('compact_compare_continuation.py'));M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class WrapperTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);self.ws=self.root/'fresh';self.ws.mkdir();self.meta=self.root/'metadata';self.meta.mkdir();self.calls=[]
  (self.ws/'scripts').mkdir();self.bind={}
  for rel in ('scripts/compare_runs.py','scripts/make_paper_assets.py','scripts/build_paper.py','tolerances.json'):
   p=self.ws/rel;p.write_text('synthetic operational fixture');self.bind[rel]=M.C.sha(p)
  candidate=self.ws/'candidate.parquet';candidate.write_bytes(b'fixed-original-fixture')
  self.record={'schema':M.C.SCHEMA,'canonical_manifest_sha256':'a'*64,'canonical_comparison_manifest_sha256':'b'*64,'slots':[{'target':'data/predictions_fixture.parquet','role':'synthetic','sha256':M.C.sha(candidate),'size_bytes':candidate.stat().st_size}]}
  fresh=self.ws/'comparison_manifest.json';fresh.write_text(json.dumps({'mode':'F','fresh_execution':True,'score':{'primary':'score'},'protein':'protein','eligibility':'cite/eligibility.json'}))
  baseline=self.meta/'comparison_manifest.json';baseline.write_text(json.dumps({'mode':'R','data':'data','arms':{},'score':{'primary':'score'},'protein':'protein','cite':'cite'}))
  failed=self.ws/'failed-receipt.json';failed.write_text(json.dumps({'status':'stopped','steps':[{'name':'score','status':'ok','returncode':0},{'name':'compare','status':'failed','returncode':1}],'comparison':{'returncode':1,'report':str(self.ws/'failed-report.json')}}));(self.ws/'failed-report.json').write_text('{"initial_failure":true}')
  self.args={'record':self.record,'mapping':{'data/predictions_fixture.parquet':str(candidate)},'workspace':self.ws,'reference_destination':self.root/'reference','baseline_template':baseline,'fresh_manifest':fresh,'failed_receipt':failed,'continuation_dir':self.root/'continuation','tolerances':self.ws/'tolerances.json','script_bindings':self.bind,'metadata_bindings':{'comparison_manifest.json':M.C.sha(baseline)},'runner':self.runner}
 def runner(self,cmd,**kwargs):
  self.calls.append(cmd);name=Path(cmd[1]).name
  if name=='compare_runs.py':
   p=Path(cmd[cmd.index('--out')+1]);p.write_text(json.dumps({'schema':'celltransfer-compare-report/1','counts':{'gated_breaches_or_structural':0,'unsupported':0},'failures':[],'unsupported':[]}))
  if name=='build_paper.py':
   p=self.ws/'paper/build/main.pdf';p.parent.mkdir(parents=True);p.write_bytes(b'%PDF-synthetic-not-scientific')
  return SimpleNamespace(returncode=0,stdout='synthetic engineering runner',stderr='')
 def test_only_existing_comparison_assets_pdf_execute_after_identity_restoration(self):
  original=self.args['failed_receipt'].read_bytes();result=M.continue_comparison(**self.args)
  self.assertEqual(result['status'],'completed');self.assertFalse(result['generation_repeated']);self.assertEqual([Path(x[1]).name for x in self.calls],['compare_runs.py','make_paper_assets.py','build_paper.py']);self.assertEqual(self.args['failed_receipt'].read_bytes(),original);self.assertEqual((self.args['continuation_dir']/'initial-failed-receipt.json').read_bytes(),original)
 def test_mismatch_preserves_initial_failure_without_command_or_verdict(self):
  (self.ws/'candidate.parquet').write_bytes(b'mismatch');result=M.continue_comparison(**self.args);self.assertEqual(result['status'],'unsupported');self.assertIsNone(result['scientific_verdict']);self.assertEqual(self.calls,[]);self.assertTrue((self.args['continuation_dir']/'initial-failed-receipt.json').is_file())
 def test_changed_tolerance_refuses_before_any_continuation(self):
  self.args['tolerances'].write_text('changed')
  with self.assertRaisesRegex(ValueError,'operational bytes'):M.continue_comparison(**self.args)
  self.assertEqual(self.calls,[]);self.assertFalse(self.args['continuation_dir'].exists())
 def test_metadata_array_even_bound_is_refused(self):
  p=self.meta/'withheld.parquet';p.write_bytes(b'private-array');self.args['metadata_bindings'][p.name]=M.C.sha(p)
  with self.assertRaisesRegex(ValueError,'metadata only'):M.continue_comparison(**self.args)
  self.assertFalse(self.args['reference_destination'].exists())
 def test_failed_scientific_stage_cannot_be_bypassed(self):
  p=self.args['failed_receipt'];x=json.loads(p.read_text());x['steps'][0]['returncode']=1;p.write_text(json.dumps(x))
  with self.assertRaisesRegex(ValueError,'generation must'):M.continue_comparison(**self.args)
 def test_comparison_failure_does_not_build_paper(self):
  self.args['runner']=lambda cmd,**kw:(self.calls.append(cmd) or SimpleNamespace(returncode=3,stdout='',stderr='unsupported fixture'))
  result=M.continue_comparison(**self.args);self.assertEqual(result['status'],'failed');self.assertEqual(len(self.calls),1);self.assertIsNone(result['scientific_verdict'])
 def test_two_reserved_package_controls_are_validated_but_not_copied_as_metadata(self):
  record=self.meta/'compact-reference.json';record.write_text(json.dumps(self.record));checks=self.meta/'checksums.json';checks.write_text('{}');self.args['package_controls']={record.name:M.C.sha(record),checks.name:M.C.sha(checks)}
  result=M.continue_comparison(**self.args);self.assertEqual(result['status'],'completed');self.assertFalse((self.args['reference_destination']/'compact-reference.json').exists());self.assertEqual(len(self.calls),3)
 def test_reserved_original_record_cannot_be_replaced(self):
  record=self.meta/'compact-reference.json';record.write_text('{}');self.args['package_controls']={record.name:M.C.sha(record)}
  with self.assertRaisesRegex(ValueError,'original reference record'):M.continue_comparison(**self.args)
  self.assertEqual(self.calls,[])
