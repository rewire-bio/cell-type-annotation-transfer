"""Synthetic exact-identity restoration tests. No scientific stages."""
import importlib.util,json
from pathlib import Path
import tempfile,unittest
S=importlib.util.spec_from_file_location('compact',Path(__file__).with_name('compact_reference.py'));M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class CompactTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);self.f=self.root/'fresh';self.f.mkdir();self.p=self.f/'file.parquet';self.p.write_bytes(b'fixture-not-array');self.dst=self.root/'reference';self.receipt=self.root/'restoration.json'
  self.r={'schema':M.SCHEMA,'canonical_manifest_sha256':'a'*64,'canonical_comparison_manifest_sha256':'b'*64,'slots':[{'target':'arms/A/M1/predictions_fixture.parquet','role':'synthetic','sha256':M.sha(self.p),'size_bytes':self.p.stat().st_size}]};self.map={self.r['slots'][0]['target']:str(self.p)}
 def restore(self):return M.restore(self.r,self.map,self.f,self.dst,self.receipt)
 def test_exact_identity_copies_bytes_without_alias(self):
  result=self.restore();target=self.dst/self.r['slots'][0]['target'];self.assertEqual(result['status'],'exact-reference-restored');self.assertEqual(target.read_bytes(),self.p.read_bytes());self.assertNotEqual(target.stat().st_ino,self.p.stat().st_ino);self.assertIsNone(result['scientific_verdict'])
 def test_mismatch_never_creates_reference_or_scientific_verdict(self):
  self.p.write_bytes(b'changed');result=self.restore();self.assertEqual(result['status'],'unsupported');self.assertFalse(self.dst.exists());self.assertIsNone(result['scientific_verdict'])
 def test_missing_never_creates_reference(self):
  self.p.unlink();self.assertEqual(self.restore()['status'],'unsupported');self.assertFalse(self.dst.exists())
 def test_reference_cannot_overlap_fresh_tree(self):
  self.dst=self.f/'ref'
  with self.assertRaisesRegex(ValueError,'Separate'):self.restore()
 def test_reference_cannot_replace_existing_tree(self):
  self.dst.mkdir()
  with self.assertRaisesRegex(ValueError,'new'):self.restore()
 def test_duplicate_and_traversal_slots_rejected(self):
  self.r['slots'].append(dict(self.r['slots'][0]))
  with self.assertRaisesRegex(ValueError,'Duplicate'):self.restore()
  self.r['slots'].pop();self.r['slots'][0]['target']='../escaped'
  with self.assertRaisesRegex(ValueError,'Unsafe'):self.restore()
 def test_outside_fresh_candidate_is_unsupported(self):
  p=self.root/'outside';p.write_bytes(self.p.read_bytes());self.map[self.r['slots'][0]['target']]=str(p);self.assertEqual(self.restore()['status'],'unsupported')
 def test_expected_hashes_derive_only_from_bound_canonical_originals(self):
  c=self.root/'canonical';c.mkdir();p=c/'ref';p.write_bytes(b'canonical');cm=c/'manifest.json';cm.write_text('{}');cp=c/'comparison_manifest.json';cp.write_text('{}')
  audit={'canonical_id':'synthetic','canonical_run_manifest_sha256':M.sha(cm),'canonical_comparison_manifest_sha256':M.sha(cp),'slots':[{'target':'data/reference','role':'synthetic','canonical_source':'canonical/ref','original_sha256':M.sha(p),'original_bytes':p.stat().st_size,'candidate_sha256':'FORGED-CANDIDATE'}]}
  result=M.prepare_record(audit,self.root,cm,cp);self.assertEqual(result['slots'][0]['sha256'],M.sha(p));self.assertNotIn('canonical_source',json.dumps(result));p.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'original bytes'):M.prepare_record(audit,self.root,cm,cp)
 def test_package_contains_only_reviewed_metadata_and_fixed_hashes(self):
  import tarfile
  metadata=self.root/'metadata';metadata.mkdir();p=metadata/'comparison_manifest.json';p.write_text('{"mode":"R","data":"data"}')
  archive=self.root/'baseline.tar.gz';result=M.package_metadata(self.r,metadata,{p.name:M.sha(p)},self.root/'package',archive)
  with tarfile.open(archive) as t:names=t.getnames()
  self.assertEqual(set(names),{'baseline/comparison_manifest.json','baseline/compact-reference.json','baseline/checksums.json'});self.assertIsNone(result['scientific_verdict']);self.assertEqual(self.p.read_bytes(),b'fixture-not-array')
 def test_package_refuses_percell_arrays_and_private_locations(self):
  metadata=self.root/'metadata';metadata.mkdir();p=metadata/'file.parquet';p.write_bytes(b'withheld')
  with self.assertRaisesRegex(ValueError,'No arrays'):M.package_metadata(self.r,metadata,{p.name:M.sha(p)},self.root/'package',self.root/'a.tar.gz')
  p.unlink();p=metadata/'comparison_manifest.json';p.write_text('{"private":"/Users/someone/data"}')
  with self.assertRaisesRegex(ValueError,'private absolute'):M.package_metadata(self.r,metadata,{p.name:M.sha(p)},self.root/'package',self.root/'a.tar.gz')
