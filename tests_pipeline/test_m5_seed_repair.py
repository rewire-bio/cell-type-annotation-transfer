"""Synthetic approval/adoption contracts; no fitting, prediction or scoring."""
import csv
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import m5_seed_repair as M

OLD='''class Unaffected:
    pass
class CellTypistRetrained:
    def fit(self,x):
        return celltypist.train(x,n_jobs=4)
'''
NEW=OLD.replace('n_jobs=4','n_jobs=4,random_state=0')

def put(root,name,text='fixture'):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);return name

def inventory(root):
    layout={'fits':{},'predictions':{},'cite_predictions':{},'checkpoint_sidecars':{},'data':'data','cite':'cite','materialize':[]}
    files={};refs={}
    def file(name,text='fixture'):
        put(root,name,text);files[name]=M.sha(root/name)
    for arm in ('A','B'):
        for method in M.METHODS:
            for kind in ('fits','predictions'):
                directory=f'{kind}/{arm}/{method}';layout[kind][arm+':'+method]=directory;file(directory+'/output.txt')
        sidecar=f'sidecars/{arm}.json';file(sidecar,'{}');layout['checkpoint_sidecars'][arm]=sidecar
    for method in M.METHODS:
        d=f'cite_predictions/{method}';layout['cite_predictions'][method]=d;file(d+'/pred.txt')
    file('data/features.json');file('cite/eligibility.json')
    for name in ('summary_test.csv','thresholds_validation.csv','cell_counts.csv','bootstrap_ids.csv','bootstrap_weights.npy','d03.json'):
        relative=put(root,'refs/'+name);refs[relative]=M.sha(root/relative)
    layout['d03_features']='refs/d03.json';layout['equality_references']={n:'refs/'+n for n in ('summary_test.csv','thresholds_validation.csv','cell_counts.csv','bootstrap_ids.csv','bootstrap_weights.npy')}
    return {'adopted_files':files,'readonly_references':refs,'source_controls':{},'layout':layout,'approval':{'path':'approval.json','sha256':'placeholder'}}

@pytest.mark.parametrize('replacement',['random_state=1','random_state=None','random_state=False'])
def test_wrong_seed_refused(replacement):
    with pytest.raises(M.Stop):M.validate_seed_delta(OLD,NEW.replace('random_state=0',replacement))

def test_only_seed_change_allowed():
    M.validate_seed_delta(OLD,NEW)
    with pytest.raises(M.Stop):M.validate_seed_delta(OLD,NEW.replace('class Unaffected:\n    pass','class Unaffected:\n    x=1'))
    with pytest.raises(M.Stop):M.validate_seed_delta(OLD,NEW.replace('n_jobs=4','n_jobs=2'))

def test_missing_changed_source_identity(tmp_path):
    put(tmp_path,'old.py',OLD);put(tmp_path,'companion/src/celltransfer/methods.py',NEW);put(tmp_path,'scientific.py')
    cfg={'identity':{'scientific_files':{'scientific.py':M.sha(tmp_path/'scientific.py')},'original_methods':'old.py','original_methods_sha256':M.sha(tmp_path/'old.py'),'seeded_methods_sha256':M.sha(tmp_path/'companion/src/celltransfer/methods.py')}}
    M.validate_identity(tmp_path,cfg)
    (tmp_path/'scientific.py').write_text('changed')
    with pytest.raises(M.Stop):M.validate_identity(tmp_path,cfg)
    (tmp_path/'scientific.py').unlink()
    with pytest.raises(M.Stop):M.validate_identity(tmp_path,cfg)

@pytest.mark.parametrize('change',['corrupt','missing','M5','extra','link','role','reference','forbidden'])
def test_inventory_fail_closed(tmp_path,change):
    inv=inventory(tmp_path);M.verify_inventory(tmp_path,inv)
    p=tmp_path/'fits/A/M1/output.txt'
    if change=='corrupt':p.write_text('corrupt')
    if change=='missing':p.unlink()
    if change=='M5':
        relative=put(tmp_path,'fits/A/M5/model.pkl');inv['adopted_files'][relative]=M.sha(tmp_path/relative)
    if change=='extra':put(tmp_path,'fits/A/M1/unlisted.txt')
    if change=='link':(tmp_path/'fits/A/M1/unlisted').symlink_to(p)
    if change=='role':inv['layout']['fits']['A:M5']=inv['layout']['fits'].pop('A:M1')
    if change=='reference':(tmp_path/'refs/d03.json').write_text('changed')
    if change=='forbidden':inv['forbidden_adoption_prefixes']=['fits/A/M1']
    with pytest.raises(M.Stop):M.verify_inventory(tmp_path,inv)

