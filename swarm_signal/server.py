"""Local sensing server with validated replays and retryable persistence."""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse, parse_qs, unquote
from uuid import uuid4

from . import ROOT
from .analysis import analyze, from_rows, validate_rows, finite_number, PHASES, THRESHOLDS, ANALYSIS_VERSION, MAX_ROWS
from .collector import VerifiedWindowsCollector, connected_interfaces, read_netsh

MAX_SESSION_BYTES = 16 * 1024 * 1024
ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,80}')


class SessionConflict(ValueError):
    pass


def _no_constant(value):
    raise ValueError(f'JSON no admite {value}.')


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f'Campo JSON duplicado: {name}')
        result[name] = value
    return result


def strict_json(text):
    try:
        return json.loads(text, parse_constant=_no_constant, object_pairs_hook=_unique_object)
    except (RecursionError, UnicodeDecodeError) as exc:
        raise ValueError('JSON inválido.') from exc


def validate_session(payload, expected_id=None):
    if not isinstance(payload, dict) or not isinstance(payload.get('session'), dict):
        raise ValueError('Sesión inválida: se esperaba un objeto con metadatos.')
    session = payload['session']
    ident = session.get('id')
    if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident):
        raise ValueError('Identificador de sesión inválido.')
    if expected_id is not None and ident != expected_id:
        raise ValueError('El identificador de la sesión no coincide con el archivo.')
    if not isinstance(session.get('label'), str) or not 1 <= len(session['label']) <= 100:
        raise ValueError('Nombre de sesión inválido.')
    phase = session.get('ground_truth', 'unconfirmed')
    if not isinstance(phase, str) or phase not in PHASES:
        raise ValueError('Condición de sesión inválida.')
    if 'duration_seconds' in session:
        duration = session['duration_seconds']
        if not finite_number(duration) or not 15 <= duration <= 300:
            raise ValueError('Duración de sesión inválida.')
    validate_rows(payload.get('samples'))
    return payload


def load_session(path):
    path = Path(path)
    if path.stat().st_size > MAX_SESSION_BYTES:
        raise ValueError('Archivo de sesión demasiado grande.')
    raw = path.read_bytes()
    if len(raw) > MAX_SESSION_BYTES:
        raise ValueError('Archivo de sesión demasiado grande.')
    return validate_session(strict_json(raw.decode('utf-8-sig')), path.stem)


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


