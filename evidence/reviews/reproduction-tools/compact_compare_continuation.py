#!/usr/bin/env python3
"""Bounded engineering wrapper: retain failed comparison, restore exact reference,
then execute only the existing comparator and paper asset/build scripts.

No fit, prediction, data acquisition, scoring, inference or tolerance changes.
Public fresh-clone validation remains pending until separately executed and checked.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

spec=importlib.util.spec_from_file_location('compact_reference',Path(__file__).with_name('compact_reference.py'))
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)

def continue_comparison(*,record,mapping,workspace,reference_destination,baseline_template,
    fresh_manifest,failed_receipt,continuation_dir,tolerances,script_bindings,metadata_bindings,package_controls=None,python=sys.executable,runner=subprocess.run):
    workspace=Path(workspace).resolve();continuation_dir=Path(continuation_dir).resolve();tolerances=Path(tolerances).resolve()
    reference_destination=Path(reference_destination).resolve();failed_receipt=Path(failed_receipt).resolve()
    if continuation_dir.exists():raise ValueError('Continuation directory must be new')
    old=json.loads(failed_receipt.read_text());comparison=old.get('comparison',{})
    if old.get('status')!='stopped' or comparison.get('returncode') not in (1,3):raise ValueError('Preserved actual failed comparison required')
    if not old.get('steps') or old['steps'][-1].get('name')!='compare' or old['steps'][-1].get('status')=='ok':
        raise ValueError('Initial execution must have stopped at failed comparison')
    for step in old['steps'][:-1]:
        if step.get('status')!='ok' or step.get('returncode')!=0:raise ValueError('Scientific generation must already have succeeded')
    # Require independently bound scripts and tolerance bytes, never arbitrary commands.
    required={'scripts/compare_runs.py','scripts/make_paper_assets.py','scripts/build_paper.py',str(Path(tolerances).relative_to(workspace))}
    if set(script_bindings)!=required:raise ValueError('Exact frozen operational script/tolerance bindings required')
    for rel,digest in script_bindings.items():
        p=(workspace/C.relative(rel)).resolve()
        if not p.is_relative_to(workspace) or C.sha(p)!=digest:raise ValueError('Frozen operational bytes differ')
    template=json.loads(Path(baseline_template).read_text());fresh_manifest=Path(fresh_manifest).resolve();fresh=json.loads(fresh_manifest.read_text())
    if template.get('mode')!='R' or fresh.get('mode')!='F' or fresh.get('fresh_execution') is not True:raise ValueError('Original R and actual fresh F required')
    metadata=Path(baseline_template).parent.resolve()
    package_controls=package_controls or {}
    if set(package_controls)-{'compact-reference.json','checksums.json'}:raise ValueError('Only two reserved package controls allowed')
    for rel,digest in package_controls.items():
        if C.sha(metadata/rel)!=digest:raise ValueError('Bound package control bytes differ')
    if 'compact-reference.json' in package_controls and json.loads((metadata/'compact-reference.json').read_text())!=record:
        raise ValueError('Packaged original reference record differs')
    metadata_files={p.relative_to(metadata).as_posix():p for p in metadata.rglob('*') if p.is_file() and p.relative_to(metadata).as_posix() not in package_controls}
    if set(metadata_files)!=set(metadata_bindings):raise ValueError('Exact reviewed metadata file coverage required')
    slots={s['target'] for s in record['slots']}
    for rel,p in metadata_files.items():
        if p.is_symlink() or not p.resolve().is_relative_to(metadata) or rel in slots or (p.suffix not in ('.json','.md','.tex','.sha256') and rel!='protein/protein_agreement.csv'):
            raise ValueError('Template directory must contain reviewed metadata only')
        if C.sha(p)!=metadata_bindings[rel]:raise ValueError('Reviewed metadata bytes differ')
    continuation_dir.mkdir(parents=True)
    original_bytes=failed_receipt.read_bytes();shutil.copyfile(failed_receipt,continuation_dir/'initial-failed-receipt.json')
    # Preserve existing report without regenerating or relabelling it.
    prior_report=Path(comparison.get('report',''))
    if not prior_report.is_absolute():prior_report=workspace/prior_report
    if prior_report.is_file():shutil.copyfile(prior_report,continuation_dir/'initial-failed-comparison.json')
    receipt={'schema':'celltransfer-compact-comparison-continuation/1','status':'pending',
        'initial_failed_receipt_sha256':C.sha(failed_receipt),'fresh_manifest_sha256':C.sha(fresh_manifest),
        'generation_repeated':False,'scientific_verdict':None,'steps':[]}
    def save():C.write(continuation_dir/'receipt.json',receipt)
    restored=C.restore(record,mapping,workspace,reference_destination,continuation_dir/'restoration-receipt.json')
    if restored['status']!='exact-reference-restored':receipt.update(status='unsupported',reason=restored['reason']);save();return receipt
    # Template must contain only portable local reference slots. Metadata already
    # retained by policy review is copied here; arrays/model objects never bundled.
    for key in ('data','cite','protein','sampled_ids','d03_features','bootstrap_weights'):
        if key in template:C.relative(template[key])
    for value in template.get('score',{}).values():C.relative(value)
    for value in template.get('protein_classes',{}).values():C.relative(value)
    for values in template.get('arms',{}).values():
        for value in values:C.relative(value)
    for rel,p in metadata_files.items():
        if C.sha(p)!=metadata_bindings[rel]:raise ValueError('Reviewed metadata changed during restoration')
        target=reference_destination/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        if C.sha(target)!=metadata_bindings[rel]:raise ValueError('Reviewed metadata copy differs')
    original=reference_destination/Path(baseline_template).name
    report=continuation_dir/'compare/report.json';report.parent.mkdir()
    py=str(python);score=(fresh_manifest.parent/fresh['score']['primary']).resolve();protein=(fresh_manifest.parent/fresh['protein']).resolve()
    commands=[('compare',[py,str(workspace/'scripts/compare_runs.py'),'--original',str(original),'--reproduction',str(fresh_manifest),'--tolerances',str(tolerances),'--out',str(report)]),
        ('paper_assets',[py,str(workspace/'scripts/make_paper_assets.py'),'--score',str(score),'--protein',str(protein),'--eligibility',str((fresh_manifest.parent/fresh['eligibility']).resolve()),'--comparison',str(report),'--output',str(workspace/'paper')]),
        ('paper_build',[py,str(workspace/'scripts/build_paper.py')])]
    for name,command in commands:
        before=time.monotonic();result=runner(command,cwd=workspace,capture_output=True,text=True)
        step={'name':name,'kind':'compare' if name=='compare' else 'paper','executed':True,'command':command,'returncode':result.returncode,'wall_seconds':time.monotonic()-before,'status':'ok' if result.returncode==0 else 'failed'}
        receipt['steps'].append(step);(continuation_dir/(name+'.stdout')).write_text(result.stdout or '');(continuation_dir/(name+'.stderr')).write_text(result.stderr or '')
        if failed_receipt.read_bytes()!=original_bytes:raise ValueError('Original failed receipt changed')
        if result.returncode!=0:receipt.update(status='failed',reason=name+' returned nonzero');save();return receipt
        if name=='compare':
            report_data=json.loads(report.read_text());counts=report_data.get('counts',{})
            if report_data.get('schema')!='celltransfer-compare-report/1' or counts.get('gated_breaches_or_structural')!=0 or counts.get('unsupported')!=0 or report_data.get('failures') or report_data.get('unsupported'):
                receipt.update(status='failed',reason='Actual comparator report did not pass');save();return receipt
        save()
    pdf=workspace/'paper/build/main.pdf'
    if not pdf.is_file():receipt.update(status='failed',reason='PDF missing');save();return receipt
    receipt.update(status='completed',scientific_verdict='Existing unchanged comparator passed',pdf_sha256=C.sha(pdf),comparison_sha256=C.sha(report));save();return receipt