def test_payload_no_circularity_or_sealed_change(tmp_path):
    inv=inventory(tmp_path);digest=M.inventory_payload_sha256(inv)
    inv['approval']['sha256']='different';inv['source_controls']['approval.json']='different'
    inv.update(source_inventory_sha256='sealed',parent_config_path='cfg',parent_source_manifest_sha256='parent',canonical_manifest_sha256='dynamic')
    assert M.inventory_payload_sha256(inv)==digest
    inv['adopted_files']['data/features.json']='changed'
    assert M.inventory_payload_sha256(inv)!=digest

def test_shared_four_fit_two_score_cap(tmp_path):
    l=M.Ledger(tmp_path/'fits.json','repair')
    with pytest.raises(M.Stop):l.reserve('fit','reproduction','A')
    for stage in ('canonical','reproduction'):
        for arm in ('A','B'):l.reserve('fit',stage,arm)
        l.reserve('score',stage)
    with pytest.raises(M.Stop):l.reserve('fit','canonical','A')
    with pytest.raises(M.Stop):l.reserve('score','reproduction')
    assert len(M.load(l.path)['m5_seed_repair']['fit_invocations'])==4

def test_failed_fit_reservation_cannot_retry(tmp_path):
    l=M.Ledger(tmp_path/'fits.json','repair');l.reserve('fit','canonical','A')
    with pytest.raises(M.Stop):l.reserve('fit','canonical','A')

def test_cumulative_time_cannot_reset(tmp_path):
    l=M.Ledger(tmp_path/'fits.json','repair');l.charge('canonical',100)
    l.charge('canonical',1);assert M.load(l.path)['m5_seed_repair']['driver_stage_seconds']['canonical']==100
    l.charge('reproduction',10)
    with pytest.raises(M.Stop):l.charge('reproduction',M.CAP_SECONDS-M.PRIOR_SECONDS)

@pytest.mark.parametrize('name,kind',[('A_M1_fit','fit'),('arbitrary','fit'),('A_M5_fit','predict')])
def test_non_m5_fit_calls_refused(name,kind):
    r=object.__new__(M.Repair)
    with pytest.raises(M.Stop):r.step(name,kind,lambda out:[])

def test_unapproved_preflight_no_outputs(tmp_path,monkeypatch):
    monkeypatch.delenv('RESEARCH_ADOPTION_STAGE',raising=False)
    out=tmp_path/'out'
    with pytest.raises(M.Stop):M.Repair(tmp_path,{},tmp_path/'cfg.json',out,preflight=True)
    assert not out.exists()

def test_non_m5_equality_and_t1_weights(tmp_path):
    new=tmp_path/'new';ref=tmp_path/'ref';new.mkdir();ref.mkdir();refs={}
    names=('summary_test.csv','thresholds_validation.csv','cell_counts.csv','bootstrap_ids.csv')
    for name in names:
        for d in (new,ref):(d/name).write_text('method,value\nM1,1\nM5,2\n')
        refs[name]=ref/name
    for d in (new,ref):(d/'bootstrap_weights.npy').write_bytes(b'weights')
    refs['bootstrap_weights.npy']=ref/'bootstrap_weights.npy'
    (new/names[0]).write_text('method,value\nM5,9\nM1,1\n');M.equal_non_m5(new,refs)
    (new/names[0]).write_text('method,value\nM1,2\nM5,9\n')
    with pytest.raises(M.Stop):M.equal_non_m5(new,refs)
    (new/names[0]).write_text('method,value\nM1,1\nM5,9\n');(new/'bootstrap_weights.npy').write_bytes(b'changed')
    with pytest.raises(M.Stop):M.equal_non_m5(new,refs)

