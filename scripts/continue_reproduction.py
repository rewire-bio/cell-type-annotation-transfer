"""Audited continuation of completed steps from one interrupted clean lineage."""
from __future__ import annotations
import hashlib
import json
import math
import os
import shutil
from pathlib import Path, PurePosixPath
import reproduce as base


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_path(root, relative):
    p = PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise base.Stop(f'Unsafe inventory path: {relative}')
    result = root.joinpath(*p.parts)
    # The final object can be an explicitly inventoried link, but ancestors cannot.
    for ancestor in result.parents:
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise base.Stop(f'Inventory path traverses a link: {relative}')
    return result


def validate_inventory(root, inventory, selected_only=False):
    roots = inventory['copy_roots']
    def selected(rel):
        return any(rel == r or rel.startswith(r.rstrip('/') + '/') for r in roots)
    for rel, expected in inventory['files'].items():
        if selected_only and not selected(rel):
            continue
        p = safe_path(root, rel)
        if p.is_symlink() or not p.is_file() or digest(p) != expected:
            raise base.Stop(f'Inventory file differs: {rel}')
    for rel, expected in inventory.get('symlinks', {}).items():
        if selected_only and not selected(rel):
            continue
        p = safe_path(root, rel)
        if not p.is_symlink() or os.readlink(p) != expected:
            raise base.Stop(f'Inventory link differs: {rel}')
    # Reject unlisted objects within copied trees, including hidden failed outputs.
    for rel in roots:
        start = safe_path(root, rel)
        paths = [start]
        if start.is_dir() and not start.is_symlink():
            paths += list(start.rglob('*'))
        for p in paths:
            key = p.relative_to(root).as_posix()
            if p.is_symlink():
                if key not in inventory.get('symlinks', {}):
                    raise base.Stop(f'Unlisted inventory link: {key}')
            elif p.is_file():
                if key not in inventory['files']:
                    raise base.Stop(f'Unlisted inventory file: {key}')
            elif not p.is_dir():
                raise base.Stop(f'Missing or unsupported inventory object: {key}')


