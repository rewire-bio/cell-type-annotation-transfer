#!/usr/bin/env python3
"""Read recorded sources and create a NEW adoption inventory; never fit/predict/score.

This utility resolves assembled source aliases to ordinary files inside --source-root.
It writes only --output and new derived M6 checkpoint sidecars beside --output.
Approval/target hashes must be finalized by the coordinator before harness execution.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import m5_seed_repair as M

ORIGINAL_MANIFEST='.research/runs/29879296d87343898100c190308744a1/output/comparison_manifest.json'
FRESH_MANIFEST='.research/reproductions/78542e9d412548edbfe42b38d452f7a8/checkout/runs/F-20261007T103704949889Z/comparison_manifest.json'

def build(root,output,stage,approval,repair_id,target_protocol_hash,target_science_hash,canonical_run_id=None):
    root=root.resolve();output=M.ordinary_output(output)
    M.need(output.is_relative_to(root) and '.research' in output.relative_to(root).parts,'Write inventory only under source study .research')
    M.need(not output.exists(),'Preserve existing inventory; output already exists')
    parent_manifest=root/'.research/reproductions'/M.FRESH_PARENT/'manifest.json'
    parent=M.load(parent_manifest)
    comparison=root/(ORIGINAL_MANIFEST if stage=='canonical' else FRESH_MANIFEST)
    manifest=M.load(comparison);base=comparison.parent
    files={};references={};controls={};layout={'fits':{},'predictions':{},'cite_predictions':{},'checkpoint_sidecars':{},'materialize':[]}
    def physical(p):
        p=Path(p).resolve()
        M.need(p.is_relative_to(root),'Source alias resolves outside preserved study')
        M.inside(root,p.relative_to(root).as_posix())
        return p
    def add(path,mapping=files):
        p=physical(path);M.need(p.is_file(),'Expected source file')
        relative=p.relative_to(root).as_posix();mapping[relative]=M.sha(p);return relative
    def directory(path):
        p=physical(path);M.need(p.is_dir(),'Missing source directory')
        for child in p.rglob('*'):
            if child.is_file():add(child)
        return p.relative_to(root).as_posix()
    for role in ('data','cite'):
        layout[role]=directory(base/manifest[role])
    for arm in ('A','B'):
        sources=[base/p for p in manifest['arms'][arm]]
        for method in M.METHODS:
            models=[physical(p/method/'model.pkl') for p in sources if (p/method/'model.pkl').is_file()]
            M.need(len(set(models))==1,f'Exactly one recorded {arm}:{method} model required')
            fit=models[0].parent;layout['fits'][arm+':'+method]=directory(fit)
            predictions=[physical(f) for p in sources for f in (p/method).glob('predictions_*.parquet')]
            # Separate paired RNA queries from CITE predictions, which live in distinct source dirs.
            if arm=='A':predictions=[p for p in predictions if 'totalvi_' not in p.name]
            parents={p.parent for p in predictions}
            M.need(len(parents)==1,f'Prediction layout ambiguous: {arm}:{method}')
            pred=parents.pop();layout['predictions'][arm+':'+method]=directory(pred)
            if arm=='A':
                cite=[physical(f) for p in sources for f in (p/method).glob('predictions_totalvi_*.parquet')]
                M.need(len({p.parent for p in cite})==1,'CITE prediction group missing/ambiguous')
                layout['cite_predictions'][method]=directory(cite[0].parent)
        fit=root/layout['fits'][arm+':M6']/'scanvi'
        hashes={p.relative_to(fit).as_posix():M.sha(p) for p in fit.rglob('*') if p.is_file()}
        M.need(hashes,'No recorded M6 checkpoint files')
        sidecar=output.parent/(output.stem+'-'+arm+'-M6-checkpoint-sha256.json')
        M.need(not sidecar.exists(),'Preserve existing derived sidecar')
        M.dump(sidecar,hashes);layout['checkpoint_sidecars'][arm]=add(sidecar)
    score=physical(base/manifest['score']['primary'])
    names=('summary_test.csv','thresholds_validation.csv','cell_counts.csv','bootstrap_ids.csv','bootstrap_weights.npy')
    layout['equality_references']={n:add(score/n,references) for n in names}
    layout['d03_features']=add(base/manifest['d03_features'],references)
    fresh_report=root/'.research/reproductions'/M.FRESH_PARENT/'checkout/runs/F-20261007T103704949889Z/compare/report.json'
    controls[add(comparison,controls)]=M.sha(comparison)
    add(parent_manifest,controls);add(fresh_report,references)
    # Any root-pinned acquisition inputs are ordinary original sources, not adopted model outputs.
    import acquire_inputs
    for item in acquire_inputs.ITEMS:
        p=root/item.dest
        if item.sha256:
            M.need(p.is_file() and M.sha(p)==item.sha256,f'Pinned acquisition input missing/changed: {item.id}')
            layout['materialize'].append(add(p))
    report=M.load(fresh_report)
    M.need(report['counts']['unsupported']==0 and all(x.get('method')=='M5' for x in report['failures']),
           'Failed fresh parent contains non-M5 failures; selective repair not justified')
    ap=M.inside(root,approval);M.need(ap.is_file(),'Committed explicit approval record missing')
    inventory={'schema_version':1,'repair_id':repair_id,'stage':stage,'parent_id':M.FRESH_PARENT,
      'parent_manifest_sha256':M.sha(parent_manifest),'parent_code_revision':parent['code_revision'],
      'parent_protocol_hash':parent['protocol_hash'],'parent_science_hash':parent['science_hash'],
      'target_protocol_hash':target_protocol_hash,'target_science_hash':target_science_hash,
      'approval':{'path':approval,'sha256':M.sha(ap)},'adopted_files':files,'source_controls':controls,
      'readonly_references':references,'layout':layout,
      'forbidden_adoption_prefixes':['.research/runs/'+M.ORIGINAL_RUN+'/output/recovery/attempts/score',
                                     '.research/runs/'+M.ORIGINAL_RUN+'/output/recovery/attempts/protein']}
    if stage=='reproduction':
        M.need(canonical_run_id,'Reproduction inventory requires current corrected canonical run ID')
        inventory['canonical_run_id']=canonical_run_id
        inventory['forbidden_adoption_prefixes'].append('.research/runs/'+canonical_run_id+'/output')
    M.verify_inventory(root,inventory);M.dump(output,inventory)
    return inventory

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--stage',choices=('canonical','reproduction'),required=True)
    p.add_argument('--approval',required=True);p.add_argument('--repair-id',required=True)
    p.add_argument('--target-protocol-hash',required=True);p.add_argument('--target-science-hash',required=True)
    p.add_argument('--canonical-run-id')
    a=p.parse_args()
    result=build(a.source_root,a.output,a.stage,a.approval,a.repair_id,a.target_protocol_hash,a.target_science_hash,a.canonical_run_id)
    print(json.dumps({'stage':a.stage,'selected_files':len(result['adopted_files']),'inventory_payload_sha256':M.inventory_payload_sha256(result),'status':'prepared; no experiments executed'}))

if __name__=='__main__':main()
