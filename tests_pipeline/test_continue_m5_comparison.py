"""Synthetic comparison-only recovery contracts; no study computation."""
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import continue_m5_comparison as C
import m5_seed_repair as M

NAMES=['env','A_M5_fit','A_M5_predict','B_M5_fit','B_M5_predict','A_M5_cite','score','protein']

def fixture(tmp_path):
    r=object.__new__(C.ComparisonContinuation);r.source=tmp_path;r.stage='reproduction'
    rid='failed';folder=tmp_path/'.research/reproductions'/rid;folder.mkdir(parents=True)
    out=folder/'checkout/results/m5-seed0-v2/reproduction';out.mkdir(parents=True)
    controls={};retained={};bound={};steps=[]
    for name in NAMES:
        d=out/name;d.mkdir();files={}
        if name!='env':
            p=d/'data.bin';p.write_bytes(b'synthetic');files[p.relative_to(tmp_path).as_posix()]=M.sha(p)
        step={'name':name,'kind':'fit' if name.endswith('_fit') else name,'attempt':1,'status':'ok',
              'returncode':0,'executed':True,'out_dir':str(d),'command':['synthetic',name]}
        steps.append(step);bound[name]={'step_sha256':M.object_sha256(step),'command':step['command'],
                                      'out_dir':d.relative_to(tmp_path).as_posix(),'files':files}
        controls.update(files);retained.update(files)
    receipt={'steps':steps,'status':'stopped','stage':'reproduction','version':M.VERSION,
             'blocker':"'CELLTRANSFER_BASELINE_MANIFEST'",'non_m5_equality':{'status':'passed'}}
    rp=out/'generation_receipt.json';M.dump(rp,receipt);mp=folder/'manifest.json';M.dump(mp,{'status':'failed'})
    ledger=tmp_path/'runtime.m5-invocations.json';M.dump(ledger,{'m5_seed_repair':{
        'repair_id':'repair','driver_stage_seconds':{},'fit_invocations':[{'stage':s,'arm':a} for s in ('canonical','reproduction') for a in ('A','B')],
        'score_invocations':[{'stage':s} for s in ('canonical','reproduction')]}})
    snapshot=tmp_path/'snapshot.json';snapshot.write_bytes(ledger.read_bytes())
    for p in (rp,mp,snapshot):controls[p.relative_to(tmp_path).as_posix()]=M.sha(p)
    c={'failed_manifest_sha256':M.sha(mp),'failed_receipt_sha256':M.sha(rp),'completed_steps':bound,
       'retained_files':retained,'driver_ledger_snapshot':{'path':'snapshot.json','sha256':M.sha(snapshot)}}
    r.reproduction_continuation=c;r.inventory={'reproduction_continue_of':rid,'repair_id':'repair','source_controls':controls}
    r.approval={'reproduction_continue_of':rid,'reproduction_continuation':c,'continuation_only':True,
                'remaining_fits':0,'remaining_scores':0,'total_fits':4,'total_scores':2}
    return r,tmp_path/'runtime.json',receipt,rp

def test_completed_steps_validation(tmp_path):
    r,ledger,*_=fixture(tmp_path);r.validate_reproduction_continuation(ledger)
    assert len(r.retained_receipt['steps'])==8

@pytest.mark.parametrize('change',['command','step','bytes','unlisted','link','ledger','approval','stage','scope','receipt','retained','extra_step'])
def test_fail_closed(tmp_path,change):
    r,ledger,receipt,rp=fixture(tmp_path);c=r.reproduction_continuation
    if change=='command':c['completed_steps']['A_M5_fit']['command']=['changed']
    if change=='step':c['completed_steps']['score']['step_sha256']='bad'
    if change=='bytes':next(iter(c['retained_files'])) and (tmp_path/next(iter(c['retained_files']))).write_bytes(b'changed')
    if change=='unlisted':(tmp_path/c['completed_steps']['score']['out_dir']/'extra').write_bytes(b'extra')
    if change=='link':(tmp_path/c['completed_steps']['score']['out_dir']/'link').symlink_to(tmp_path/'snapshot.json')
    if change=='ledger':M.dump(tmp_path/'runtime.m5-invocations.json',{})
    if change=='approval':r.approval['remaining_fits']=1
    if change=='stage':r.stage='canonical'
    if change=='scope':r.approval['total_scores']=3
    if change=='receipt':receipt['blocker']='other failure';M.dump(rp,receipt)
    if change=='retained':c['retained_files']={}
    if change=='extra_step':c['completed_steps']['compare']={}
    with pytest.raises(M.Stop):r.validate_reproduction_continuation(ledger)

