"""Engineering continuation contracts; fake subprocesses only."""
import copy
import json
import os
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import continue_reproduction as C
import reproduce as R


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


@pytest.fixture
def setup(tmp_path, monkeypatch):
    parent, repo = tmp_path/'parent', tmp_path/'new'
    repo.mkdir(); parent.mkdir()
    cfg = {'mode_f': {'stage_ceiling_s':50400, 'max_attempts':2,
                     'step_ceilings_s':{'env':1800, 'acquire':5400, 'fit':4800, 'predict':1200}},
           'budgets':{'reproduction_seconds':54000, 'paper_seconds':1800},
           'guard':{'threads':4, 'mem_limit_gib':12, 'storage_cap_gib':7}}
    logical = '/original/check'
    od = logical+'/runs/F-old/out/data-1'
    steps = [{'name':'env','kind':'env','status':'ok','attempt':1,'command':['uv','sync','--frozen'],
              'out_dir':None,'wall_seconds':10.,'pool':None},
             {'name':'acquire','kind':'acquire','status':'ok','attempt':1,
              'command':[logical+'/.venv/bin/python','acquire'], 'out_dir':None,'wall_seconds':20.,'pool':'data_acquisition'},
             {'name':'data','kind':'data','status':'ok','attempt':1,
              'command':[logical+'/.venv/bin/python','build',od], 'out_dir':od,'wall_seconds':30.,'pool':'data_acquisition'}]
    for i, status in [(1,'disk-stop'),(2,'disk-start')]:
        steps.append({'name':'B_M6_fit','kind':'fit','status':status,'attempt':i,
                      'command':['fit',logical+f'/runs/F-old/out/B_M6_fit-{i}'], 'out_dir':logical+f'/runs/F-old/out/B_M6_fit-{i}',
                      'wall_seconds':523.8 if i==1 else .001,'pool':'B_arm'})
    receipt = {'mode':'F','fresh_execution':True,'config':cfg,'steps':steps,
               'h_seconds_used':600,'f_seconds_used':600,'prior_seconds_reserved':30}
    receipt_rel = 'runs/F-old/generation_receipt.json'
    write(parent/receipt_rel,json.dumps(receipt))
    write(parent/'runs/F-old/out/data-1/result','science')
    write(parent/'.venv/bin/python','dummy')
    write(parent/'runs/data/input','input')
    (parent/'.venv/bin/link').symlink_to('python')
    roots=['.venv','runs/data','runs/F-old/out/data-1',receipt_rel]
    files={p.relative_to(parent).as_posix():C.digest(p) for p in parent.rglob('*') if p.is_file() and not p.is_symlink()}
    inv={'schema_version':1,'parent_id':'parent-id','receipt':receipt_rel,
         'receipt_sha256':C.digest(parent/receipt_rel),'copy_roots':roots,
         'completed_steps':['env','acquire','data'],'files':files,'symlinks':{'.venv/bin/link':'python'}}
    ip=write(tmp_path/'inventory.json',json.dumps(inv))
    mp=write(tmp_path/'manifest.json',json.dumps({'id':'parent-id','protocol_hash':'ph','status':'failed','code_revision':'rev'}))
    plan=write(repo/'evidence/reviews/disk-continuation-plan.md','Approved plan')
    approval={'parent_id':'parent-id','protocol_hash':'ph','approved_by':'user','user_reply':'continue',
              'plan_sha256':C.digest(plan),'step':'B_M6_fit','additional_guarded_attempts':1,'max_step_seconds':4800}
    write(repo/'evidence/reviews/disk-continuation-approval.json',json.dumps(approval))
    for key,value in {'PARENT':parent,'PARENT_MANIFEST':mp,'PARENT_INVENTORY':ip,'PRIOR_SECONDS':'610'}.items():
        monkeypatch.setenv('RESEARCH_REPRODUCTION_'+key,str(value))
    return parent,repo,cfg,inv,ip,receipt


