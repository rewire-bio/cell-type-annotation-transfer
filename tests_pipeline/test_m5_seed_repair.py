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

def test_array_identity_encoding_matches_metadata_and_refuses_raw():
    import hashlib,struct
    class Array:
        dtype='float64';shape=(2,)
        def tobytes(self):return struct.pack('<dd',1.,2.)
    array=Array()
    assert M.array_identity_sha256(array)==hashlib.sha256(b'float64(2,)'+array.tobytes()).hexdigest()
    assert M.array_identity_sha256(array)!=hashlib.sha256(array.tobytes()).hexdigest()
    array.shape=(1,2)
    assert M.array_identity_sha256(array)!=hashlib.sha256(b'float64(2,)'+array.tobytes()).hexdigest()


def continuation_fixture(tmp_path,monkeypatch):
    repo,source,cfg,config,inv,invpath,approval,ap=approved_fixture(tmp_path,monkeypatch)
    name='.research/runs/failed/output/m5-seed0-v2/out/A_M5_fit-1'
    put(source,name+'/model.pkl','completed seeded A model');put(source,name+'/fit_info.json','{}')
    put(source,'olddata/features.json',(source/'data/features.json').read_text())
    command=[str(source/'.venv/bin/python'),str(source/'companion/scripts/run_matched.py'),'--workspace',str(source),
             '--data',str(source/'olddata'),'--arm','A','--method','M5','--stage','fit','--out',str(source/name)]
    step={'name':'A_M5_fit','kind':'fit','status':'ok','returncode':0,'executed':True,'attempt':1,
          'command':command,'out_dir':str(source/name),'wall_seconds':744}
    receipt='.research/runs/failed/output/generation_receipt.json';manifest='.research/runs/failed/manifest.json'
    M.dump(source/receipt,{'status':'stopped','blocker':'Scaler/genes/classes changed','steps':[
        {'name':'env','status':'ok','returncode':0,'executed':True},step]})
    M.dump(source/manifest,{'status':'failed'})
    snapshot='controls/fit-ledger-snapshot.json';ledger={'m5_seed_repair':{'repair_id':inv['repair_id'],
        'fit_invocations':[{'stage':'canonical','arm':'A'}],'score_invocations':[],'driver_stage_seconds':{'canonical':756}}}
    put(source,snapshot,'{}');M.dump(source/snapshot,ledger);M.dump(tmp_path/'runtime.m5-invocations.json',ledger)
    proof={'failed_manifest_sha256':M.sha(source/manifest),'failed_receipt_sha256':M.sha(source/receipt),
           'driver_ledger_snapshot':{'path':snapshot,'sha256':M.sha(source/snapshot)},
           'completed_fit':{'step':'A_M5_fit','command':command,'step_sha256':M.object_sha256(step),
               'out_dir':name,'files':{p:M.sha(source/p) for p in (name+'/model.pkl',name+'/fit_info.json')}}}
    for p in (receipt,manifest,snapshot,*proof['completed_fit']['files']):inv['source_controls'][p]=M.sha(source/p)
    inv.update(canonical_continue_of='failed',canonical_continuation=proof)
    approval.update(canonical_continue_of='failed',canonical_continuation=proof,continuation_only=True,
                    remaining_canonical_fits=1,independent_fits=2,total_fits=4,total_scores=2)
    approval['inventory_payload_sha256']['canonical']=M.inventory_payload_sha256(inv);M.dump(ap,approval)
    inv['approval']['sha256']=M.sha(ap);M.dump(invpath,inv)
    return repo,source,cfg,config,inv,invpath,approval,ap


