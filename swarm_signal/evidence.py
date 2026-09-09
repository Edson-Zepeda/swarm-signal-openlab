"""Evidence-derived delivery state. Missing artifacts never earn completion."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def read_json(root, relative):
    try:
        value = json.loads((Path(root)/relative).read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def test_counts(path):
    try:
        cases = list(ET.parse(path).getroot().iter('testcase'))
    except (OSError, ET.ParseError):
        cases = []
    return {'total': len(cases),
            'passed': sum(not any(c.find(t) is not None for t in ('failure','error','skipped')) for c in cases),
            'failed': sum(any(c.find(t) is not None for t in ('failure','error')) for c in cases),
            'skipped': sum(c.find('skipped') is not None for c in cases)}


def valid_rows(rows):
    return isinstance(rows, list) and bool(rows) and all(
        isinstance(r, dict) and all(isinstance(r.get(k), (int,float)) and not isinstance(r[k], bool)
            and math.isfinite(r[k]) for k in ('timestamp','rssi_dbm'))
        and -120 <= r['rssi_dbm'] <= -1 for r in rows)


def reference_recording(root):
    root = Path(root)
    config = read_json(root, 'project.json')
    selected = next((r for r in config.get('recordings', []) if r.get('id') == config.get('reference_session')), None)
    if not selected or selected.get('kind') != 'recorded_real_wifi':
        raise ValueError('Falta una captura real de referencia explícita y revisada.')
    path = (root/selected['source']).resolve()
    if not path.is_relative_to(root.resolve()/'evidence/sessions'):
        raise ValueError('La referencia debe pertenecer a evidence/sessions.')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != selected['sha256']:
        raise ValueError('La captura de referencia no coincide con su SHA-256.')
    data = json.loads(raw.decode('utf-8-sig'))
    if not valid_rows(data.get('samples')) or data.get('session', {}).get('id') != selected['id']:
        raise ValueError('Captura de referencia inválida.')
    if data['session'].get('ground_truth') != selected.get('ground_truth'):
        raise ValueError('La condición física difiere del manifiesto.')
    return data, selected, config


def build_evidence(root):
    root = Path(root)
    config = read_json(root, 'project.json')
    env = read_json(root, 'evidence/tutorial/01_environment.json')
    single = read_json(root, 'evidence/tutorial/03_single_reading.json')
    pipeline = read_json(root, 'evidence/tutorial/04_pipeline_15s.json')
    commodity = read_json(root, 'evidence/tutorial/06_commodity_backend.json')
    unit = test_counts(root/'evidence/upstream/unit.xml')
    live = test_counts(root/'evidence/upstream/live_adapted.xml')
    own_path = config.get('own_tests', 'evidence/own_tests.xml')
    own = test_counts(root/own_path)
    verify_path = config.get('verification', 'evidence/upstream/verification_summary.json')
    verification = read_json(root, verify_path)
    stages = []

    def stage(ident, title, complete, summary, artifact, *, partial=False, links=()):
        exists = (root/artifact).is_file()
        stages.append({'id': ident, 'title': title,
                       'status': 'complete' if complete and exists else 'partial' if exists and partial else 'pending',
                       'summary': summary if exists else 'Falta la evidencia de esta etapa.',
                       'artifact_url': artifact if exists else None,
                       'artifact_links': [{'label': label, 'url': path} for label,path in links if (root/path).is_file()]})

    stage('01', 'Entorno reproducible', bool(env.get('python') and env.get('packages')
          and env.get('source_commit') == config.get('upstream_commit')),
          'Python, dependencias y commit registrados.', 'evidence/tutorial/01_environment.json')
    netsh_path = root/'evidence/tutorial/02_netsh.txt'
    netsh = netsh_path.read_text(encoding='utf-8-sig') if netsh_path.is_file() else ''
    stage('02', 'Conexión WiFi', bool(netsh.strip()),
          'Salida real de Windows con identificadores omitidos.', 'evidence/tutorial/02_netsh.txt')
    rssi = single.get('sample', {}).get('rssi_dbm')
    valid_rssi = isinstance(rssi, (int,float)) and not isinstance(rssi, bool) and math.isfinite(rssi) and -120 <= rssi <= -1
    stage('03', 'Lectura individual', valid_rssi,
          f'{rssi:g} dBm con el colector original.' if valid_rssi else 'Lectura no verificable.',
          'evidence/tutorial/03_single_reading.json')
    rows = pipeline.get('samples')
    valid = valid_rows(rows) and len(rows) >= 4
    elapsed = rows[-1]['timestamp']-rows[0]['timestamp'] if valid else 0
    valid = valid and elapsed >= 14 and all(b['timestamp'] > a['timestamp'] for a,b in zip(rows,rows[1:]))
    verdict = pipeline.get('classification', {}).get('motion_level')
    valid = valid and verdict in {'absent','present_still','active'}
    stage('04', 'Pipeline de 15 s', valid,
          f'{len(rows)} muestras · {(len(rows)-1)/elapsed:.2f} Hz · salida {verdict}.' if valid else 'Pipeline incompleto.',
          'evidence/tutorial/04_pipeline_15s.json')
    physical = config.get('physical_evidence') or {}
    physical_complete = False
    if physical.get('operator_confirmed') is True:
        observed = read_json(root, physical.get('session', ''))
        physical_complete = (observed.get('session', {}).get('ground_truth') == 'walking'
                             and observed.get('session', {}).get('ground_truth_source') == 'operator_label'
                             and valid_rows(observed.get('samples'))
                             and (root/physical.get('screenshot', 'missing')).is_file())
    screenshot = physical.get('screenshot') if physical_complete else 'evidence/ui/monitor-live.png'
    stage('05', 'Monitor y movimiento', physical_complete,
          'Captura en vivo y movimiento confirmado por el participante.' if physical_complete else
          'Monitor real. Falta confirmar el movimiento del participante.', screenshot, partial=True,
          links=[('Captura del monitor', screenshot), ('Datos de la captura', 'evidence/ui/monitor-live-state.json')])
    backend_ok = commodity.get('checks_passed', 0) > 0 and valid_rows(commodity.get('samples'))
    stage('06', 'CommodityBackend', backend_ok,
          f"{commodity.get('checks_passed', 0)} comprobaciones con el adaptador real.",
          'evidence/tutorial/06_commodity_backend.json')
    tests_ok = all(c['total'] > 0 and c['passed'] == c['total'] for c in (unit, live, own))
    stage('07', 'Pruebas', tests_ok,
          f"{unit['passed']} unitarias · {live['passed']} integraciones adaptadas · {own['passed']} propias.",
          own_path, partial=True, links=[('Pruebas originales','evidence/upstream/verification_summary.json'),
                                       ('Pruebas de la revisión',own_path)])
    phases = verification.get('phases', [])
    counts = {s:sum(p.get('status') == s.upper() for p in phases) for s in ('pass','fail','skip')}
    verify_ok = (verification.get('exit_code') == 0 and verification.get('source_unchanged') is True
                 and len(phases) == 9 and counts['fail'] == 0
                 and any(p.get('phase') == 1 and p.get('status') == 'PASS' for p in phases))
    stage('08', 'Verificación determinística', verify_ok,
          f"{counts['pass']} fases PASS · {counts['skip']} SKIP. CSI: hash exacto." if verify_ok else
          'La verificación conserva fallos u omisiones; consulta el registro.', verify_path, partial=True,
          links=[('Ejecución actual','evidence/revision/verify_identified.log'),
                 ('Fallo inicial conservado','evidence/upstream/03_verify_original_shell.log')])
    return {'stages': stages, 'completed': sum(s['status']=='complete' for s in stages),
            'total': len(stages), 'movement_ground_truth': 'operator_confirmed' if physical_complete else 'unconfirmed',
            'physical_evidence_complete': physical_complete,
            'own_tests_passed': own['passed'], 'tests': {'unit':unit,'live_adapted':live,'own':own},
            'verification': {'passed':counts['pass'],'failed':counts['fail'],'skipped':counts['skip'],
                             'scope':'Only phases that ran; skipped phases are not verified.'},
            'advanced': config.get('advanced', {}).get('reason', 'Opcional; fuera del reto base.')}
