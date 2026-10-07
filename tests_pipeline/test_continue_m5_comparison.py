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
        'repair_id':'repair','fit_invocations':[{'stage':s,'arm':a} for s in ('canonical','reproduction') for a in ('A','B')],
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

def test_baseline_required_before_execution(tmp_path,monkeypatch):
    r=object.__new__(C.ComparisonContinuation);r.reproduction_continuation=None
    monkeypatch.delenv('CELLTRANSFER_BASELINE_MANIFEST',raising=False)
    with pytest.raises(M.Stop):r.baseline_check()
    p=tmp_path/'baseline.json';p.write_text('{}');r.approval={'canonical_manifest_sha256':M.sha(p)}
    monkeypatch.setenv('CELLTRANSFER_BASELINE_MANIFEST',str(p));assert r.baseline_check()==p
    p.write_text('{"changed":true}')
    with pytest.raises(M.Stop):r.baseline_check()