class Lab:
    def __init__(self, evidence_dir=None, interface=None):
        self.directory = Path(evidence_dir or ROOT / 'evidence' / 'sessions')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.interface = interface
        self.lock = threading.RLock()
        self.collector = None
        self.session = None
        self.rows = []
        self.active = False
        self.stopping = False
        self.pending_save = False
        self.persistence_error = None
        self.error = None
        self.timer = None
        self.replay_frames = []
        self.capture_diagnostics = None
        self.provenance = None
        self.catalog_errors = []
        self._replay_cache = {}

    def sessions(self):
        result, errors = [], []
        for path in sorted(self.directory.glob('*.json'), reverse=True):
            try:
                data = load_session(path)
                result.append({**data['session'], 'samples': len(data['samples'])})
            except (ValueError, OSError) as exc:
                errors.append({'file': path.name, 'error': str(exc)})
        self.catalog_errors = errors
        return result

    def saved(self, ident):
        if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident):
            raise ValueError('Identificador inválido')
        return load_session(self.directory / (ident + '.json'))

    def resolve(self, ident):
        with self.lock:
            if not ident or (self.session and ident == self.session['id']):
                return self.snapshot()
            return self._replay(ident)

    def _replay(self, ident):
        if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident):
            raise ValueError('Identificador inválido')
        path = self.directory / (ident + '.json')
        if path.stat().st_size > MAX_SESSION_BYTES:
            raise ValueError('Archivo de sesión demasiado grande.')
        raw = path.read_bytes()
        if len(raw) > MAX_SESSION_BYTES:
            raise ValueError('Archivo de sesión demasiado grande.')
        data = validate_session(strict_json(raw.decode('utf-8-sig')), ident)
        digest = hashlib.sha256(raw).hexdigest()
        original_policy = data.get('analysis_policy_version', data.get('analysis_version', 'legacy_unversioned'))
        signature = (ident, digest, ANALYSIS_VERSION)
        if signature not in self._replay_cache:
            samples = from_rows(data['samples'])
            frames = [{'index': i, **analyze(samples[:i+1])} for i in range(len(samples))]
            # Derived views do not replace or edit any historical session file.
            self._replay_cache = {signature: {'frames': frames, **analyze(samples)}}
        data.update(copy.deepcopy(self._replay_cache[signature]))
        data['replay_source'] = {'sha256': digest, 'analysis_policy_version': original_policy,
                                 'source_preserved': True, 'derived_view': True}
        data.update(mode='replay', status='ready', pending_save=False,
                    persistence={'status': 'saved', 'error': None}, sessions=self.sessions(),
                    catalog_errors=list(self.catalog_errors), evidence=self._evidence())
        return data

    @staticmethod
    def _evidence():
        path = ROOT / 'web' / 'data' / 'evidence.json'
        if not path.exists():
            return {'stages': []}
        try:
            payload = strict_json(path.read_text(encoding='utf-8-sig'))
            if not isinstance(payload, dict) or not isinstance(payload.get('stages', []), list):
                raise ValueError('Índice de evidencia inválido.')
            return payload
        except (ValueError, OSError) as exc:
            return {'stages': [], 'error': str(exc)}

    def start(self, label='Observación WiFi', duration_seconds=60, ground_truth='unconfirmed', interface=None):
        with self.lock:
            if self.active or self.stopping:
                raise SessionConflict('Ya hay una medición en curso.')
            if self.pending_save:
                raise SessionConflict('Hay una captura sin guardar. Reintenta guardar antes de iniciar otra.')
            if not finite_number(duration_seconds) or not 15 <= duration_seconds <= 300:
                raise ValueError('Elige una duración entre 15 y 300 segundos.')
            if not isinstance(ground_truth, str) or ground_truth not in PHASES:
                raise ValueError('Etiqueta de observación inválida.')
            if not isinstance(label, str) or not label.strip() or len(label) > 100:
                raise ValueError('Usa un nombre de 1 a 100 caracteres.')
            if interface is not None and (not isinstance(interface, str) or not interface.strip() or len(interface) > 100):
                raise ValueError('Nombre de interfaz inválido.')
            now = datetime.now(timezone.utc)
            ident = now.strftime('%Y%m%dT%H%M%S') + '_' + uuid4().hex[:6]
            callback = lambda sample: self.append(sample, ident)
            selected = self.interface if interface is None else interface
            collector = (VerifiedWindowsCollector(interface=selected, on_sample=callback) if selected is not None
                         else VerifiedWindowsCollector(on_sample=callback))
            # Validate/start before replacing the previous completed session.
            try:
                collector.start()
            except Exception as exc:
                self.error = str(exc)
                try:
                    collector.stop()
                except Exception:
                    # Retain a retryable failed run if its reader cannot close.
                    self.collector, self.active, self.pending_save = collector, False, True
                    self.session = {'id': ident, 'label': label.strip(), 'started_at': now.isoformat(),
                                    'duration_seconds': duration_seconds, 'ground_truth': ground_truth,
                                    'ground_truth_source': 'operator_label' if ground_truth != 'unconfirmed' else 'not_observed'}
                    self.rows, self.replay_frames = [], []
                    self.capture_diagnostics, self.provenance = None, None
                    self.persistence_error = 'El lector no pudo cerrarse. Reintenta detener y guardar.'
                raise ValueError(self.error) from exc
            self.session = {'id': ident, 'label': label.strip(), 'started_at': now.isoformat(),
                            'duration_seconds': duration_seconds, 'ground_truth': ground_truth,
                            'ground_truth_source': 'operator_label' if ground_truth != 'unconfirmed' else 'not_observed',
                            'interface': getattr(collector, 'selected_interface', selected)}
            self.rows, self.replay_frames = [], []
            self.capture_diagnostics = None
            self.pending_save, self.persistence_error, self.error = False, None, None
            self.collector = collector
            self.provenance = {'kind': 'recorded_real_wifi', 'capture_method': 'windows_netsh_direct_rssi',
                               'ground_truth': ground_truth, 'ground_truth_source': self.session['ground_truth_source'],
                               'physical_validation': 'not_verified', 'network_identifiers': 'not included'}
            self.active = True
            self.timer = threading.Timer(duration_seconds, lambda: self._timer_stop(ident))
            self.timer.daemon = True
            try:
                self.timer.start()
            except Exception:
                # Preserve any acquired rows and expose a retryable stop/save.
                self.active, self.pending_save = False, True
                self.persistence_error = 'No se pudo programar el cierre. Detén y guarda la captura.'
                raise
        return self.snapshot()

    def _timer_stop(self, ident):
        try:
            self.stop(ident)
        except (OSError, ValueError, RuntimeError):
            # stop() keeps the error and unsaved data visible for manual retry.
            pass

    def append(self, sample, ident):
        with self.lock:
            if not self.active or not self.session or ident != self.session['id'] or self.stopping:
                return
            quality = sample.link_quality
            row = {'timestamp': sample.timestamp, 'rssi_dbm': sample.rssi_dbm,
                   'quality': None if isinstance(quality, (float, int)) and math.isnan(quality) else quality,
                   'phase': self.session['ground_truth']}
            try:
                if len(self.rows) >= MAX_ROWS:
                    raise ValueError('Se alcanzó el límite de muestras de la sesión.')
                validate_rows([*self.rows[-1:], row])
            except ValueError as exc:
                self.error = str(exc)
                raise
            self.rows.append(row)

    def stop(self, ident=None):
        with self.lock:
            if (ident and (not self.session or ident != self.session['id'])) or self.stopping:
                return self.snapshot()
            if not self.active and not self.pending_save:
                return self.snapshot()
            self.active, self.stopping, self.pending_save = False, True, True
            collector = self.collector
            if self.timer:
                self.timer.cancel()
        try:
            if collector:
                collector.stop()
            with self.lock:
                self.session.setdefault('stopped_at', datetime.now(timezone.utc).isoformat())
                if not self.replay_frames:
                    recorded = from_rows(self.rows)
                    self.replay_frames = [{'index': i, **analyze(recorded[:i+1])} for i in range(len(recorded))]
                self.capture_diagnostics = {
                    'netsh_error_count': collector.error_count if collector else 0,
                    'mean_netsh_latency_seconds': sum(collector.latencies) / len(collector.latencies) if collector and collector.latencies else None,
                    'raw_rssi_only': True, 'noise_and_byte_counters': 'not_measured'}
                state = self.snapshot()
                state['pending_save'] = False
                state['persistence'] = {'status': 'saved', 'error': None}
                state['error'] = self.error or (collector.last_error if collector else None)
                state['status'] = 'error' if state['error'] else 'ready'
                write_json(self.directory / (self.session['id'] + '.json'), state)
                self.pending_save, self.persistence_error = False, None
        except Exception as exc:
            with self.lock:
                self.persistence_error = f'No se pudo guardar la captura: {exc}'
            raise
        finally:
            with self.lock:
                self.stopping = False
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            available = self.sessions()
            if not self.session and available:
                return self._replay(available[0]['id'])
            rows = list(self.rows)
            measurement_error = self.error or (self.collector.last_error if self.collector else None)
            error = self.persistence_error or measurement_error
            calculated = analyze(from_rows(rows))
            if measurement_error or (self.active and rows and time.time() - rows[-1]['timestamp'] > 3):
                calculated['classification'] = None
                calculated['quality'].update(ready=False, reason=measurement_error or 'Señal desactualizada')
            status = ('save_error' if self.persistence_error else ('stopping' if self.stopping else
                      ('error' if measurement_error else ('collecting' if self.active else ('ready' if self.session else 'idle')))))
            persistence = 'pending' if self.pending_save else ('collecting' if self.active else ('saved' if self.session and 'stopped_at' in self.session else 'none'))
            return {'mode': 'live' if self.active else 'replay', 'status': status, 'error': error,
                    'pending_save': self.pending_save, 'persistence': {'status': persistence, 'error': self.persistence_error},
                    'session': dict(self.session) if self.session else None, 'samples': rows,
                    'thresholds': THRESHOLDS, **calculated, 'frames': self.replay_frames if not self.active else [],
                    'capture_diagnostics': self.capture_diagnostics, 'provenance': self.provenance,
                    'sessions': available, 'catalog_errors': list(self.catalog_errors), 'evidence': self._evidence()}


