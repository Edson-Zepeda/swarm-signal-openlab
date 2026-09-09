"""A repeatable real measurement using CommodityBackend-compatible collector."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import json
import time
from swarm_signal.server import Lab

parser = argparse.ArgumentParser(description='Mide RSSI directo. No genera datos simulados.')
parser.add_argument('--seconds', type=int, default=60)
parser.add_argument('--label', default='Observación ambiental')
parser.add_argument('--condition', choices=['unconfirmed', 'still', 'walking'], default='unconfirmed')
args = parser.parse_args()
lab = Lab()
try:
    lab.start(args.label, args.seconds, args.condition)
    print('Capturando. Condición declarada:', args.condition, flush=True)
    while lab.active:
        time.sleep(3)
        s = lab.snapshot()
        c = s.get('classification') or {}
        f = s.get('features') or {}
        print(json.dumps({'samples': len(s['samples']), 'rssi_mean_dbm': f.get('mean'),
                          'variance': f.get('variance'), 'class': c.get('motion_level'),
                          'quality': s.get('quality')}, ensure_ascii=False), flush=True)
except KeyboardInterrupt:
    lab.stop()
finally:
    lab.stop()
    while lab.stopping:
        time.sleep(.1)
    if lab.session:
        print('Evidencia:', lab.directory / (lab.session['id'] + '.json'))
