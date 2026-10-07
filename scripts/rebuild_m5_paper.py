#!/usr/bin/env python3
"""Approved paper-only rebuild from preserved results; no scientific invocations."""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path
import m5_seed_repair as M
from m5_seed_repair import need,sha,load,dump,inside,object_sha256,VERSION,METHODS,RM
from continue_m5_comparison import ComparisonContinuation

class PaperRebuild(ComparisonContinuation):
    def __init__(self,repo,cfg,config_path,output,runner=None,clock=time.monotonic,preflight=False):
        self.repo=Path(repo).resolve();self.cfg=cfg;self.output=M.ordinary_output(output)
        self.clock=clock;self.started=clock();self.runner=runner or self.guarded
        need(os.environ.get('RESEARCH_ADOPTION_STAGE')=='reproduction','Explicit reproduction stage required')
        self.stage='reproduction';self.source=Path(os.environ['RESEARCH_ADOPTION_SOURCE_ROOT']).resolve()
        self.inventory_path=Path(os.environ['RESEARCH_ADOPTION_INVENTORY']);self.inventory=load(self.inventory_path)
        self.approval_path=Path(os.environ['RESEARCH_ADOPTION_APPROVAL']);self.approval=load(self.approval_path)
        self.prior=float(os.environ['RESEARCH_ADOPTION_PRIOR_SECONDS'])
        self.reproduction_continuation=self.inventory.get('paper_rebuild');self.continuation=None
        need(isinstance(self.reproduction_continuation,dict) and self.inventory.get('paper_rebuild_of'), 'Paper rebuild proof required')
        need(not self.inventory.get('canonical_continuation') and not self.inventory.get('reproduction_continuation'),'Recovery modes cannot combine')
        need(self.inventory['stage']=='reproduction' and self.inventory['parent_id']==M.FRESH_PARENT,'Immutable adoption stage/parent differs')
        a=self.approval
        need(sha(self.approval_path)==self.inventory['approval']['sha256'] and a.get('status')=='approved'
             and a.get('user_reply') and a.get('approved_by') and a.get('paper_only') is True and a.get('continuation_only') is True
             and a.get('paper_rebuild_of')==self.inventory['paper_rebuild_of'] and a.get('paper_rebuild')==self.reproduction_continuation,
             'Explicit paper-only approval binding differs')
        need(a.get('total_fits')==4 and a.get('total_scores')==2 and a.get('worker_call_cap')==26
             and a.get('total_seconds')==M.CAP_SECONDS and a.get('ledger_choice')=='existing-cumulative'
             and a.get('remaining_fits')==0 and a.get('remaining_scores')==0,'Approved immutable budget differs')
        need(a['inventory_payload_sha256']['reproduction']==M.inventory_payload_sha256(self.inventory),'Inventory approval payload differs')
        need(a['repair_config_sha256']==sha(config_path) and a['target_protocol_hash']==self.inventory['target_protocol_hash']
             and a['target_science_hash']==self.inventory['target_science_hash'],'Scientific/configuration binding differs')
        need(cfg.get('execution_ready') is True and cfg['guard']=={'threads':4,'mem_limit_gib':12,'storage_cap_gib':7}
             and cfg['step_ceilings_s']==M.LIMITS and cfg['stage_seconds']=={'canonical':21900,'reproduction':26700}
             and cfg['version']==VERSION,'Frozen resource/configuration contract differs')
        need(16624.054019914955<=self.prior<M.CAP_SECONDS,'Cumulative runtime cannot reset')
        need(not self.output.exists() or self.output.is_dir() and not any(self.output.iterdir()),'New empty output required')
        M.validate_identity(self.repo,cfg);M.verify_inventory(self.source,self.inventory)
        runtime=Path(os.environ['RESEARCH_ADOPTION_LEDGER'])
        self.ledger=M.Ledger(runtime.with_name(runtime.stem+'.m5-invocations.json'),self.inventory['repair_id'])
        self.validate_paper_rebuild(runtime);self.baseline_check()
        if not preflight:self.output.mkdir(parents=True,exist_ok=True)
        self.receipt={'schema_version':1,'version':VERSION,'stage':'reproduction','status':'running','mode':'F',
                      'scope':'approved paper-only rebuild; all scientific steps retained without invocation',
                      'parent_run':M.ORIGINAL_RUN,'parent_reproduction':M.FRESH_PARENT,
                      'approval_sha256':sha(self.approval_path),'inventory_sha256':sha(self.inventory_path),
                      'prior_seconds':self.prior,'adopted_files':self.inventory['adopted_files'],'steps':[]}
        self.env={'UV_CACHE_DIR':str(self.repo/'.cache-study/uv'),'UV_PROJECT_ENVIRONMENT':str(self.repo/'.venv'),
                  'HF_HOME':str(self.repo/'.cache-study/hf'),'MPLCONFIGDIR':str(self.repo/'.cache-study/mpl'),
                  'PYTHONDONTWRITEBYTECODE':'1','PYTHONWARNINGS':'ignore','PYTHONOPTIMIZE':'0'}
        self.python=str(self.repo/'.venv/bin/python');self.step_used={};self.paper_used=0

    def validate_paper_rebuild(self,runtime):
        c=self.reproduction_continuation;pid=self.inventory['paper_rebuild_of']
        folder=inside(self.source,'.research/reproductions/'+pid)
        old=inside(self.source,c['parent_output_dir'])
        need(old==folder/'checkout/results/m5-seed0-v2/reproduction','Parent output binding differs')
        for path,digest in ((folder/'manifest.json',c['parent_manifest_sha256']),(old/'generation_receipt.json',c['parent_receipt_sha256'])):
            need(sha(path)==digest and self.inventory['source_controls'].get(path.relative_to(self.source).as_posix())==digest,'Completed parent record differs')
        manifest=load(folder/'manifest.json');receipt=load(old/'generation_receipt.json')
        need(manifest['status']=='completed' and manifest['exit_code']==0 and receipt['status']=='complete'
             and manifest['science_hash']==self.inventory['target_science_hash']
             and manifest['protocol_hash']==self.inventory['target_protocol_hash']
             and manifest['manuscript_hash']==c['frozen_parent_manuscript_hash'],'Parent scientific/manuscript identity differs')
        names=['env','A_M5_fit','A_M5_predict','B_M5_fit','B_M5_predict','A_M5_cite','score','protein']
        need([s['name'] for s in receipt['steps']]==names+['env_setup','compare','paper_assets','paper_build']
             and all(s['status']=='ok' and s['returncode']==0 for s in receipt['steps'])
             and all(s.get('executed') is False for s in receipt['steps'][:8])
             and all(s.get('executed') is True for s in receipt['steps'][8:])
             and receipt['non_m5_equality']['status']=='passed','Parent completed step provenance differs')
        need(set(c['completed_steps'])==set(names),'Retain exactly eight scientific/setup provenance steps')
        retained={}
        for step in receipt['steps'][:8]:
            b=c['completed_steps'][step['name']];directory=inside(self.source,b['out_dir'])
            need(b['step_sha256']==object_sha256(step) and b['command']==step['source_command']
                 and directory==Path(step['out_dir']).resolve(),'Retained parent step binding differs')
            need(step['source_reproduction']=='c056e758da6842f59e611930ec06bb17'
                 and b['original_source_reproduction']==step['source_reproduction']
                 and b['original_source_step_sha256']==step['source_step_sha256'],'Independent source lineage differs')
            observed={} if step['name']=='env' else {p.relative_to(self.source).as_posix():sha(p) for p in directory.rglob('*') if p.is_file()}
            need(not any(p.is_symlink() for p in directory.rglob('*')) and observed==b['files'],'Parent output file listing differs')
            retained.update(observed)
        need(retained==c['retained_files'],'Parent scientific file union differs')
        for relative,digest in retained.items():need(self.inventory['source_controls'].get(relative)==digest,'Retained file control differs')
        for relative,digest in c['retained_metadata'].items():
            need(sha(inside(self.source,relative))==digest and self.inventory['source_controls'].get(relative)==digest,'Retained metadata differs')
        need(set(c['retained_metadata'])=={(old/n).relative_to(self.source).as_posix() for n in ('results.json','comparison_manifest.json')},'Metadata set differs')
        paper=c['paper_change'];oldpaper=folder/'checkout/paper/main.tex'
        need(paper['path']=='paper/main.tex' and sha(oldpaper)==paper['old_sha256']
             and sha(self.repo/'paper/main.tex')==paper['new_sha256'] and paper['old_sha256']!=paper['new_sha256'],'Explicit paper-only revision differs')
        review=c['prior_paper_review'];need(sha(inside(self.source,review['path']))==review['sha256']
             and self.inventory['source_controls'].get(review['path'])==review['sha256'],'Original failed paper review differs')
        for key,path in (('operational_helper','scripts/rebuild_m5_paper.py'),('operational_test','tests_pipeline/test_rebuild_m5_paper.py')):
            need(c[key]['path']==path and sha(inside(self.repo,path))==c[key]['sha256'],'Operational source binding differs')
        snapshot=c['driver_ledger_snapshot'];p=inside(self.source,snapshot['path'])
        need(sha(p)==snapshot['sha256'] and self.inventory['source_controls'].get(snapshot['path'])==snapshot['sha256'] and sha(self.ledger.path)==snapshot['sha256'],'Live fixed invocation ledger differs')
        state=load(p)['m5_seed_repair']
        need(state['repair_id']==self.inventory['repair_id'] and len(state['fit_invocations'])==4
             and len(state['score_invocations'])==2,'Four-fit/two-score ledger required')
        self.retained_receipt=receipt
    def run_reproduction_continuation(self):
        self.copy_inputs()
        outputs={}
        for step in self.retained_receipt['steps'][:8]:
            bound=self.reproduction_continuation['completed_steps'][step['name']]
            dest=self.output/VERSION/'continued'/step['name'];dest.mkdir(parents=True)
            original=inside(self.source,bound['out_dir'])
            for relative,digest in bound['files'].items():
                src=inside(self.source,relative);target=dest/src.relative_to(original)
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
                need(sha(src)==digest and sha(target)==digest,'Retained independent copy changed')
            outputs[step['name']]=dest
            self.receipt['steps'].append({'name':step['name'],'kind':step['kind'],'attempt':step['attempt'],
                'status':'ok','returncode':0,'executed':False,'wall_seconds':0,'out_dir':str(dest),
                'source_reproduction':self.inventory['paper_rebuild_of'],
                'source_step_sha256':bound['step_sha256'],'source_command':bound['command'],
                'original_source_reproduction':bound['original_source_reproduction'],
                'original_source_step_sha256':bound['original_source_step_sha256'],
                'copied_files_sha256':bound['files'],'provenance':'retained completed independent step; no new invocation'})
            self.receipt['steps'][-1]['original_source_binding']={k:step[k] for k in ('source_reproduction','source_step_sha256','source_command','copied_files_sha256') if k in step}
            self.save()
        self.receipt['environment']=self.retained_receipt['environment']
        self.receipt['models']=self.retained_receipt['models']
        self.step('env_setup','env',lambda out:['uv','sync','--frozen'])
        self.environment_check()
        D,ci=self.role('data'),self.role('cite');elig=RM.parse_eligibility(ci/RM.ELIGIBILITY_FILE)
        need(elig['n_eligible']==2,'Approved eligible CITE inputs changed')
        arms={}
        for arm in ('A','B'):
            sources={m:list(dict.fromkeys([self.role('predictions',arm+':'+m),self.role('fits',arm+':'+m)])) for m in METHODS}
            sources['M5']=[outputs[arm+'_M5_predict'],outputs[arm+'_M5_fit']]
            arms[arm]=RM.assemble_arm(self.output/'arms'/arm,sources)
        citearm=RM.assemble_arm(self.output/'armA_cite',{m:[self.role('cite_predictions',m)] for m in METHODS}|{'M5':[outputs['A_M5_cite']]})
        refs={k:inside(self.source,v) for k,v in self.inventory['layout']['equality_references'].items()}
        M.equal_non_m5(outputs['score'],refs)
        self.receipt['non_m5_equality']=self.retained_receipt['non_m5_equality']
        self.receipt['paper_rebuild_of']=self.inventory['paper_rebuild_of']
        self.finish_comparison(D,ci,arms,citearm,outputs['score'],outputs['protein'])

    def finish_comparison(self,D,ci,arms,citearm,score,protein):
        c=self.reproduction_continuation
        old=inside(self.source,c['parent_output_dir'])
        for name in ('comparison_manifest.json','results.json'):
            relative=(old/name).relative_to(self.source).as_posix()
            need(c['retained_metadata'].get(relative)==sha(old/name)
                 and self.inventory['source_controls'].get(relative)==sha(old/name),'Retained metadata binding differs')
        man=load(old/'comparison_manifest.json')
        need(man['mode']=='F' and man['fresh_execution'] is True,'Original comparison mode differs')
        rel=lambda p:os.path.relpath(p,self.output)
        man.update(arms={'A':[rel(arms['A']),rel(citearm)],'B':[rel(arms['B'])]},data=rel(D),cite=rel(ci),
                   eligibility=rel(ci/RM.ELIGIBILITY_FILE),score={'primary':rel(score)},protein=rel(protein),
                   bootstrap_weights=rel(score/'bootstrap_weights.npy'),
                   d03_features=rel(inside(self.source,self.inventory['layout']['d03_features'])))
        man['protein_classes']={k:rel(protein/Path(v).name) for k,v in man['protein_classes'].items()}
        destination=self.output/'comparison_manifest.json';dump(destination,man)
        shutil.copyfile(old/'results.json',self.output/'results.json')
        need(sha(self.output/'results.json')==sha(old/'results.json'),'Retained aggregate bytes changed')
        report=self.output/'compare/report.json';report.parent.mkdir()
        py=self.python;baseline=self.baseline_check()
        self.step('compare','compare',lambda out:[py,str(self.repo/'scripts/compare_runs.py'),'--original',str(baseline),
            '--reproduction',str(destination),'--tolerances',str(self.repo/'protocol/tolerances-v2.json'),'--out',str(report)])
        target=self.repo/'results/full/results.json';target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(old/'results.json',target)
        self.step('paper_assets','paper',lambda out:[py,str(self.repo/'scripts/make_paper_assets.py'),'--root',str(self.repo),
            '--score',str(score),'--protein',str(protein),'--eligibility',str(ci/RM.ELIGIBILITY_FILE),
            '--comparison',str(report),'--output',str(self.repo/'paper')])
        self.step('paper_build','paper',lambda out:[py,str(self.repo/'scripts/build_paper.py')])
        need((self.repo/'paper/build/main.pdf').is_file(),'PDF missing after build')
        self.receipt['status']='complete';self.save();dump(self.output/'provenance.json',self.receipt)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['reproduction'],required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight',action='store_true');a=p.parse_args();r=None
    try:
        r=PaperRebuild(Path(__file__).resolve().parent.parent,load(a.config),a.config,a.output,preflight=a.preflight)
        if a.preflight:print('Paper-only preflight passed; no scientific invocations');return 0
        r.run();return 0
    except (M.Stop,RM.ManifestError,OSError,ValueError,KeyError) as exc:
        if r is not None and not a.preflight:r.receipt.update(status='stopped',blocker=str(exc));r.save()
        print('STOPPED: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