@pytest.mark.parametrize('name,kind',[('A_M5_fit','fit'),('score','score'),('A_M5_predict','predict'),('protein','protein'),('env','env'),('other','paper')])
def test_never_invokes_scientific_steps(name,kind):
    r=object.__new__(C.ComparisonContinuation)
    with pytest.raises(M.Stop):r.step(name,kind,lambda out:[])

def canonical_fixture(r,tmp_path,monkeypatch):
    cid='corrected-canonical';folder=tmp_path/'.research/runs'/cid;folder.mkdir(parents=True)
    baseline=folder/'output/comparison_manifest.json';baseline.parent.mkdir();baseline.write_text('{"mode":"R"}')
    manifest=folder/'manifest.json';M.dump(manifest,{'id':cid,'status':'completed','mode':'R','exit_code':0,
        'outputs':{'comparison_manifest.json':M.sha(baseline)}})
    r.inventory['canonical_run_id']=cid;r.approval['canonical_manifest_sha256']=M.sha(manifest)
    r.reproduction_continuation['canonical_baseline']={'path':baseline.relative_to(tmp_path).as_posix(),'sha256':M.sha(baseline)}
    assert M.sha(manifest)!=M.sha(baseline)
    monkeypatch.setenv('CELLTRANSFER_BASELINE_MANIFEST',str(baseline))
    return baseline,manifest

def test_baseline_record_and_comparison_hashes_are_distinct(tmp_path,monkeypatch):
    r,*_=fixture(tmp_path)
    monkeypatch.delenv('CELLTRANSFER_BASELINE_MANIFEST',raising=False)
    with pytest.raises(M.Stop):r.baseline_check()
    baseline,manifest=canonical_fixture(r,tmp_path,monkeypatch)
    assert r.baseline_check()==baseline
    comparison_digest=r.reproduction_continuation['canonical_baseline']['sha256']
    r.approval['canonical_manifest_sha256']=comparison_digest
    with pytest.raises(M.Stop):r.baseline_check()
    r.approval['canonical_manifest_sha256']=M.sha(manifest)
    baseline.write_text('{"changed":true}')
    with pytest.raises(M.Stop):r.baseline_check()


