"""Verify preserved historical files against their migration-time SHA256 hashes."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / 'evidence/migration-manifest.json').read_text())
    missing, changed = [], []
    for item in manifest['files']:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'Invalid manifest path: {relative}')
        path = root / manifest['destination'] / relative
        if not path.is_file():
            missing.append(str(relative))
        elif path.stat().st_size != item['bytes'] or hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() != item['sha256']:
            changed.append(str(relative))
    print(json.dumps({'checked': len(manifest['files']), 'missing': missing, 'changed': changed}, indent=2))
    return 1 if missing or changed else 0


if __name__ == '__main__':
    raise SystemExit(main())
