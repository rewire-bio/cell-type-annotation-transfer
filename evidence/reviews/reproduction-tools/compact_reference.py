#!/usr/bin/env python3
"""Engineering preparation and exact-byte reference restoration. No scientific computation.

The frozen reference contains file identity metadata only. It does not replace the
unchanged scientific comparator or demonstrate a public fresh-clone reproduction.
"""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

SCHEMA='celltransfer-compact-reference/1'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def relative(value):
    p=Path(value)
    if not value or p.is_absolute() or '..' in p.parts or str(p)=='.':raise ValueError('Unsafe relative slot')
    return p.as_posix()
def validate(record):
    if record.get('schema')!=SCHEMA or not record.get('canonical_manifest_sha256') or not record.get('canonical_comparison_manifest_sha256'):
        raise ValueError('Independently frozen canonical identity required')
    seen=set()
    for slot in record.get('slots',[]):
        name=relative(slot['target'])
        if name in seen:raise ValueError('Duplicate reference slot')
        seen.add(name)
        if (len(slot.get('sha256',''))!=64 or any(c not in '0123456789abcdef' for c in slot['sha256'])
            or type(slot.get('size_bytes')) is not int or slot['size_bytes']<0):raise ValueError('Invalid frozen byte identity')
    if not seen:raise ValueError('Empty reference metadata')
    return record

def prepare_record(audit,study,canonical_manifest,canonical_comparison):
    """Inspect already frozen C files, never derive expected hashes from fresh F."""
    study=Path(study).resolve();cm=Path(canonical_manifest).resolve();cp=Path(canonical_comparison).resolve()
    if sha(cm)!=audit['canonical_run_manifest_sha256'] or sha(cp)!=audit['canonical_comparison_manifest_sha256']:
        raise ValueError('Frozen C manifest binding differs')
    slots=[]
    for old in audit['slots']:
        path=(study/relative(old['canonical_source'])).resolve()
        if not path.is_relative_to(study) or not path.is_file():raise ValueError('Canonical source escapes or missing')
        if sha(path)!=old['original_sha256'] or path.stat().st_size!=old['original_bytes']:
            raise ValueError('Frozen canonical original bytes differ')
        slots.append({'target':relative(old['target']),'role':old['role'],'sha256':old['original_sha256'],'size_bytes':old['original_bytes']})
    # Same established metadata-only CSV extraction; this is a virtual byte
    # digest from the frozen original query obs, not a candidate-derived target.
    sample=audit.get('sampled_ids_virtual_csv',{})
    if sample:
        originals=[x for x in sample.get('records',[]) if x.get('side')=='canonical']
        if len(originals)!=1:raise ValueError('Frozen original sampled-ID digest required')
        row=originals[0];slots.append({'target':'data/sampled_ids.csv','role':'sampled-Census-ID-metadata','sha256':row['sha256'],'size_bytes':row['bytes']})
    return validate({'schema':SCHEMA,'canonical_id':audit['canonical_id'],'canonical_manifest_sha256':sha(cm),
        'canonical_comparison_manifest_sha256':sha(cp),'slots':slots,
        'scope':'Byte identity metadata for withheld reference files. No arrays, models or source paths.',
        'public_fresh_clone_status':'not yet executed or validated',
        'mismatch_policy':'Reference unavailable; do not infer a scientific tolerance verdict or reproduction success.'})

def candidate_map(record,fresh_manifest,workspace,sampled_ids=None):
    """Locate independently generated candidates from the actual fresh manifest.

Only relocation happens here; no inference, scoring, conversions or acquisitions.
Sampled-ID CSV must already have been prepared with the documented obs-only recipe.
"""
    validate(record);workspace=Path(workspace).resolve();manifest_path=Path(fresh_manifest).resolve();manifest=json.loads(manifest_path.read_text())
    if manifest.get('mode')!='F' or manifest.get('fresh_execution') is not True:raise ValueError('Actual fresh F manifest required')
    def source(value):
        p=(manifest_path.parent/value).resolve()
        if not p.is_relative_to(workspace):raise ValueError('Fresh source escapes independent workspace')
        return p
    mapping={}
    for slot in record['slots']:
        parts=Path(slot['target']).parts
        if parts[0]=='arms':
            candidates=[source(p)/parts[2]/parts[3] for p in manifest['arms'][parts[1]]]
        elif parts[0]=='score':candidates=[source(manifest['score'][parts[1]])/parts[2]]
        elif slot['target']=='bootstrap_weights.npy':candidates=[source(manifest['bootstrap_weights'])]
        elif slot['target']=='data/sampled_ids.csv':candidates=[Path(sampled_ids).resolve()] if sampled_ids else ([source(manifest['sampled_ids'])] if manifest.get('sampled_ids') else [])
        else:candidates=[source(manifest[parts[0]])/Path(*parts[1:])]
        present={p.resolve() for p in candidates if p.is_file()}
        if not present:raise ValueError('Missing fresh reference candidate: '+slot['target'])
        if len({(p.stat().st_size,sha(p)) for p in present})!=1:raise ValueError('Conflicting fresh candidate aliases')
        mapping[slot['target']]=str(sorted(present)[0])
    return mapping

