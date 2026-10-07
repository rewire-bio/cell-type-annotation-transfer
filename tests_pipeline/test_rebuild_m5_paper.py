"""Synthetic paper-only rebuild gates. No scientific computation."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import rebuild_m5_paper as P
import m5_seed_repair as M
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_continue_m5_comparison as OLD

def fixture(tmp_path):
    r,ledger,oldreceipt,rp=OLD.fixture(tmp_path);r.__class__=P.PaperRebuild
    pid='failed';r.repo=tmp_path/'current';r.repo.mkdir()
    steps=oldreceipt['steps']
    for s in steps:
        s.update(executed=False,source_reproduction='c056e758da6842f59e611930ec06bb17',source_command=s.pop('command'),
                 source_step_sha256='original-source-step',copied_files_sha256={})
    for name,kind in [('env_setup','env'),('compare','compare'),('paper_assets','paper'),('paper_build','paper')]:
        steps.append({'name':name,'kind':kind,'status':'ok','returncode':0,'executed':True})
    receipt=oldreceipt;receipt.update(status='complete',environment={'pinned':'fixture'},models={'A':{},'B':{}})
    M.dump(rp,receipt);folder=rp.parents[4]
    assert folder.name==pid
    parent_manifest={'status':'completed','exit_code':0,'science_hash':'science','protocol_hash':'protocol','manuscript_hash':'oldmanuscript'}
    M.dump(folder/'manifest.json',parent_manifest)
    oldpaper=folder/'checkout/paper/main.tex';oldpaper.parent.mkdir();oldpaper.write_text('old paper')
    newpaper=r.repo/'paper/main.tex';newpaper.parent.mkdir();newpaper.write_text('corrected paper')
    review=tmp_path/'old-review.md';review.write_text('FAIL: correction needed')
    for p in (rp,folder/'manifest.json',review):r.inventory['source_controls'][p.relative_to(tmp_path).as_posix()]=M.sha(p)
    c=r.reproduction_continuation
    c.pop('failed_manifest_sha256');c.pop('failed_receipt_sha256')
    c.update(parent_manifest_sha256=M.sha(folder/'manifest.json'),parent_receipt_sha256=M.sha(rp),
        parent_output_dir=rp.parent.relative_to(tmp_path).as_posix(),frozen_parent_manuscript_hash='oldmanuscript',
        paper_change={'path':'paper/main.tex','old_sha256':M.sha(oldpaper),'new_sha256':M.sha(newpaper)},
        prior_paper_review={'path':'old-review.md','sha256':M.sha(review)})
    for step in steps[:8]:
        b=c['completed_steps'][step['name']];b['step_sha256']=M.object_sha256(step);b['command']=step['source_command'];b['original_source_reproduction']=step['source_reproduction'];b['original_source_step_sha256']=step['source_step_sha256']
    for key,path in [('operational_helper','scripts/rebuild_m5_paper.py'),('operational_test','tests_pipeline/test_rebuild_m5_paper.py')]:
        p=r.repo/path;p.parent.mkdir(exist_ok=True);p.write_text('synthetic bound source');c[key]={'path':path,'sha256':M.sha(p)}
    for name in ('results.json','comparison_manifest.json'):M.dump(rp.parent/name,{'fixture':'preserved'})
    c['retained_metadata']={p.relative_to(tmp_path).as_posix():M.sha(p) for p in (rp.parent/'results.json',rp.parent/'comparison_manifest.json')}
    r.inventory['source_controls'].update(c['retained_metadata'])
    r.inventory.update(paper_rebuild_of=pid,target_science_hash='science',target_protocol_hash='protocol')
    r.ledger=M.Ledger(tmp_path/'runtime.m5-invocations.json','repair')
    return r,ledger,rp,folder/'manifest.json'

def test_completed_parent_and_explicit_new_paper(tmp_path):
    r,ledger,*_=fixture(tmp_path);r.validate_paper_rebuild(ledger)
    assert len(r.retained_receipt['steps'])==12

@pytest.mark.parametrize('change',['parent_status','parent_hash','science','protocol','paper_old','paper_new','review','step','source','bytes','metadata','helper','test','ledger','union','extra_file'])
def test_paper_only_gate_rejects_changes(tmp_path,change):
    r,ledger,rp,mp=fixture(tmp_path);c=r.reproduction_continuation
    if change=='parent_status':
        x=M.load(mp);x['status']='failed';M.dump(mp,x)
    if change=='parent_hash':c['parent_receipt_sha256']='bad'
    if change=='science':r.inventory['target_science_hash']='newscience'
    if change=='protocol':r.inventory['target_protocol_hash']='newprotocol'
    if change=='paper_old':c['paper_change']['old_sha256']='bad'
    if change=='paper_new':(r.repo/'paper/main.tex').write_text('unapproved edit')
    if change=='review':(tmp_path/'old-review.md').write_text('changed')
    if change=='step':c['completed_steps']['score']['step_sha256']='bad'
    if change=='source':
        x=M.load(rp);x['steps'][1]['source_reproduction']='other';M.dump(rp,x)
    if change=='bytes':(tmp_path/next(iter(c['retained_files']))).write_bytes(b'changed')
    if change=='metadata':c['retained_metadata']={}
    if change=='helper':(r.repo/'scripts/rebuild_m5_paper.py').write_text('changed')
    if change=='test':c['operational_test']['sha256']='bad'
    if change=='ledger':M.dump(r.ledger.path,{})
    if change=='union':c['retained_files']={}
    if change=='extra_file':(tmp_path/c['completed_steps']['score']['out_dir']/'extra').write_text('extra')
    with pytest.raises(M.Stop):r.validate_paper_rebuild(ledger)

@pytest.mark.parametrize('name,kind',[('fit','fit'),('A_M5_fit','fit'),('predict','predict'),('score','score'),('protein','protein'),('acquire','env')])
def test_scientific_calls_refused(name,kind):
    r=object.__new__(P.PaperRebuild)
    with pytest.raises(M.Stop):r.step(name,kind,lambda out:[])

def test_full_paper_rebuild_orchestration(tmp_path,monkeypatch):
    """Run actual continuation/copy/assembly/finalization with synthetic subprocesses."""
    r,ledger,rp,mp=fixture(tmp_path);receipt=M.load(rp)
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
    for step in receipt['steps'][:8]:
        b=c['completed_steps'][step['name']];d=tmp_path/b['out_dir']
        b['files']={} if step['name']=='env' else {p.relative_to(tmp_path).as_posix():M.sha(p) for p in d.rglob('*') if p.is_file()}
        retained.update(b['files'])
    c['retained_files']=retained
    r.inventory['source_controls']={k:v for k,v in r.inventory['source_controls'].items() if (tmp_path/k).is_file()}
    r.inventory['source_controls'].update(retained)
    r.validate_paper_rebuild(ledger)  # Actual fail-closed evidence gate.
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
    old=rp.parent;c['parent_output_dir']=str(old.relative_to(tmp_path))
    original_manifest={'mode':'F','fresh_execution':True,'schema':'fixture','provenance':{'scope':'preserved'},'protein_classes':{}}
    M.dump(old/'comparison_manifest.json',original_manifest);(old/'results.json').write_text('{"original": 2}\n')
    c['retained_metadata']={p.relative_to(tmp_path).as_posix():M.sha(p) for p in (old/'comparison_manifest.json',old/'results.json')}
    r.inventory['source_controls'].update(c['retained_metadata'])
    OLD.canonical_fixture(r,tmp_path,monkeypatch)
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
    assert [s['name'] for s in r.receipt['steps'][:8]]==OLD.NAMES
    assert all(s['executed'] is False for s in r.receipt['steps'][:8])
    assert all(s['executed'] is True for s in r.receipt['steps'][8:])
    assert r.receipt['status']=='complete'
    assert (r.output/'results.json').read_bytes()==(old/'results.json').read_bytes()
    assert M.load(r.output/'comparison_manifest.json')['provenance']==original_manifest['provenance']