def test_full_recovery_orchestration(tmp_path,monkeypatch):
    """Run actual continuation/copy/assembly/finalization with synthetic subprocesses."""
    r,ledger,receipt,rp=fixture(tmp_path)
    c=r.reproduction_continuation
    # Populate synthetic files matching the real assembly and equality interfaces.
    for name in ('A_M5_predict','B_M5_predict','A_M5_cite'):
        d=tmp_path/c['completed_steps'][name]['out_dir'];(d/'data.bin').rename(d/'predictions_fixture.parquet')
    score=tmp_path/c['completed_steps']['score']['out_dir']
    refs={}
    for name in ('summary_test.csv','thresholds_validation.csv','cell_counts.csv','bootstrap_ids.csv'):
        p=score/name;p.write_text('method,value\nM1,1\nM5,2\n');refs[name]=p.relative_to(tmp_path).as_posix()
    (score/'bootstrap_weights.npy').write_bytes(b'weights');refs['bootstrap_weights.npy']=(score/'bootstrap_weights.npy').relative_to(tmp_path).as_posix()
    retained={}
    for step in receipt['steps']:
        b=c['completed_steps'][step['name']];d=tmp_path/b['out_dir']
        b['files']={} if step['name']=='env' else {p.relative_to(tmp_path).as_posix():M.sha(p) for p in d.rglob('*') if p.is_file()}
        retained.update(b['files'])
    c['retained_files']=retained
    r.inventory['source_controls']={k:v for k,v in r.inventory['source_controls'].items() if (tmp_path/k).is_file()}
    r.inventory['source_controls'].update(retained)
    r.validate_reproduction_continuation(ledger)  # Actual fail-closed evidence gate.
    r.repo=tmp_path/'repo';r.repo.mkdir();r.output=tmp_path/'new-output';r.output.mkdir()
    r.adopted=r.output/'adopted';r.adopted.mkdir();layout={'fits':{},'predictions':{},'cite_predictions':{}}
    for arm in ('A','B'):
        for m in M.METHODS:
            d=r.adopted/arm/m;d.mkdir(parents=True);(d/'predictions_fixture.parquet').write_bytes(b'predictions')
            layout['fits'][arm+':'+m]=layout['predictions'][arm+':'+m]=str(d.relative_to(r.adopted))
    for m in M.METHODS:
        d=r.adopted/'cite'/m;d.mkdir(parents=True);(d/'predictions_fixture.parquet').write_bytes(b'cite')
        layout['cite_predictions'][m]=str(d.relative_to(r.adopted))
    for name in ('data','cite'):(r.adopted/name).mkdir(exist_ok=True);layout[name]=name
    (r.adopted/'data/features.json').write_text('{}')
    d03=tmp_path/'d03.json';d03.write_text('{}');layout['d03_features']='d03.json';layout['equality_references']=refs
    layout['checkpoint_sidecars']={};layout['materialize']=[]
    for arm in ('A','B'):
        checkpoint=r.adopted/arm/'M6/scanvi';checkpoint.mkdir();(checkpoint/'weights.pt').write_bytes(b'fixture weights')
        side=r.adopted/(arm+'-checkpoint.json');M.dump(side,{'weights.pt':M.sha(checkpoint/'weights.pt')})
        layout['checkpoint_sidecars'][arm]=side.relative_to(r.adopted).as_posix()
    # Source-relative layout and inventory permit the real hash-checked copying implementation.
    prefix=r.adopted.relative_to(tmp_path)
    for category in ('fits','predictions','cite_predictions','checkpoint_sidecars'):
        layout[category]={k:(prefix/v).as_posix() for k,v in layout[category].items()}
    for category in ('data','cite'):layout[category]=(prefix/layout[category]).as_posix()
    r.inventory['adopted_files']={p.relative_to(tmp_path).as_posix():M.sha(p) for p in r.adopted.rglob('*') if p.is_file()}
    r.inventory['readonly_references']={v:M.sha(tmp_path/v) for v in refs.values()}|{'d03.json':M.sha(d03)}
    r.inventory['layout']=layout
    monkeypatch.setattr(M.RM,'parse_eligibility',lambda path:{'n_eligible':2})
    old=rp.parent;c['failed_output_dir']=str(old.relative_to(tmp_path))
    original_manifest={'mode':'F','fresh_execution':True,'schema':'fixture','provenance':{'scope':'preserved'},'protein_classes':{}}
    M.dump(old/'comparison_manifest.json',original_manifest);(old/'results.json').write_text('{"original": 2}\n')
    c['retained_metadata']={p.relative_to(tmp_path).as_posix():M.sha(p) for p in (old/'comparison_manifest.json',old/'results.json')}
    r.inventory['source_controls'].update(c['retained_metadata'])
    canonical_fixture(r,tmp_path,monkeypatch)
    receipt.update(environment={'pinned':'fixture'},models={'A':{},'B':{}});r.retained_receipt=receipt
    r.receipt={'steps':[],'stage':'reproduction','version':M.VERSION,'mode':'F'}
    r.cfg={'stage_seconds':{'reproduction':26700}};r.prior=M.PRIOR_SECONDS;r.clock=lambda:1;r.started=1
    r.ledger=M.Ledger(tmp_path/'runtime.m5-invocations.json','repair');r.step_used={};r.paper_used=0
    r.python=str(r.repo/'.venv/bin/python');calls=[];environment_checks=[]
    def runner(argv,name,timeout):
        calls.append((name,argv))
        if name=='env_setup':
            p=Path(r.python);p.parent.mkdir(parents=True);p.write_text('synthetic pinned python')
        if name=='compare':Path(argv[argv.index('--out')+1]).write_text('{"status":"pass"}')
        if name=='paper_build':
            p=r.repo/'paper/build/main.pdf';p.parent.mkdir(parents=True);p.write_bytes(b'%PDF-synthetic')
        assert Path(r.python).exists(), 'Environment must precede interpreter use'
        return {'status':'ok','returncode':0}
    r.runner=runner
    monkeypatch.setattr(r,'environment_check',lambda:environment_checks.append(True))
    before=M.load(r.ledger.path)['m5_seed_repair']
    r.run_reproduction_continuation()
    after=M.load(r.ledger.path)['m5_seed_repair']
    assert before['fit_invocations']==after['fit_invocations'] and before['score_invocations']==after['score_invocations']
    assert [name for name,argv in calls]==['env_setup','compare','paper_assets','paper_build']
    assert calls[0][1]==['uv','sync','--frozen'] and environment_checks==[True]
    assert [s['name'] for s in r.receipt['steps'][:8]]==NAMES
    assert all(s['executed'] is False for s in r.receipt['steps'][:8])
    assert all(s['executed'] is True for s in r.receipt['steps'][8:])
    assert r.receipt['status']=='complete'
    assert (r.output/'results.json').read_bytes()==(old/'results.json').read_bytes()
    assert M.load(r.output/'comparison_manifest.json')['provenance']==original_manifest['provenance']