def create(setup, runner=None):
    _,repo,cfg,_,_,_=setup
    return C.ContinuedRepro(repo,cfg,runner=runner or (lambda *a:{'status':'ok','returncode':0}),now=lambda:1000.)


def test_copy_and_runtime_preserved(setup):
    r=create(setup)
    assert r.f_used == 640
    assert r.t0 == 360
    assert r.pool_used == pytest.approx({'data_acquisition':50,'B_arm':523.801})
    assert (r.repo/'runs/F-old/out/data-1/result').read_text() == 'science'
    assert os.readlink(r.repo/'.venv/bin/link') == 'python'
    r.step('env','env',lambda o:['uv','sync','--frozen'],out=False)
    r.step('acquire','acquire',lambda o:[r.python,'acquire'],out=False)
    od=r.step('data','data',lambda o:[r.python,'build',str(o)])
    assert od == r.repo/'runs/F-old/out/data-1'
    assert r.receipt['steps'][-1]['executed'] is False
    assert r.receipt['steps'][-1]['provenance'] == 'reused-completed-fresh-step'


@pytest.mark.parametrize('kind',['file','link','receipt'])
def test_corrupted_source_refused(setup,kind):
    parent,_,_,_,_,_=setup
    if kind=='file': (parent/'runs/data/input').write_text('changed')
    elif kind=='link':
        p=parent/'.venv/bin/link';p.unlink();p.symlink_to('/different')
    else: (parent/'runs/F-old/generation_receipt.json').write_text('{}')
    with pytest.raises(R.Stop): create(setup)


def test_command_mismatch_refused(setup):
    r=create(setup)
    with pytest.raises(R.Stop,match='command identity'):
        r.step('env','env',lambda o:['uv','sync'],out=False)


def test_partial_fit_cannot_be_selected(setup):
    parent,_,_,inv,ip,_=setup
    bad='runs/F-old/out/B_M6_fit-1'
    p=write(parent/bad/'partial','unfinished')
    inv['files'][bad+'/partial']=C.digest(p)
    inv['copy_roots'].append(bad);ip.write_text(json.dumps(inv))
    with pytest.raises(R.Stop,match='Partial failed fit'): create(setup)


def test_extra_retry_only_once_and_no_other_fit(setup):
    calls=[]
    def runner(*args):
        calls.append(args)
        return {'status':'disk-start','returncode':None}
    r=create(setup,runner)
    r.cursor=len(r.completed)
    with pytest.raises(R.Stop): r.step('B_M6_fit','fit',lambda o:['fit',str(o)])
    assert len(calls)==1 and calls[0][2] <=4800
    assert r.receipt['steps'][-1]['total_attempt']==3
    with pytest.raises(R.Stop,match='allowance exhausted'): r.step('B_M6_fit','fit',lambda o:[])
    with pytest.raises(R.Stop,match='Unapproved extra fit'): r.step('B_M5_fit','fit',lambda o:[])
    assert len(calls)==1


def test_new_destination_copy_checked(setup,monkeypatch):
    real=C.shutil.copytree
    def corrupt(src,dst,*args,**kwargs):
        value=real(src,dst,*args,**kwargs)
        if Path(dst).name=='data-1': (Path(dst)/'result').write_text('replacement')
        return value
    monkeypatch.setattr(C.shutil,'copytree',corrupt)
    with pytest.raises(R.Stop,match='Inventory file differs'): create(setup)


def test_unlisted_link_and_escape_refused(setup):
    parent,_,_,inv,_,_=setup
    (parent/'runs/data/newlink').symlink_to('/escape')
    with pytest.raises(R.Stop,match='Unlisted inventory link'): C.validate_inventory(parent,inv)
    with pytest.raises(R.Stop,match='Unsafe inventory path'): C.safe_path(parent,'../escape')


def test_retry_command_identity_refused(setup):
    calls=[]
    r=create(setup,lambda *args:calls.append(args))
    r.cursor=len(r.completed)
    with pytest.raises(R.Stop,match='Retry command identity'):
        r.step('B_M6_fit','fit',lambda o:['different',str(o)])
    assert not calls
