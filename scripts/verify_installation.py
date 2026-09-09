"""Verify clean Windows setup and repair without measuring WiFi."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(argv, cwd):
    return subprocess.run([str(v) for v in argv],cwd=cwd,capture_output=True,timeout=240)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repair-python',default=sys.executable)
    args=parser.parse_args()
    shell=shutil.which('powershell.exe')
    if not shell:
        raise SystemExit('Esta comprobacion requiere Windows PowerShell.')
    ident=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
    parent=ROOT/'tmp'/('installation-'+ident)
    reports=[]
    output=ROOT/'evidence/revision';output.mkdir(parents=True,exist_ok=True)
    for kind in ('clean','repair'):
        dest=parent/kind;dest.mkdir(parents=True,exist_ok=False)
        for name in ('swarm_signal','vendor'):
            shutil.copytree(ROOT/name,dest/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ('Iniciar.ps1','requirements.txt','project.json'):
            shutil.copyfile(ROOT/name,dest/name)
        if kind=='repair':
            created=run([args.repair_python,'-m','venv',dest/'.venv'],dest)
            if created.returncode:
                raise RuntimeError(created.stderr.decode('utf-8','replace'))
            incomplete=run([dest/'.venv/Scripts/python.exe','-c','import numpy'],dest)
            assert incomplete.returncode != 0, 'Repair fixture must begin without NumPy.'
        checked=run([shell,'-NoProfile','-ExecutionPolicy','Bypass','-File',dest/'Iniciar.ps1','-SoloVerificar'],dest)
        transcript=(checked.stdout+checked.stderr).decode('utf-8','replace').replace(str(ROOT),'<project>')
        log='installation_'+kind+'.log'
        (output/log).write_text(transcript,encoding='utf-8')
        if checked.returncode:
            raise RuntimeError(f'{kind} failed: {transcript[-1500:]}')
        info=run([dest/'.venv/Scripts/python.exe','-c',
                  "import json,sys,importlib.metadata as m;print(json.dumps({'python':sys.version.split()[0],'numpy':m.version('numpy'),'scipy':m.version('scipy')}))"],dest)
        if info.returncode:
            raise RuntimeError(info.stderr.decode('utf-8','replace'))
        reports.append({'case':kind,'exit_code':checked.returncode,'status':'PASS',
                        'environment':json.loads(info.stdout),'log':log,
                        'log_sha256':hashlib.sha256((output/log).read_bytes()).hexdigest()})
    report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS',
            'checks':reports,'scope':'Creates environments and imports the application; no WiFi capture.',
            'bootstrap_sha256':hashlib.sha256((ROOT/'Iniciar.ps1').read_bytes()).hexdigest(),
            'requirements_sha256':hashlib.sha256((ROOT/'requirements.txt').read_bytes()).hexdigest()}
    (output/'installation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
