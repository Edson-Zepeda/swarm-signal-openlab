"""Replay the pinned unit suite and CSI proof; live Wi-Fi is opt-in.

Usage: python reproduce.py --repo PATH_TO_RUVIEW [--python VENV_PYTHON] [--live]
The root ./verify is documented separately because it contacts registries and Docker.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PIN = 'd613a576ea848f96a9b15bac4e7f60b6be7c08e7'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--live', action='store_true', help='Run ~40 seconds of real netsh Wi-Fi reads.')
    parser.add_argument('--output', type=Path, default=Path('upstream-replay'))
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = args.output.resolve()
    head = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise SystemExit(f'Expected upstream {PIN}; observed {head}. Stop and review version drift.')
    required = ['archive/v1/tests/unit/test_sensing.py', 'archive/v1/tests/integration/test_windows_live_sensing.py',
                'archive/v1/data/proof/verify.py', 'archive/v1/data/proof/sample_csi_data.json',
                'archive/v1/data/proof/expected_features.sha256']
    for path in required:
        if not (repo / path).is_file():
            raise SystemExit(f'Missing {path}; populate archive/v1/src, archive/v1/tests, archive/v1/data/proof.')
    dirty = subprocess.check_output(['git', '-C', str(repo), 'diff', '--name-only', 'HEAD', '--', 'archive/v1'], text=True).strip()
    if dirty:
        raise SystemExit(f'Upstream archive/v1 has modifications; preserve it and use a clean pinned clone:\n{dirty}')
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PYTHONPATH'] = str(repo / 'archive')
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env.pop('PROOF_HASH_DECIMALS', None)
    commands = [
        ('unit', [args.python, '-m', 'pytest', 'archive/v1/tests/unit/test_sensing.py', '-v', '-o', 'addopts=', '--junitxml=' + str(out / 'unit.xml')]),
        ('csi-proof', [args.python, 'archive/v1/data/proof/verify.py', '--verbose', '--audit']),
    ]
    if args.live:
        original = (repo / 'archive/v1/tests/integration/test_windows_live_sensing.py').read_text(encoding='utf-8')
        old = '        return "connected" in r.stdout.lower() and "disconnected" not in r.stdout.lower().split("state")[1][:30]'
        new = '''        for line in r.stdout.lower().splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() in {"state", "estado"}:
                if value.strip() in {"connected", "conectado"}:
                    return True
        return False'''
        if original.count(old) != 1:
            raise SystemExit('The precheck changed; stop and review the adaptation.')
        adapted = original.replace(old, new)
        assertions = lambda text: [ast.dump(node) for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Assert)]
        if assertions(original) != assertions(adapted):
            raise SystemExit('Test assertions changed; refusing to run.')
        copy = out / 'test_windows_live_sensing_es.py'
        copy.write_text(adapted, encoding='utf-8')
        commands.extend([
            ('live-original', [args.python, '-m', 'pytest', 'archive/v1/tests/integration/test_windows_live_sensing.py', '-v', '-o', 'addopts=', '-s']),
            ('live-es', [args.python, '-m', 'pytest', str(copy), '-v', '-o', 'addopts=', '-s', '--junitxml=' + str(out / 'live.xml')]),
        ])
    records = []
    for label, command in commands:
        started = datetime.now(timezone.utc).isoformat()
        log = out / (label + '.log')
        with log.open('wb') as stream:
            stream.write((json.dumps({'started_at_utc': started, 'argv': command, 'cwd': str(repo), 'commit': head})+'\n').encode())
            stream.flush()
            result = subprocess.run(command, cwd=repo, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record = {'label': label, 'exit_code': result.returncode, 'log': log.name,
                  'started_at_utc': started, 'ended_at_utc': datetime.now(timezone.utc).isoformat(),
                  'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
        records.append(record)
        print(json.dumps(record))
    (out / 'replay.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    raise SystemExit(0 if all(row['exit_code'] == 0 for row in records) else 1)


if __name__ == '__main__':
    main()
