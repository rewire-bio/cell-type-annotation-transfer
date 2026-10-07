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


def test_receipt_hash_bound_without_copying(setup):
    _,_,_,inv,ip,_=setup
    inv['copy_roots'].remove(inv['receipt'])
    ip.write_text(json.dumps(inv))
    r=create(setup)
    assert not (r.repo/inv['receipt']).exists()
    assert r.receipt['continuation']['receipt_sha256'] == inv['receipt_sha256']
    assert r.receipt['continuation']['parent_steps'] == r.old['steps']


@pytest.fixture
def descendant(setup):
    parent,repo,cfg,inv,ip,ancestor=setup
    cfg['mode_f']['step_ceilings_s']['cite_build']=1200
    logical='/descendant/check'
    steps=[]
    names=['env','acquire','data']+[f'{a}_{m}_{stage}' for a in ('A','B') for m in R.METHODS for stage in ('fit','predict')]
    roots=['.venv','runs/data']
    for name in names:
        kind='env' if name=='env' else ('acquire' if name=='acquire' else ('data' if name=='data' else name.rsplit('_',1)[1]))
        od=None if name in ('env','acquire') else logical+'/runs/'+('F-child' if name.startswith('B_M6') else 'F-old')+'/out/'+name+'-1'
        argv=['uv','sync','--frozen'] if name=='env' else [logical+'/.venv/bin/python', name]
        if od:
            argv+=['--out',od]
            rel=Path(od).relative_to(logical).as_posix()
            write(parent/rel/'result','result '+name)
            roots.append(rel)
        if name in ('A_M6_predict','B_M6_predict'):
            side='runs/'+('F-old' if name.startswith('A') else 'F-child')+'/'+name[:4]+'_checkpoint_sha256.json'
            write(parent/side,'{"model.pt":"abc"}')
            roots.append(side)
            argv+=['--expected-hashes',logical+'/'+side]
        fresh=name.startswith('B_M6')
        steps.append({'name':name,'kind':kind,'status':'ok','attempt':1,'command':argv,'out_dir':od,
                      'pool':'B_arm' if fresh else ('data_acquisition' if name in ('data','acquire') else None),
                      'wall_seconds':40 if fresh and kind=='fit' else (50 if fresh else 0),
                      'executed':fresh,'prior_wall_seconds':30 if not fresh else 0})
    failed={'name':'cite_build','kind':'cite_build','status':'failed','attempt':1,
            'command':[logical+'/.venv/bin/python','cite_build','--out',logical+'/runs/F-child/out/cite_build-1'],
            'out_dir':logical+'/runs/F-child/out/cite_build-1','pool':'cite','wall_seconds':16}
    steps.append(failed)
    old={'mode':'F','fresh_execution':True,'config':cfg,'steps':steps,'prior_seconds_reserved':30,
         'h_seconds_used':780,'f_seconds_used':779,'continuation':{'parent_id':'parent-id','parent_steps':ancestor['steps']}}
    rel='runs/F-child/generation_receipt.json'
    write(parent/rel,json.dumps(old))
    roots.append(rel)
    inv.update(parent_id='child-id',receipt=rel,receipt_sha256=C.digest(parent/rel),
               completed_steps=names,copy_roots=roots)
    inv['files']={p.relative_to(parent).as_posix():C.digest(p) for p in parent.rglob('*') if p.is_file() and not p.is_symlink()}
    ip.write_text(json.dumps(inv))
    mp=Path(os.environ['RESEARCH_REPRODUCTION_PARENT_MANIFEST'])
    mp.write_text(json.dumps({'id':'child-id','status':'failed','protocol_hash':'ph','code_revision':'childrev',
                             'lineage':[{'parent_id':'parent-id'}],'parent_reproduction_id':'parent-id'}))
    return setup


def test_descendant_reuses_all_12_fits_and_preserves_pools(descendant):
    calls=[]
    r=create(descendant,lambda *args:calls.append(args))
    assert r.retry_step=='cite_build'
    assert r.f_used==780
    assert r.pool_used==pytest.approx({'data_acquisition':50,'B_arm':613.801,'cite':16})
    for old in r.completed:
        if '--expected-hashes' in old['command']:
            p=Path(old['command'][old['command'].index('--expected-hashes')+1]).relative_to(r.logical_parent)
            write(r.run_dir/Path(p).name,(r.repo/p).read_text())
        r.step(old['name'],old['kind'],lambda out,old=old:r.normalized(old['command']),out=old['out_dir'] is not None)
    assert not calls
    assert len([x for x in r.receipt['steps'] if x['name'].endswith('_fit')])==12
    assert all(x['executed'] is False for x in r.receipt['steps'])
    with pytest.raises(R.Stop,match='Unapproved extra fit'): r.step('B_M6_fit','fit',lambda out:[])


def test_descendant_cite_only_remaining_attempt(descendant):
    calls=[]
    def runner(*args):
        calls.append(args)
        return {'status':'timeout','returncode':None}
    r=create(descendant,runner);r.cursor=len(r.completed)
    with pytest.raises(R.Stop):
        r.step('cite_build','cite_build',lambda out:[r.python,'cite_build','--out',str(out)])
    assert len(calls)==1
    assert r.receipt['steps'][-1]['total_attempt']==2
    with pytest.raises(R.Stop,match='allowance exhausted'):
        r.step('cite_build','cite_build',lambda out:[])
    assert len(calls)==1