class Handler(SimpleHTTPRequestHandler):
    lab: Lab
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

    def do_HEAD(self):
        if self.headers.get('Host', '').split(':')[0] not in {'127.0.0.1', 'localhost'}:
            self.send_error(403, 'Host not permitted')
            return
        super().do_HEAD()

    def send_head(self):
        """Serve seekable local media with one bounded byte range.

        Multiple ranges and unsupported/malformed range syntax are ignored,
        returning the complete representation, as allowed by HTTP. Range only
        applies to GET; HEAD describes the complete representation without a body.
        """
        self._media_remaining = None
        if not unquote(urlparse(self.path).path).startswith('/media/'):
            return super().send_head()
        path = Path(self.translate_path(self.path))
        if not path.resolve().is_relative_to((ROOT / 'web' / 'media').resolve()):
            self.send_error(403, 'Media path not permitted')
            return None
        if path.is_dir():
            return super().send_head()
        try:
            stream = path.open('rb')
        except OSError:
            self.send_error(404, 'Media not found')
            return None
        try:
            stat = os.fstat(stream.fileno())
            size = stat.st_size
            start, end, partial = 0, size - 1, False
            header = self.headers.get('Range', '') if self.command == 'GET' else ''
            # If-Range may use our Last-Modified validator. Unrecognized or
            # invalid validators require a complete response, never stale bytes.
            validator = self.headers.get('If-Range')
            if header and validator:
                try:
                    date = parsedate_to_datetime(validator)
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=timezone.utc)
                    if int(stat.st_mtime) > date.timestamp():
                        header = ''
                except (ValueError, TypeError, OverflowError):
                    header = ''
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', header.strip(), flags=re.I)
            if match and (match[1] or match[2]):
                first, last = match.groups()
                def bounded_integer(value):
                    digits = value.lstrip('0') or '0'
                    return min(int(digits), size + 1) if len(digits) <= 20 else size + 1
                if first:
                    start = bounded_integer(first)
                    end = min(bounded_integer(last), size - 1) if last else size - 1
                else:
                    length = bounded_integer(last)
                    start, end = max(0, size - length), size - 1
                if start >= size or end < start:
                    stream.close()
                    self.send_response(416)
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return None
                partial = True
            length = max(0, end - start + 1)
            stream.seek(start)
            self._media_remaining = length
            self.send_response(206 if partial else 200)
            self.send_header('Content-Type', self.guess_type(str(path)))
            self.send_header('Content-Length', str(length))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Last-Modified', self.date_time_string(stat.st_mtime))
            if partial:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            return stream
        except Exception:
            stream.close()
            raise

    def copyfile(self, source, outputfile):
        remaining = getattr(self, '_media_remaining', None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        # Bound every write to the selected range, even for an open-ended GET.
        try:
            while remaining:
                block = source.read(min(64 * 1024, remaining))
                if not block:
                    break
                outputfile.write(block)
                remaining -= len(block)
        except (BrokenPipeError, ConnectionResetError):
            # A seek cancels the previous transfer in normal browser playback.
            pass

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get('Host', '').split(':')[0] not in {'127.0.0.1', 'localhost'}:
            return self.send_json({'error': 'Host no permitido'}, 403)
        parsed = urlparse(self.path)
        try:
            if parsed.path == '/api/state':
                return self.send_json(self.lab.snapshot())
            if parsed.path == '/api/sessions':
                return self.send_json(self.lab.sessions())
            if parsed.path == '/api/comparison':
                from .experiment import build_comparison
                result = build_comparison(self.lab.directory)
                if not isinstance(result, dict):
                    raise ValueError('Comparación inválida.')
                return self.send_json(result)
            if parsed.path == '/api/interfaces':
                interfaces = connected_interfaces(read_netsh())
                return self.send_json({'interfaces': interfaces, 'selection_required': len(interfaces) > 1})
            if parsed.path in {'/api/session', '/api/export.csv'}:
                ident = parse_qs(parsed.query).get('id', [''])[0]
                data = self.lab.resolve(ident)
                if parsed.path == '/api/session':
                    return self.send_json(data)
                output = io.StringIO(newline='')
                fields = ['timestamp', 'rssi_dbm', 'quality', 'phase']
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                writer.writerows({k: row.get(k) for k in fields} for row in data['samples'])
                body = output.getvalue().encode('utf-8-sig')
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="swarm-signal.csv"')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            return super().do_GET()
        except FileNotFoundError:
            self.send_json({'error': 'Sesión no encontrada.'}, 404)
        except (ValueError, TypeError) as exc:
            self.send_json({'error': str(exc)}, 400)
        except (OSError, RuntimeError, ImportError) as exc:
            self.send_json({'error': str(exc)}, 503)

    def do_POST(self):
        expected = f'http://{self.headers.get("Host", "")}'
        host = self.headers.get('Host', '').split(':')[0]
        if host not in {'127.0.0.1', 'localhost'} or self.headers.get('Origin', expected) != expected:
            return self.send_json({'error': 'Origen no permitido'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 <= size <= 4096:
                raise ValueError('Solicitud demasiado grande')
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('Codificación de solicitud no admitida.')
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('La solicitud debe usar application/json.')
            body = strict_json(self.rfile.read(size) or b'{}')
            if not isinstance(body, dict):
                raise ValueError('El cuerpo JSON debe ser un objeto.')
            if self.path == '/api/start':
                if set(body) - {'label', 'duration_seconds', 'ground_truth', 'interface'}:
                    raise ValueError('La solicitud contiene campos desconocidos.')
                result = self.lab.start(**body)
            elif self.path == '/api/stop':
                if body:
                    raise ValueError('Detener no admite parámetros.')
                result = self.lab.stop()
            else:
                return self.send_json({'error': 'Ruta desconocida'}, 404)
            self.send_json(result)
        except SessionConflict as exc:
            self.send_json({'error': str(exc)}, 409)
        except (ValueError, TypeError) as exc:
            self.send_json({'error': str(exc)}, 400)
        except (OSError, RuntimeError) as exc:
            self.send_json({'error': str(exc), 'state': self.lab.snapshot()}, 503)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--interface', help='Nombre exacto; se detecta automáticamente si solo hay una conectada.')
    args = parser.parse_args()
    Handler.lab = Lab(interface=args.interface)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'SWARM SIGNAL: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            Handler.lab.stop()
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