def restore(record,mapping,fresh_workspace,destination,receipt_path):
    """All slots must match frozen C hashes before any reference copies appear.

On missing/mismatch write an explicit unsupported receipt; no comparator is run.
The reader's fresh outputs remain untouched. Destination files are ordinary copies.
"""
    validate(record);fresh=Path(fresh_workspace).resolve();dest=Path(destination).resolve();receipt_path=Path(receipt_path)
    if dest==fresh or dest.is_relative_to(fresh) or fresh.is_relative_to(dest):raise ValueError('Separate reference and fresh trees required')
    if dest.exists():raise ValueError('Reference destination must be new')
    expected={s['target'] for s in record['slots']}
    if set(mapping)!=expected:raise ValueError('Exact candidate slot coverage required')
    receipt={'schema':'celltransfer-reference-restoration/1','status':'unsupported','scientific_verdict':None,
        'reference_record_sha256':hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest(),'slots':[]}
    sources={}
    for slot in record['slots']:
        path=Path(mapping[slot['target']]).resolve()
        valid=path.is_relative_to(fresh) and path.is_file()
        size=path.stat().st_size if valid else None;observed=sha(path) if valid and size==slot['size_bytes'] else None
        matched=valid and observed==slot['sha256'] and size==slot['size_bytes']
        receipt['slots'].append({'target':slot['target'],'expected_sha256':slot['sha256'],'observed_sha256':observed,'expected_size_bytes':slot['size_bytes'],'observed_size_bytes':size,'matched':matched})
        if matched:sources[slot['target']]=path
    if len(sources)!=len(expected):
        receipt['reason']='At least one candidate lacks exact independently frozen original bytes. Strict reference remains unavailable.'
        receipt_path.parent.mkdir(parents=True,exist_ok=True);write(receipt_path,receipt);return receipt
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reference-stage-',dir=dest.parent) as tmp:
        stage=Path(tmp)
        for slot in record['slots']:
            target=stage/relative(slot['target']);target.parent.mkdir(parents=True,exist_ok=True);source=sources[slot['target']]
            shutil.copyfile(source,target)
            if sha(source)!=slot['sha256'] or sha(target)!=slot['sha256'] or target.stat().st_size!=slot['size_bytes']:
                raise ValueError('Source changed during exact-byte restoration')
            if target.is_symlink() or source.stat().st_ino==target.stat().st_ino:raise ValueError('Reference copy aliases fresh source')
        stage.rename(dest)
    receipt['status']='exact-reference-restored';receipt['reason']='Byte identity verified against frozen C metadata; scientific comparison is still required.'
    receipt_path.parent.mkdir(parents=True,exist_ok=True);write(receipt_path,receipt);return receipt

def package_metadata(record,metadata_directory,reviewed_bindings,destination,archive):
    """Create a metadata-only artifact from explicitly reviewed bytes.

This function does not package arrays, models or reader-generated candidates.
Approval/content review and archive attachment remain separate release gates.
"""
    import gzip
    import tarfile
    validate(record);metadata=Path(metadata_directory).resolve();destination=Path(destination).resolve();archive=Path(archive)
    files={p.relative_to(metadata).as_posix():p for p in metadata.rglob('*') if p.is_file()}
    if set(files)!=set(reviewed_bindings):raise ValueError('Exact reviewed metadata coverage required')
    if destination.exists() or archive.exists():raise ValueError('New metadata package outputs required')
    slotnames={s['target'] for s in record['slots']}
    for rel,p in files.items():
        relative(rel)
        if p.is_symlink() or not p.resolve().is_relative_to(metadata) or rel in slotnames or (p.suffix not in ('.json','.md','.tex','.sha256') and rel!='protein/protein_agreement.csv'):
            raise ValueError('No arrays, model objects or unreviewed formats in metadata package')
        if sha(p)!=reviewed_bindings[rel]:raise ValueError('Reviewed metadata bytes differ')
        content=p.read_text()
        if any(marker in content for marker in ('/Users/','/Volumes/','/private/var/','file://')):
            raise ValueError('Metadata contains private absolute source locations')
    if 'compact-reference.json' in files or 'checksums.json' in files:raise ValueError('Reserved package metadata filename')
    destination.mkdir(parents=True)
    for rel,p in files.items():
        target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        if sha(target)!=reviewed_bindings[rel]:raise ValueError('Reviewed metadata changed during package copy')
    write(destination/'compact-reference.json',record)
    checks={p.relative_to(destination).as_posix():sha(p) for p in destination.rglob('*') if p.is_file()};write(destination/'checksums.json',checks)
    archive.parent.mkdir(parents=True,exist_ok=True)
    with archive.open('xb') as output,gzip.GzipFile(filename='',mode='wb',fileobj=output,mtime=0) as gz,tarfile.open(fileobj=gz,mode='w') as tar:
        for p in sorted(destination.rglob('*')):
            if p.is_file():
                info=tar.gettarinfo(str(p),arcname='baseline/'+p.relative_to(destination).as_posix());info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
                with p.open('rb') as f:tar.addfile(info,f)
    return {'status':'prepared-metadata-only','archive_sha256':sha(archive),'withheld_reference_slots':len(record['slots']),
        'public_fresh_clone_status':'not yet executed or validated','scientific_verdict':None}
