"""Local-only sensing server. Static publication is a recorded replay."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

from . import ROOT
from .analysis import analyze, from_rows, THRESHOLDS
from .collector import VerifiedWindowsCollector


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


class Lab:
    def __init__(self, evidence_dir=None):
        self.directory = Path(evidence_dir or ROOT / 'evidence' / 'sessions')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.collector = None
        self.session = None
        self.rows = []
        self.active = False
        self.error = None
        self.timer = None

    def sessions(self):
        result = []
        for p in sorted(self.directory.glob('*.json'), reverse=True):
            s = json.loads(p.read_text(encoding='utf-8'))
            result.append({**s['session'], 'samples': len(s['samples'])})
        return result

    def saved(self, ident):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', ident):
            raise ValueError('Identificador inválido')
        p = self.directory / (ident + '.json')
        return json.loads(p.read_text(encoding='utf-8'))

    def start(self, label='Observación WiFi', duration_seconds=60, ground_truth='unconfirmed'):
        with self.lock:
            if self.active:
                raise ValueError('Ya hay una medición en curso.')
            if not isinstance(duration_seconds, (float, int)) or not 15 <= duration_seconds <= 300:
                raise ValueError('Elige una duración entre 15 y 300 segundos.')
            if ground_truth not in {'unconfirmed', 'still', 'walking'}:
                raise ValueError('Etiqueta de observación inválida.')
            now = datetime.now(timezone.utc)
            self.session = {'id': now.strftime('%Y%m%dT%H%M%S') + '_' + uuid4().hex[:6],
                            'label': str(label)[:100], 'started_at': now.isoformat(),
                            'duration_seconds': duration_seconds, 'ground_truth': ground_truth,
                            'ground_truth_source': 'operator_label' if ground_truth != 'unconfirmed' else 'not_observed'}
            self.rows = []
            self.error = None
            self.collector = VerifiedWindowsCollector(on_sample=self.append)
            try:
                self.collector.start()
            except Exception as exc:
                self.error = str(exc)
                self.collector = None
                raise ValueError(self.error) from exc
            self.active = True
            self.timer = threading.Timer(duration_seconds, self.stop)
            self.timer.daemon = True
            self.timer.start()
        return self.snapshot()

    def append(self, sample):
        with self.lock:
            self.rows.append({'timestamp': sample.timestamp, 'rssi_dbm': sample.rssi_dbm,
                              'quality': sample.link_quality if math.isfinite(sample.link_quality) else None,
                              'phase': self.session['ground_truth']})

    def stop(self):
        with self.lock:
            if not self.active:
                return self.snapshot()
            self.active = False
            collector = self.collector
            if self.timer:
                self.timer.cancel()
        if collector:
            collector.stop()
        state = self.snapshot()
        if self.session:
            state['session']['stopped_at'] = datetime.now(timezone.utc).isoformat()
            state['capture_diagnostics'] = {
                'netsh_error_count': collector.error_count if collector else 0,
                'mean_netsh_latency_seconds': sum(collector.latencies) / len(collector.latencies) if collector and collector.latencies else None,
                'raw_rssi_only': True, 'noise_and_byte_counters': 'not_measured'}
            write_json(self.directory / (self.session['id'] + '.json'), state)
        return state

    def snapshot(self):
        with self.lock:
            if not self.session:
                available = self.sessions()
                if available:
                    saved = self.saved(available[0]['id'])
                    saved.update(mode='replay', status='ready', sessions=available)
                    return saved
            rows = list(self.rows)
            error = self.error or (self.collector.last_error if self.collector else None)
            calculated = analyze(from_rows(rows))
            if error or (self.active and rows and time.time() - rows[-1]['timestamp'] > 3):
                calculated['classification'] = None
                calculated['quality'] = {'ready': False, 'reason': error or 'Señal desactualizada'}
            stagefile = ROOT / 'web' / 'data' / 'evidence.json'
            evidence = json.loads(stagefile.read_text(encoding='utf-8')) if stagefile.exists() else {'stages': []}
            return {'mode': 'live' if self.active else 'replay',
                    'status': 'error' if error else ('collecting' if self.active else ('ready' if rows else 'idle')),
                    'error': error, 'session': dict(self.session) if self.session else None,
                    'samples': rows, 'thresholds': THRESHOLDS, **calculated,
                    'sessions': self.sessions(), 'evidence': evidence}


class Handler(SimpleHTTPRequestHandler):
    lab: Lab
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == '/api/state':
                return self.send_json(self.lab.snapshot())
            if parsed.path == '/api/sessions':
                return self.send_json(self.lab.sessions())
            if parsed.path in {'/api/session', '/api/export.csv'}:
                ident = parse_qs(parsed.query).get('id', [''])[0]
                data = self.lab.saved(ident) if ident else self.lab.snapshot()
                if parsed.path == '/api/session':
                    return self.send_json(data)
                output = io.StringIO(newline='')
                writer = csv.DictWriter(output, fieldnames=['timestamp', 'rssi_dbm', 'quality', 'phase'])
                writer.writeheader()
                writer.writerows(data['samples'])
                body = output.getvalue().encode('utf-8-sig')
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="swarm-signal.csv"')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            return super().do_GET()
        except (ValueError, FileNotFoundError) as exc:
            self.send_json({'error': str(exc)}, 404)

    def do_POST(self):
        # Reject cross-origin browser requests and DNS rebinding on local sensor.
        expected = f'http://{self.headers.get("Host", "")}'
        host = self.headers.get('Host', '').split(':')[0]
        if host not in {'127.0.0.1', 'localhost'} or self.headers.get('Origin', expected) != expected:
            return self.send_json({'error': 'Origen no permitido'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 <= size <= 4096:
                raise ValueError('Solicitud demasiado grande')
            body = json.loads(self.rfile.read(size) or b'{}')
            if self.path == '/api/start':
                result = self.lab.start(**{k: body[k] for k in ('label', 'duration_seconds', 'ground_truth') if k in body})
            elif self.path == '/api/stop':
                result = self.lab.stop()
            else:
                return self.send_json({'error': 'Ruta desconocida'}, 404)
            self.send_json(result)
        except (ValueError, TypeError) as exc:
            self.send_json({'error': str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    Handler.lab = Lab()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'SWARM SIGNAL: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        Handler.lab.stop()
        server.server_close()


if __name__ == '__main__':
    main()
