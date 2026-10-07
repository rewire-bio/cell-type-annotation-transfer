#!/usr/bin/env python3
"""One explicitly bound comparison/PDF continuation; never fit, predict or score."""
from pathlib import Path
import argparse
import os
import shutil
import sys
import m5_seed_repair as M
from m5_seed_repair import need,sha,load,dump,inside,object_sha256,VERSION,METHODS,RM

class ComparisonContinuation(M.Repair):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.reproduction_continuation=self.inventory.get('reproduction_continuation')
        need(bool(self.inventory.get('reproduction_continue_of')) and isinstance(self.reproduction_continuation,dict),
             'Explicit comparison-only continuation required')
        need(not self.continuation,'Canonical and reproduction continuations cannot combine')
        self.validate_reproduction_continuation(Path(os.environ['RESEARCH_ADOPTION_LEDGER']))
        self.baseline_check()
        c=self.reproduction_continuation
        helper=c['operational_helper']
        need(helper['path']=='scripts/continue_m5_comparison.py'
             and sha(inside(self.repo,helper['path']))==helper['sha256'], 'Operational helper binding differs')
        old=inside(self.source,c['failed_output_dir'])
        need(old==inside(self.source,'.research/reproductions/'+self.inventory['reproduction_continue_of']+
                         '/checkout/results/m5-seed0-v2/reproduction'),'Failed output directory binding differs')
        need(set(c['retained_metadata'])=={(old/n).relative_to(self.source).as_posix()
                                         for n in ('results.json','comparison_manifest.json')},'Metadata set differs')
        for relative,digest in c['retained_metadata'].items():
            need(sha(inside(self.source,relative))==digest and self.inventory['source_controls'].get(relative)==digest,
                 'Retained metadata missing/changed')
    def step(self,name,kind,argv_fn):
        need((name,kind) in (('env_setup','env'),('compare','compare'),('paper_assets','paper'),('paper_build','paper')),
             'Comparison continuation refuses scientific/setup invocations')
        return super().step(name,kind,argv_fn)
    def run(self):
        return self.run_reproduction_continuation()
    def baseline_check(self):
        raw=os.environ.get('CELLTRANSFER_BASELINE_MANIFEST')
        need(bool(raw),'Corrected canonical baseline environment binding missing')
        baseline=Path(raw).resolve()
        need(baseline.is_file() and sha(baseline)==self.approval['canonical_manifest_sha256'],
             'Corrected canonical baseline hash differs')
        if self.reproduction_continuation:
            binding=self.reproduction_continuation['canonical_baseline']
            need(baseline==inside(self.source,binding['path']) and sha(baseline)==binding['sha256'],
                 'Continuation canonical baseline binding differs')
        return baseline

    def validate_reproduction_continuation(self,runtime_ledger):
        c=self.reproduction_continuation;a=self.approval
        need(self.stage=='reproduction' and isinstance(c,dict),'Comparison continuation is reproduction-only')
        need(a.get('reproduction_continue_of')==self.inventory['reproduction_continue_of']
             and a.get('reproduction_continuation')==c and a.get('continuation_only') is True
             and a.get('remaining_fits')==0 and a.get('remaining_scores')==0
             and a.get('total_fits')==4 and a.get('total_scores')==2,
             'Explicit comparison-only continuation approval differs')
        folder=inside(self.source,'.research/reproductions/'+self.inventory['reproduction_continue_of'])
        receipt_path=folder/'checkout/results/m5-seed0-v2/reproduction/generation_receipt.json'
        for path,digest in ((folder/'manifest.json',c['failed_manifest_sha256']),(receipt_path,c['failed_receipt_sha256'])):
            need(sha(path)==digest and self.inventory['source_controls'].get(path.relative_to(self.source).as_posix())==digest,
                 'Failed reproduction record binding differs')
        receipt=load(receipt_path);steps=receipt['steps']
        names=['env','A_M5_fit','A_M5_predict','B_M5_fit','B_M5_predict','A_M5_cite','score','protein']
        need(receipt['status']=='stopped' and receipt['stage']=='reproduction' and receipt['version']==VERSION
             and receipt.get('blocker')=="'CELLTRANSFER_BASELINE_MANIFEST'"
             and receipt.get('non_m5_equality',{}).get('status')=='passed'
             and [x['name'] for x in steps]==names
             and all(x['status']=='ok' and x['returncode']==0 and x.get('executed') is True for x in steps),
             'Requires precisely completed independent scientific steps and missing-baseline failure')
        need(set(c['completed_steps'])==set(names),'Completed step set differs')
        retained={}
        for step in steps:
            bound=c['completed_steps'][step['name']]
            need(bound['step_sha256']==object_sha256(step) and bound['command']==step['command'],
                 'Completed independent command/step differs')
            need(inside(self.source,bound['out_dir'])==Path(step['out_dir']).resolve(),'Completed independent directory differs')
            files=bound['files']
            if step['name']=='env':need(files=={},'Environment step must have no retained scientific files')
            else:
                directory=inside(self.source,bound['out_dir'])
                observed={p.relative_to(self.source).as_posix():sha(p) for p in directory.rglob('*') if p.is_file()}
                need(not any(p.is_symlink() for p in directory.rglob('*')) and observed==files and bool(files),
                     'Completed independent output listing changed')
            retained.update(files)
        need(retained==c['retained_files'],'Retained scientific file union differs')
        for relative,digest in retained.items():
            need(self.inventory['source_controls'].get(relative)==digest and sha(inside(self.source,relative))==digest,
                 'Retained scientific output missing/changed')
        snapshot=c['driver_ledger_snapshot'];path=inside(self.source,snapshot['path'])
        need(sha(path)==snapshot['sha256'] and self.inventory['source_controls'].get(snapshot['path'])==snapshot['sha256'],
             'Final invocation snapshot differs')
        state=load(path)['m5_seed_repair']
        need(state['repair_id']==self.inventory['repair_id']
             and [(x['stage'],x.get('arm')) for x in state['fit_invocations']]==
                 [('canonical','A'),('canonical','B'),('reproduction','A'),('reproduction','B')]
             and [x['stage'] for x in state['score_invocations']]==['canonical','reproduction'],
             'Exactly four fit and two score reservations required')
        live=runtime_ledger.with_name(runtime_ledger.stem+'.m5-invocations.json')
        need(sha(live)==snapshot['sha256'],'Live invocation ledger differs; no resetting allowed')
        self.retained_receipt=receipt

    def run_reproduction_continuation(self):
        self.copy_inputs()
        outputs={}
        for step in self.retained_receipt['steps']:
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
                'source_reproduction':self.inventory['reproduction_continue_of'],
                'source_step_sha256':bound['step_sha256'],'source_command':bound['command'],
                'copied_files_sha256':bound['files'],'provenance':'retained completed independent step; no new invocation'})
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
        self.receipt['reproduction_continuation_of']=self.inventory['reproduction_continue_of']
        self.finish_comparison(D,ci,arms,citearm,outputs['score'],outputs['protein'])

    def finish_comparison(self,D,ci,arms,citearm,score,protein):
        c=self.reproduction_continuation
        old=inside(self.source,c['failed_output_dir'])
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
    p.add_argument('--stage',choices=['reproduction'],required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--preflight',action='store_true');a=p.parse_args();r=None
    try:
        need(os.environ.get('RESEARCH_ADOPTION_STAGE')==a.stage,'CLI/harness stage differs')
        r=ComparisonContinuation(Path(__file__).resolve().parent.parent,load(a.config),a.config,a.output,preflight=a.preflight)
        if a.preflight:
            print('Comparison continuation preflight passed; no experiments executed');return 0
        r.run();return 0
    except (M.Stop,RM.ManifestError,OSError,ValueError,KeyError) as exc:
        if r is not None and not a.preflight:r.receipt.update(status='stopped',blocker=str(exc));r.save()
        print('STOPPED: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