class ContinuedRepro(base.Repro):
    def __init__(self, repo, cfg, runner=None, now=base.time.time):
        started = now()
        super().__init__(repo, cfg, runner=runner, now=now)
        env = os.environ
        self.parent = Path(env['RESEARCH_REPRODUCTION_PARENT']).resolve()
        manifest_path = Path(env['RESEARCH_REPRODUCTION_PARENT_MANIFEST'])
        inv_path = Path(env['RESEARCH_REPRODUCTION_PARENT_INVENTORY'])
        self.inventory = json.loads(inv_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        approval = json.loads((repo / 'evidence/reviews/disk-continuation-approval.json').read_text())
        plan = repo / 'evidence/reviews/disk-continuation-plan.md'
        if (self.inventory.get('schema_version') != 1 or
            approval.get('parent_id') not in ({manifest.get('id')} | {x.get('parent_id') for x in manifest.get('lineage', [])}) or
            self.inventory.get('parent_id') != manifest.get('id') or
            approval.get('protocol_hash') != manifest.get('protocol_hash') or
            not approval.get('approved_by') or not approval.get('user_reply') or
            approval.get('plan_sha256') != digest(plan) or
            approval.get('step') != 'B_M6_fit' or
            approval.get('additional_guarded_attempts') != 1 or
            approval.get('max_step_seconds') != 4800 or
            float(self.step_ceil['fit']) != 4800 or
            manifest.get('status') != 'failed'):
            raise base.Stop('Continuation approval/parent identity mismatch')
        receipt_path = safe_path(self.parent, self.inventory['receipt'])
        if digest(receipt_path) != self.inventory['receipt_sha256']:
            raise base.Stop('Parent receipt differs from inventory')
        self.old = json.loads(receipt_path.read_text())
        if self.old.get('mode') != 'F' or self.old.get('fresh_execution') is not True or self.old['config'] != cfg:
            raise base.Stop('Parent is not the same clean Mode F configuration')
        steps = self.old['steps']
        replay = [s for s in steps if s['name'] != 'repair_acquire']
        if any(s['name'] == 'repair_acquire' and (s['status'] != 'ok' or s.get('executed') is not True) for s in steps):
            raise base.Stop('Invalid prior repair acquisition record')
        failed = [s for s in steps if s['status'] != 'ok']
        self.retry_step = 'B_M6_fit'
        disk_parent = (len(failed) == 2 and all(s['name'] == 'B_M6_fit' for s in failed)
                       and [s['attempt'] for s in failed] == [1, 2]
                       and all(s['status'] in (base.RG.INFRA_STATUSES | {'disk-start'}) for s in failed)
                       and steps[-2:] == failed)
        cite_parent = (len(failed) == 1 and failed[0]['name'] == 'cite_build'
                       and failed[0]['attempt'] == 1 and failed[0]['kind'] == 'cite_build'
                       and replay[-1:] == failed and self.old.get('continuation')
                       and manifest.get('parent_reproduction_id') == self.old['continuation']['parent_id'])
        if not disk_parent and not cite_parent:
            raise base.Stop('Parent does not have only the approved exhausted B_M6 fit or first cite attempt')
        if cite_parent:
            self.retry_step = 'cite_build'
            expected = ['env', 'acquire', 'data'] + [f'{a}_{m}_{stage}' for a in ('A', 'B')
                        for m in base.METHODS for stage in ('fit', 'predict')]
            if [x['name'] for x in replay[:-1]] != expected or any(x['status'] != 'ok' for x in replay[:-1]):
                raise base.Stop('Cite continuation requires all 27 completed fresh steps')
        self.completed = [s for s in replay if s['status'] == 'ok']
        if self.inventory['completed_steps'] != [s['name'] for s in steps if s['status'] == 'ok']:
            raise base.Stop('Inventory completed-step prefix differs')
        self.extra_cite_approval = None
        self.retry_total_attempt = 3 if disk_parent else 2
        if cite_parent and failed[0].get('total_attempt', 1) == 2:
            # This candidate path is deliberately unavailable without a new explicit approval.
            extra_path = repo / 'evidence/reviews/cite-preflight-retry-approval.json'
            extra_plan = repo / 'evidence/reviews/cite-preflight-retry-plan.md'
            if not extra_path.is_file() or not extra_plan.is_file():
                raise base.Stop('Additional CITE preflight attempt requires explicit approval')
            extra = json.loads(extra_path.read_text())
            if (manifest['id'] != '108dfa6e36394279931f372749ad6f6c'
                or extra.get('parent_id') != manifest['id']
                or extra.get('protocol_hash') != manifest['protocol_hash']
                or extra.get('step') != 'cite_build' or extra.get('additional_guarded_attempts') != 1
                or extra.get('total_attempt') != 3 or not extra.get('approved_by')
                or not extra.get('user_reply') or extra.get('plan_sha256') != digest(extra_plan)):
                raise base.Stop('Additional CITE preflight approval differs from concrete plan/parent')
            self.retry_total_attempt = 3
            self.extra_cite_approval = {'path': str(extra_path.relative_to(repo)),
                                        'sha256': digest(extra_path), 'record': extra}
        elif cite_parent and failed[0].get('total_attempt', 1) != 1:
            raise base.Stop('CITE attempt allowance exhausted for this parent')
        acq = next(s for s in self.completed if s['name'] == 'acquire')
        suffix = '/.venv/bin/python'
        if not acq['command'][0].endswith(suffix):
            raise base.Stop('Cannot infer original logical checkout path')
        self.logical_parent = acq['command'][0][:-len(suffix)]
        self.old_control = str(Path(self.inventory['receipt']).parent)
        self.cursor = 0
        prior = float(env['RESEARCH_REPRODUCTION_PRIOR_SECONDS']) + float(self.old.get('prior_seconds_reserved', 0))
        used = max(prior, float(self.old['h_seconds_used']), float(self.old['f_seconds_used']))
        if not math.isfinite(used) or used < 0 or used >= min(self.ceiling_h, self.ceiling_f):
            raise base.Stop('Invalid/exhausted continuation runtime')
        self.t0 = started - used
        self.f_used = used
        self.pool_used = dict(self.old.get('continuation', {}).get('carried_pool_usage', {}))
        ancestry = [] if self.pool_used else self.old.get('continuation', {}).get('parent_steps', [])
        for step in ancestry + steps:
            if step.get('pool') and step.get('executed', True):
                self.pool_used[step['pool']] = self.pool_used.get(step['pool'], 0.0) + float(step['wall_seconds'])
        # Validate before copying, then validate the independent destination copy.
        validate_inventory(self.parent, self.inventory)
        failed_roots = [str(Path(s['out_dir']).relative_to(self.logical_parent)) for s in failed]
        for rel in self.inventory['copy_roots']:
            safe_path(self.parent, rel)
            if any(rel == bad or bad.startswith(rel.rstrip('/') + '/') or rel.startswith(bad + '/') for bad in failed_roots):
                raise base.Stop('Partial failed fit selected for copying')
            src, dst = safe_path(self.parent, rel), safe_path(repo, rel)
            if dst.exists() or dst.is_symlink():
                raise base.Stop(f'Continuation copy destination already exists: {rel}')
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir() and not src.is_symlink():
                shutil.copytree(src, dst, symlinks=True)
            elif src.is_symlink():
                dst.symlink_to(os.readlink(src))
            else:
                shutil.copy2(src, dst)
        validate_inventory(repo, self.inventory, selected_only=True)
        overhead = now() - started
        self.f_used += overhead
        self.receipt.update(driver='scripts/continue_reproduction.py',
                            fresh_execution=True, execution_scope='continued-clean-reproduction-lineage',
                            continuation={'parent_id': manifest['id'], 'parent_source': manifest['code_revision'],
                                          'inventory_sha256': digest(inv_path), 'receipt_sha256': digest(receipt_path),
                                          'prior_seconds_charged': used, 'copy_validation_seconds': overhead,
                                          'parent_steps': steps, 'carried_pool_usage': dict(self.pool_used),
                                          'extra_cite_approval': self.extra_cite_approval,
                                          'retry_step': self.retry_step, 'retry_total_attempt': self.retry_total_attempt, 'copy_roots': self.inventory['copy_roots']})
        self.retry_used = False

    def save(self):
        # Charge continuation bookkeeping and hash checking as well as guarded steps.
        self.f_used = max(self.f_used, self.now() - self.t0 - self.paper_used)
        super().save()

    def normalized(self, argv):
        result = []
        for value in argv:
            if value == self.logical_parent or value.startswith(self.logical_parent + '/'):
                value = str(self.repo) + value[len(self.logical_parent):]
            # Both checkpoint controls are reconstructed, including inherited old-run paths.
            p = Path(value)
            if p.name in ('A_M6_checkpoint_sha256.json', 'B_M6_checkpoint_sha256.json'):
                if not p.is_relative_to(self.repo):
                    raise base.Stop('Checkpoint argument outside normalized checkout')
                value = str(self.run_dir / p.name)
            result.append(value)
        return result

    def preflight(self, baseline):
        super().preflight(baseline)
        if self.retry_step == 'cite_build':
            self.repair_acquisition()

    def repair_acquisition(self):
        """Restore only omitted pinned acquisition inputs, under existing acquisition budget."""
        import acquire_inputs as acquisition
        items = [acquisition.ITEMS_BY_ID[k] for k in ('sctab-hparams', 'sctab-var')]
        if self.retry_total_attempt == 3:
            for item in items:
                copied = any(item.dest == root or item.dest.startswith(root.rstrip('/') + '/')
                             for root in self.inventory['copy_roots'])
                if not copied or self.inventory['files'].get(item.dest) != item.sha256:
                    raise base.Stop('Third CITE attempt requires hash-bound copied pinned inputs')
        if all((self.repo / item.dest).is_file() and not (self.repo / item.dest).is_symlink()
               and digest(self.repo / item.dest) == item.sha256 for item in items):
            self.receipt['continuation']['pinned_inputs_verified'] = {item.dest: item.sha256 for item in items}
            self.save()
            return
        if self.retry_total_attempt == 3:
            raise base.Stop('Third CITE attempt requires all pinned acquisition inputs in copied inventory')
        repair = self.run_dir / 'repair_acquisition'
        repair.mkdir(parents=True, exist_ok=True)
        old_manifest = self.repo / 'runs/data/retrieval-manifest.json'
        before = old_manifest.read_bytes() if old_manifest.is_file() else None
        if before is not None:
            (repair / 'original-retrieval-manifest.json').write_bytes(before)
        argv = [self.python, str(self.repo / 'scripts/acquire_inputs.py'), 'acquire', '--root', str(self.repo),
                '--repo', str(self.repo), '--only', 'sctab-hparams', 'sctab-var', '--attempts', '1']
        attempts = self.max_attempts
        self.max_attempts = 1
        first = len(self.receipt['steps'])
        try:
            super().step('acquire', 'acquire', lambda _: argv, out=False)
            outputs = {}
            for item in items:
                p = safe_path(self.repo, item.dest)
                if p.is_symlink() or not p.is_file() or digest(p) != item.sha256:
                    raise base.Stop(f'Repaired pinned input differs: {item.id}')
                outputs[item.dest] = digest(p)
            self.receipt['continuation']['repair_acquisition'] = {
                'executed': True, 'command': argv, 'outputs_sha256': outputs,
                'provenance': 'restored-pinned-third-party-inputs-in-new-checkout'}
        finally:
            self.max_attempts = attempts
            for rec in self.receipt['steps'][first:]:
                rec.update(name='repair_acquire', executed=True, provenance='repair-pinned-input-acquisition')
            if old_manifest.is_file():
                (repair / 'repair-retrieval-manifest.json').write_bytes(old_manifest.read_bytes())
            if before is not None:
                old_manifest.write_bytes(before)
            elif old_manifest.is_file():
                old_manifest.unlink()
            self.save()

    def step(self, name, kind, argv_fn, mode_f=True, out=True):
        self.f_used = max(self.f_used, self.now() - self.t0 - self.paper_used)
        if self.cursor < len(self.completed):
            old = self.completed[self.cursor]
            if old['name'] != name or old['kind'] != kind:
                raise base.Stop(f'Completed prefix mismatch at {name}')
            od = None
            if old.get('out_dir'):
                rel = Path(old['out_dir']).relative_to(self.logical_parent).as_posix()
                od = safe_path(self.repo, rel)
                if not any(rel == r or rel.startswith(r.rstrip('/') + '/') for r in self.inventory['copy_roots']):
                    raise base.Stop(f'Completed output not copied: {name}')
            argv = argv_fn(od)
            if argv != self.normalized(old['command']):
                raise base.Stop(f'Reused command identity differs: {name}')
            if '--expected-hashes' in argv:
                hp = Path(argv[argv.index('--expected-hashes') + 1])
                old_arg = old['command'][old['command'].index('--expected-hashes') + 1]
                bound_rel = Path(old_arg).relative_to(self.logical_parent)
                bound = self.repo / bound_rel
                if not bound.is_file() or digest(hp) != digest(bound):
                    raise base.Stop('M6 checkpoint sidecar differs from hash-bound parent')
            self.receipt['steps'].append(dict(old, command=argv, out_dir=str(od) if od else None,
                    wall_seconds=0.0, prior_wall_seconds=old['wall_seconds'], executed=False,
                    provenance='reused-completed-fresh-step', source_command=old['command'],
                    source_step_id=f"{self.inventory['parent_id']}:{name}:{old['attempt']}"))
            self.cursor += 1
            self.save()
            return od
        if name == self.retry_step:
            if self.retry_used:
                raise base.Stop('Additional guarded continuation allowance exhausted')
            expected_kind = 'fit' if name == 'B_M6_fit' else 'cite_build'
            if kind != expected_kind or not mode_f or not out:
                raise base.Stop('Approved retry must be the normal guarded fit')
            self.retry_used = True
            # The builder checks disk space at OUT.parent before creating OUT itself.
            # Replayed earlier outputs live in old control directories, so create this infrastructure path.
            (self.run_dir / 'out').mkdir(parents=True, exist_ok=True)
            source = self.old['steps'][-1]
            def approved_argv(od):
                argv = argv_fn(od)
                expected = self.normalized(source['command'])
                old_out = str(self.repo / Path(source['out_dir']).relative_to(self.logical_parent))
                expected = [str(od) if value == old_out else value for value in expected]
                if argv != expected:
                    raise base.Stop('Retry command identity differs from parent failed step')
                return argv
            attempts = self.max_attempts
            self.max_attempts = 1
            try:
                return super().step(name, kind, approved_argv, mode_f, out)
            finally:
                self.max_attempts = attempts
                for rec in self.receipt['steps']:
                    if rec['name'] == name:
                        rec.update(total_attempt=self.retry_total_attempt, executed=True, continuation_attempt=1)
                self.save()
        if name.endswith('_fit'):
            raise base.Stop(f'Unapproved extra fit retry: {name}')
        return super().step(name, kind, argv_fn, mode_f, out)