def test_completed_A_continuation_no_reservation_or_refit(tmp_path,monkeypatch):
    repo,source,cfg,config,inv,*_=continuation_fixture(tmp_path,monkeypatch)
    r=M.Repair(repo,cfg,config,tmp_path/'output');r.model_check=lambda directory,arm,persist=True:None
    newdata=r.output/'newdata';newdata.mkdir();(newdata/'features.json').write_text((source/'data/features.json').read_text())
    expected=lambda out:[str(repo/'.venv/bin/python'),str(repo/'companion/scripts/run_matched.py'),'--workspace',str(repo),
             '--data',str(newdata),'--arm','A','--method','M5','--stage','fit','--out',str(out)]
    dest=r.continued_fit(expected,newdata)
    assert (dest/'model.pkl').read_text()=='completed seeded A model'
    assert r.receipt['steps'][-1]['executed'] is False
    assert r.receipt['steps'][-1]['source_run']=='failed'
    assert len(M.load(r.ledger.path)['m5_seed_repair']['fit_invocations'])==1
    with pytest.raises(M.Stop):r.ledger.reserve('fit','canonical','A')
    r.ledger.reserve('fit','canonical','B');r.ledger.reserve('score','canonical')
    for arm in ('A','B'):r.ledger.reserve('fit','reproduction',arm)
    r.ledger.reserve('score','reproduction')
    assert len(M.load(r.ledger.path)['m5_seed_repair']['fit_invocations'])==4


@pytest.mark.parametrize('change',['model','info','receipt','ledger','approval'])
def test_continuation_changed_proof_refused(tmp_path,monkeypatch,change):
    repo,source,cfg,config,inv,invpath,approval,ap=continuation_fixture(tmp_path,monkeypatch)
    c=inv['canonical_continuation']
    if change=='model':(source/c['completed_fit']['out_dir']/'model.pkl').write_text('changed')
    if change=='info':(source/c['completed_fit']['out_dir']/'fit_info.json').write_text('changed')
    if change=='receipt':(source/'.research/runs/failed/output/generation_receipt.json').write_text('{}')
    if change=='ledger':M.dump(tmp_path/'runtime.m5-invocations.json',{'m5_seed_repair':{'fit_invocations':[]}})
    if change=='approval':approval['remaining_canonical_fits']=2;M.dump(ap,approval);inv['approval']['sha256']=M.sha(ap);M.dump(invpath,inv)
    with pytest.raises(M.Stop):M.Repair(repo,cfg,config,tmp_path/'output',preflight=True)
    assert not (tmp_path/'output').exists()


def test_continuation_source_command_and_training_inputs_refused(tmp_path,monkeypatch):
    repo,source,cfg,config,inv,*_=continuation_fixture(tmp_path,monkeypatch)
    r=M.Repair(repo,cfg,config,tmp_path/'output');r.model_check=lambda directory,arm,persist=True:None
    newdata=r.output/'newdata';newdata.mkdir();(newdata/'features.json').write_text('wrong data')
    with pytest.raises(M.Stop,match='data differs'):r.continued_fit(lambda out:[],newdata)
    assert len(M.load(r.ledger.path)['m5_seed_repair']['fit_invocations'])==1


def test_continuation_command_mismatch_refused_without_new_fit(tmp_path,monkeypatch):
    repo,source,cfg,config,inv,*_=continuation_fixture(tmp_path,monkeypatch)
    r=M.Repair(repo,cfg,config,tmp_path/'output');r.model_check=lambda directory,arm,persist=True:None
    data=r.output/'newdata';data.mkdir();(data/'features.json').write_text((source/'data/features.json').read_text())
    expected=lambda out:[str(repo/'.venv/bin/python'),str(repo/'companion/scripts/run_matched.py'),'--workspace',str(repo),
             '--data',str(data),'--arm','A','--method','M1','--stage','fit','--out',str(out)]
    with pytest.raises(M.Stop,match='command changes'):r.continued_fit(expected,data)
    assert len(M.load(r.ledger.path)['m5_seed_repair']['fit_invocations'])==1
    assert r.receipt['steps']==[]


@pytest.mark.parametrize('field',['canonical_continue_of','canonical_continuation'])
def test_unpaired_continuation_refused(tmp_path,monkeypatch,field):
    repo,source,cfg,config,inv,invpath,*_=continuation_fixture(tmp_path,monkeypatch)
    inv.pop(field);M.dump(invpath,inv)
    with pytest.raises(M.Stop,match='paired'):M.Repair(repo,cfg,config,tmp_path/'output',preflight=True)
    assert not (tmp_path/'output').exists()