def approved_fixture(tmp_path,monkeypatch):
    repo=tmp_path/'repo';source=tmp_path/'source';repo.mkdir();source.mkdir()
    inv=inventory(source);inv.update(schema_version=1,stage='canonical',parent_id=M.FRESH_PARENT,
                                   repair_id='synthetic-only',target_protocol_hash='protocol',target_science_hash='science')
    cfg={'execution_ready':True,'version':M.VERSION,'proposal':'proposal.md','execution_note':'note.md',
         'guard':{'threads':4,'mem_limit_gib':12,'storage_cap_gib':7},'step_ceilings_s':M.LIMITS,
         'stage_seconds':{'canonical':21900,'reproduction':26700}}
    for p,text in [('original.py',OLD),('companion/src/celltransfer/methods.py',NEW),('scientific.py','same'),('proposal.md','plan'),('note.md','note')]:put(repo,p,text)
    cfg['identity']={'scientific_files':{'scientific.py':M.sha(repo/'scientific.py')},'original_methods':'original.py',
                     'original_methods_sha256':M.sha(repo/'original.py'),'seeded_methods_sha256':M.sha(repo/'companion/src/celltransfer/methods.py')}
    config=repo/'cfg.json';M.dump(config,cfg)
    approval={'status':'approved','repair_id':'synthetic-only','protocol_hash':'protocol','target_protocol_hash':'protocol',
              'target_science_hash':'science','option':'R','user_reply':'synthetic test only','approved_by':'synthetic fixture',
              'version':M.VERSION,'original_run_id':M.ORIGINAL_RUN,'parent_reproduction_id':M.FRESH_PARENT,
              'fit_invocations':4,'score_invocations':2,'worker_call_cap':24,'total_seconds':M.CAP_SECONDS,
              'prior_seconds':M.PRIOR_SECONDS,'ledger_choice':'existing-cumulative','proposal_sha256':M.sha(repo/'proposal.md'),
              'execution_note_sha256':M.sha(repo/'note.md'),'repair_config_sha256':M.sha(config),
              'inventory_payload_sha256':{'canonical':M.inventory_payload_sha256(inv)}}
    approval_path=source/'approval.json';M.dump(approval_path,approval);inv['approval']['sha256']=M.sha(approval_path)
    invpath=source/'inventory.json';M.dump(invpath,inv)
    env={'STAGE':'canonical','SOURCE_ROOT':str(source),'INVENTORY':str(invpath),'APPROVAL':str(approval_path),
         'PRIOR_SECONDS':str(M.PRIOR_SECONDS),'LEDGER':str(tmp_path/'runtime.json')}
    for key,value in env.items():monkeypatch.setenv('RESEARCH_ADOPTION_'+key,value)
    return repo,source,cfg,config,inv,invpath,approval,approval_path

def test_actual_harness_empty_output_contract(tmp_path,monkeypatch):
    repo,source,cfg,config,*_=approved_fixture(tmp_path,monkeypatch)
    out=tmp_path/'output';out.mkdir()
    r=M.Repair(repo,cfg,config,out,preflight=True)
    assert list(out.iterdir())==[]
    assert r.ledger.path.name=='runtime.m5-invocations.json'
    (out/'history.txt').write_text('old')
    with pytest.raises(M.Stop):M.Repair(repo,cfg,config,out,preflight=True)
    alias=tmp_path/'alias';alias.symlink_to(tmp_path/'empty',target_is_directory=True);(tmp_path/'empty').mkdir()
    with pytest.raises(M.Stop):M.Repair(repo,cfg,config,alias,preflight=True)

@pytest.mark.parametrize('change',['status','config','seed','payload','parent','scope','approvalhash'])
def test_approved_gate_fail_closed(tmp_path,monkeypatch,change):
    repo,source,cfg,config,inv,invpath,approval,ap=approved_fixture(tmp_path,monkeypatch)
    if change=='status':approval['status']='prepared'
    if change=='config':config.write_text(config.read_text()+' ')
    if change=='seed':(repo/'companion/src/celltransfer/methods.py').write_text(NEW.replace('random_state=0','random_state=1'))
    if change=='payload':inv['layout']['data']='changed'
    if change=='parent':inv['parent_id']='different'
    if change=='scope':approval['fit_invocations']=5
    if change=='approvalhash':approval['approved_by']='changed'
    M.dump(ap,approval)
    if change!='approvalhash':inv['approval']['sha256']=M.sha(ap)
    M.dump(invpath,inv)
    with pytest.raises(M.Stop):M.Repair(repo,cfg,config,tmp_path/'out',preflight=True)
    assert not (tmp_path/'out').exists()

