"""Static web export from real immutable recordings, with exact Python replay frames."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import datetime, timezone
import csv
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from swarm_signal import ROOT
from swarm_signal.analysis import analyze, from_rows
from swarm_signal.server import write_json


def main():
    sessions = sorted((ROOT / 'evidence' / 'sessions').glob('*.json'))
    if not sessions:
        raise SystemExit('No real recording exists. Capture before exporting.')
    chosen = max(sessions, key=lambda p: len(json.loads(p.read_text(encoding='utf-8'))['samples']))
    d = json.loads(chosen.read_text(encoding='utf-8'))
    d['mode'] = 'replay'
    d['status'] = 'ready'
    d['session']['source_sha256'] = hashlib.sha256(chosen.read_bytes()).hexdigest()
    frames = []
    samples = from_rows(d['samples'])
    for index in range(len(samples)):
        frames.append({'index': index, **analyze(samples[:index+1])})
    d['frames'] = frames
    d['provenance'] = {'kind': 'recorded_real_wifi', 'ground_truth': 'unconfirmed',
                       'source_file': 'evidence/sessions/' + chosen.name,
                       'generated_at': datetime.now(timezone.utc).isoformat(),
                       'classifier': 'RuView, thresholds .3 variance / .1 energy, quality gates applied',
                       'network_identifiers': 'not included'}
    xml = ROOT / 'evidence' / 'own_tests.xml'
    own = 0
    if xml.exists():
        root = ET.parse(xml).getroot()
        cases = root.findall('.//testcase')
        own = sum(1 for c in cases if c.find('failure') is None and c.find('error') is None and c.find('skipped') is None)
    stages = [
        {'id':'01', 'title':'Entorno reproducible', 'status':'complete', 'summary':'Python y RuView fijados por versión.', 'artifact_url':'evidence/tutorial/01_environment.json'},
        {'id':'02', 'title':'Conexión WiFi', 'status':'complete', 'summary':'Adaptador real conectado; identificadores omitidos.', 'artifact_url':'evidence/tutorial/02_netsh.txt'},
        {'id':'03', 'title':'Lectura individual', 'status':'complete', 'summary':'−60 dBm con WindowsWifiCollector.', 'artifact_url':'evidence/tutorial/03_single_reading.json'},
        {'id':'04', 'title':'Pipeline de 15 s', 'status':'complete', 'summary':'30 muestras · 1.99 Hz · salida active.', 'artifact_url':'evidence/tutorial/04_pipeline_15s.json'},
        {'id':'05', 'title':'Monitor y movimiento', 'status':'partial', 'summary':'Monitor con RSSI real. Cruce humano pendiente de confirmar.', 'artifact_url':'evidence/sessions/' + chosen.name},
        {'id':'06', 'title':'CommodityBackend', 'status':'complete' if (ROOT/'evidence/tutorial/06_commodity_backend.json').exists() else 'pending', 'summary':'Integración propia con el colector validado.', 'artifact_url':'evidence/tutorial/06_commodity_backend.json'},
        {'id':'07', 'title':'Pruebas', 'status':'complete', 'summary':f'45 unitarias + 5 de hardware + {own} propias.', 'artifact_url':'evidence/upstream/verification_summary.json'},
        {'id':'08', 'title':'Verificación determinística', 'status':'partial', 'summary':'CSI: hash exacto. ./verify ampliado: error HTTP 403 y 3 omisiones.', 'artifact_url':'evidence/upstream/verification_summary.json'},
    ]
    evidence = {'stages': stages, 'movement_ground_truth':'unconfirmed', 'own_tests_passed':own,
                'advanced': 'Pendiente de repositorio y tutorial asignados por VantTec.'}
    d['evidence'] = evidence
    write_json(ROOT/'web/data/evidence.json', evidence)
    write_json(ROOT/'web/data/session.json', d)
    with (ROOT/'web/data/session.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp','rssi_dbm','quality','phase'])
        writer.writeheader()
        writer.writerows(d['samples'])
    for directory in ['tutorial','sessions','upstream','ui']:
        source = ROOT/'evidence'/directory
        if source.exists():
            shutil.copytree(source, ROOT/'web/evidence'/directory, dirs_exist_ok=True)
    print(json.dumps({'source': chosen.name, 'samples': len(samples), 'frames': len(frames), 'own_passed':own}, indent=2))


if __name__ == '__main__':
    main()