def test_descendant_guarded_missing_input_repair(descendant,monkeypatch):
    import acquire_inputs as acquisition
    items=[acquisition.ITEMS_BY_ID[k] for k in ('sctab-hparams','sctab-var')]
    # Fake pinned input bytes keep this test independent of network/data/models.
    from dataclasses import replace
    for item in items:
        content=('input '+item.id).encode()
        monkeypatch.setitem(acquisition.ITEMS_BY_ID,item.id,replace(item,sha256=__import__('hashlib').sha256(content).hexdigest()))
    calls=[]
    def runner(argv,name,timeout,cwd):
        calls.append((argv,name,timeout))
        for item in items:
            write(cwd/item.dest,'input '+item.id)
        write(cwd/'runs/data/retrieval-manifest.json','new repair receipt')
        return {'status':'ok','returncode':0}
    r=create(descendant,runner)
    original=write(r.repo/'runs/data/retrieval-manifest.json','copied original acquisition')
    r.repair_acquisition()
    assert len(calls)==1 and calls[0][1]=='acquire'
    assert calls[0][0][-5:]==['--only','sctab-hparams','sctab-var','--attempts','1']
    assert original.read_text()=='copied original acquisition'
    assert (r.run_dir/'repair_acquisition/repair-retrieval-manifest.json').read_text()=='new repair receipt'
    assert r.receipt['steps'][-1]['executed'] is True
    assert r.receipt['steps'][-1]['name']=='repair_acquire'
    assert len(r.receipt['continuation']['repair_acquisition']['outputs_sha256'])==2
    assert not any((r.parent/item.dest).exists() for item in items)


@pytest.fixture
def preflight_parent(descendant,monkeypatch):
    parent,repo,cfg,inv,ip,_=descendant
    import acquire_inputs as acquisition
    from dataclasses import replace
    for key in ('sctab-hparams','sctab-var'):
        item=acquisition.ITEMS_BY_ID[key]
        p=write(parent/item.dest,'pinned '+key)
        monkeypatch.setitem(acquisition.ITEMS_BY_ID,key,replace(item,sha256=C.digest(p)))
        inv['files'][item.dest]=C.digest(p)
        inv['copy_roots'].append(item.dest)
    old=json.loads((parent/inv['receipt']).read_text())
    old['continuation']['carried_pool_usage']={'data_acquisition':50,'B_arm':613.801,'cite':16}
    old['continuation']['parent_id']='child-id'
    for step in old['steps'][:-1]:
        step['wall_seconds']=0
        step['executed']=False
    old['steps'][-1].update(total_attempt=2,executed=True,wall_seconds=.04)
    old['steps'].insert(0,{'name':'repair_acquire','kind':'acquire','status':'ok','attempt':1,
                          'command':['repair'],'out_dir':None,'executed':True,'wall_seconds':6,'pool':'data_acquisition'})
    old.update(h_seconds_used=900,f_seconds_used=899)
    (parent/inv['receipt']).write_text(json.dumps(old))
    inv['receipt_sha256']=C.digest(parent/inv['receipt'])
    inv['files'][inv['receipt']]=inv['receipt_sha256']
    inv['parent_id']='108dfa6e36394279931f372749ad6f6c'
    inv['completed_steps'].insert(0,'repair_acquire')
    ip.write_text(json.dumps(inv))
    mp=Path(os.environ['RESEARCH_REPRODUCTION_PARENT_MANIFEST'])
    manifest=json.loads(mp.read_text())
    manifest.update(id=inv['parent_id'],parent_reproduction_id='child-id')
    mp.write_text(json.dumps(manifest))
    return descendant


def extra_approval(setup):
    _,repo,_,inv,_,_=setup
    plan=write(repo/'evidence/reviews/cite-preflight-retry-plan.md','concrete one extra CITE attempt')
    return write(repo/'evidence/reviews/cite-preflight-retry-approval.json',json.dumps({
        'parent_id':inv['parent_id'],'protocol_hash':'ph','step':'cite_build',
        'additional_guarded_attempts':1,'total_attempt':3,'approved_by':'test user',
        'user_reply':'approve this concrete extra attempt','plan_sha256':C.digest(plan)}))


def test_third_cite_refused_without_new_explicit_approval(preflight_parent):
    with pytest.raises(R.Stop,match='requires explicit approval'): create(preflight_parent)


def test_old_approval_cannot_authorize_third_cite(preflight_parent):
    _,repo,_,_,_,_=preflight_parent
    extra_approval(preflight_parent)
    old=json.loads((repo/'evidence/reviews/disk-continuation-approval.json').read_text())
    (repo/'evidence/reviews/cite-preflight-retry-approval.json').write_text(json.dumps(old))
    with pytest.raises(R.Stop,match='approval differs'): create(preflight_parent)


def test_third_cite_out_parent_created_and_only_one_retry(preflight_parent):
    extra_approval(preflight_parent)
    calls=[]
    def runner(argv,name,timeout,cwd):
        out=Path(argv[argv.index('--out')+1])
        assert out.parent.is_dir(), 'builder disk preflight requires existing OUT.parent'
        calls.append(name)
        return {'status':'timeout','returncode':None}
    r=create(preflight_parent,runner)
    assert len(r.completed)==27
    assert r.f_used==900
    assert r.pool_used==pytest.approx({'data_acquisition':56,'B_arm':613.801,'cite':16.04})
    r.repair_acquisition()  # already hash-bound and copied; no subprocess allowed
    assert not calls
    assert len(r.receipt['continuation']['pinned_inputs_verified'])==2
    r.cursor=len(r.completed)
    with pytest.raises(R.Stop):
        r.step('cite_build','cite_build',lambda out:[r.python,'cite_build','--out',str(out)])
    assert calls==['cite_build']
    assert r.receipt['steps'][-1]['total_attempt']==3
    with pytest.raises(R.Stop,match='allowance exhausted'):
        r.step('cite_build','cite_build',lambda out:[])
    with pytest.raises(R.Stop,match='Unapproved extra fit'):
        r.step('A_M1_fit','fit',lambda out:[])
    assert calls==['cite_build']