def test_materialize_pins_and_copy_only_adopted(tmp_path,monkeypatch):
    repo,source,cfg,config,inv,invpath,approval,ap=approved_fixture(tmp_path,monkeypatch)
    pin=put(source,'runs/data/pinned.dat','pinned');inv['adopted_files'][pin]=M.sha(source/pin);inv['layout']['materialize']=[pin]
    # Real checkpoints are hash-bound and must match copied M6 files.
    for arm in ('A','B'):
        name=f'fits/{arm}/M6/scanvi/weights.pt';put(source,name,'checkpoint');inv['adopted_files'][name]=M.sha(source/name)
        side=inv['layout']['checkpoint_sidecars'][arm];M.dump(source/side,{'weights.pt':M.sha(source/name)});inv['adopted_files'][side]=M.sha(source/side)
    approval['inventory_payload_sha256']['canonical']=M.inventory_payload_sha256(inv);M.dump(ap,approval)
    inv['approval']['sha256']=M.sha(ap);M.dump(invpath,inv)
    r=M.Repair(repo,cfg,config,tmp_path/'out');r.copy_inputs()
    assert (repo/pin).read_text()=='pinned'
    assert not (r.adopted/pin).exists()
    assert not (r.adopted/'refs/d03.json').exists()
    assert (source/'refs/d03.json').read_text()=='fixture'
    for name,digest in inv['adopted_files'].items():assert M.sha(repo/name if name==pin else r.adopted/name)==digest
    assert not Path(monkeypatch.getenv('RESEARCH_ADOPTION_LEDGER') if hasattr(monkeypatch,'getenv') else tmp_path/'runtime.json').exists()

def test_canonical_existing_pins_same_file_no_copy_error(tmp_path,monkeypatch):
    repo,source,cfg,config,inv,invpath,approval,ap=approved_fixture(tmp_path,monkeypatch)
    pin=put(source,'runs/data/pinned.dat','pinned');inv['adopted_files'][pin]=M.sha(source/pin);inv['layout']['materialize']=[pin]
    for arm in ('A','B'):
        name=f'fits/{arm}/M6/scanvi/weights.pt';put(source,name,'checkpoint');inv['adopted_files'][name]=M.sha(source/name)
        side=inv['layout']['checkpoint_sidecars'][arm];M.dump(source/side,{'weights.pt':M.sha(source/name)});inv['adopted_files'][side]=M.sha(source/side)
    approval['inventory_payload_sha256']['canonical']=M.inventory_payload_sha256(inv);M.dump(ap,approval)
    inv['approval']['sha256']=M.sha(ap);M.dump(invpath,inv)
    # A canonical harness invokes the driver in the existing source study itself.
    import shutil
    for name in cfg['identity']['scientific_files']|{cfg['identity']['original_methods']:'', 'companion/src/celltransfer/methods.py':'',cfg['proposal']:'',cfg['execution_note']:''}:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/name,target)
    shutil.copyfile(config,source/'cfg.json')
    r=M.Repair(source,cfg,source/'cfg.json',tmp_path/'out');r.copy_inputs()
    assert (source/pin).read_text()=='pinned'

def test_materialization_alias_parent_refused(tmp_path):
    root=tmp_path/'repo';root.mkdir();outside=tmp_path/'elsewhere';outside.mkdir()
    (root/'runs').symlink_to(outside,target_is_directory=True)
    with pytest.raises(M.Stop):M.inside(root,'runs/data/pin')

def test_failed_preflight_never_saves(tmp_path,monkeypatch):
    repo,source,cfg,config,inv,invpath,approval,ap=approved_fixture(tmp_path,monkeypatch)
    put(source,'.venv/bin/python','not executed')
    output=tmp_path/'out'
    monkeypatch.setattr(M,'HERE',repo/'scripts')
    monkeypatch.setattr(M.Repair,'environment_check',lambda self,persist=True: (_ for _ in ()).throw(M.Stop('synthetic missing package')))
    monkeypatch.setattr(sys,'argv',['m5_seed_repair.py','--stage','canonical','--config',str(config),'--output',str(output),'--preflight'])
    assert M.main()==1
    assert not output.exists()
    assert not (tmp_path/'runtime.json').exists()
    assert not (tmp_path/'runtime.m5-invocations.json').exists()
