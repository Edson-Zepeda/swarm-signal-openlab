"""Export the explicitly reviewed recording and evidence-derived delivery state."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime, timezone
import csv
import json
import shutil
from swarm_signal import ROOT
from swarm_signal.analysis import analyze, from_rows
from swarm_signal.evidence import reference_recording, build_evidence
from swarm_signal.experiment import build_comparison
from swarm_signal.server import write_json


def main():
    data, reference, config = reference_recording(ROOT)
    data.update(mode='replay', status='ready')
    data['session']['source_sha256'] = reference['sha256']
    samples = from_rows(data['samples'])
    data['frames'] = [{'index': i, **analyze(samples[:i+1])} for i in range(len(samples))]
    data.update(analyze(samples))
    data['provenance'] = {'kind':reference['kind'], 'ground_truth':data['session']['ground_truth'],
                          'source_file':reference['source'], 'source_sha256':reference['sha256'],
                          'generated_at':datetime.now(timezone.utc).isoformat(),
                          'classifier':'Original RuView thresholds with explicit application quality gates',
                          'network_identifiers':'not included', 'release':config['version']}
    web = ROOT/'web'
    (web/'data').mkdir(parents=True,exist_ok=True)
    (web/'code').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'scripts/check_backend.py', web/'code/check_backend.py')
    evidence = build_evidence(ROOT)
    evidence['stages'][5]['artifact_links'] = [{'label':'Código de integración','url':'code/check_backend.py'}]
    data['evidence'] = evidence
    write_json(web/'data/evidence.json', evidence)
    write_json(web/'data/session.json', data)
    write_json(web/'data/comparison.json', build_comparison())
    with (web/'data/session.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=['timestamp','rssi_dbm','quality','phase'])
        writer.writeheader(); writer.writerows(data['samples'])
    for directory in ('tutorial','sessions','upstream','ui','revision'):
        source=ROOT/'evidence'/directory
        if source.exists():
            shutil.copytree(source,web/'evidence'/directory,dirs_exist_ok=True)
    for document in ('SwarmSignal_Informe.pdf','SwarmSignal_Propuesta.pdf','SwarmSignal_Auditoria.pdf'):
        if (ROOT/'docs'/document).is_file():
            (web/'docs').mkdir(exist_ok=True)
            shutil.copyfile(ROOT/'docs'/document,web/'docs'/document)
    print(json.dumps({'source':reference['source'],'samples':len(samples),'frames':len(data['frames']),
                      'completed':evidence['completed'],'total':evidence['total']},indent=2))


if __name__ == '__main__':
    main()
