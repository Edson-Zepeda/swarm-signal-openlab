"""Compare recorded sessions descriptively, using disjoint 15-second windows."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

from . import ROOT
from .analysis import analyze, from_rows, validate_rows

WINDOW_SECONDS = 15
# The recorder allows at most five minutes; this generous import limit also
# prevents corrupt timestamps from creating millions of empty windows.
MAX_COMPARISON_SECONDS = 3600
MAX_RECORDING_BYTES = 16 * 1024 * 1024


def describe_session(data, *, source, label=None, source_sha256=None, source_kind='unverified'):
    rows = data['samples']
    if not isinstance(rows, list) or not rows:
        raise ValueError('No hay muestras')
    validate_rows(rows)
    times = [r['timestamp'] for r in rows]
    gaps = [b-a for a, b in zip(times, times[1:])]
    if any(g <= 0 for g in gaps):
        raise ValueError('Marcas temporales no crecientes')
    values = [r['rssi_dbm'] for r in rows]
    coverage = times[-1]-times[0]
    if coverage > MAX_COMPARISON_SECONDS:
        raise ValueError('La comparación admite capturas de hasta 3600 segundos.')
    windows = []
    # Every sample belongs to exactly one window. No sliding-window pseudo-replication.
    buckets = {}
    for row in rows:
        index = int((row['timestamp']-times[0]) // WINDOW_SECONDS)
        buckets.setdefault(index, []).append(row)
    for index in range(max(buckets)+1):
        chunk = buckets.get(index, [])
        measured_span = chunk[-1]['timestamp']-chunk[0]['timestamp'] if len(chunk)>1 else 0
        result = analyze(from_rows(chunk))
        horizon = min((index+1)*WINDOW_SECONDS, coverage)-index*WINDOW_SECONDS
        eligible = horizon >= 14
        ready = eligible and bool(result.get('quality', {}).get('ready'))
        features = result.get('features', {})
        classification = result.get('classification') or {}
        windows.append({'index': index, 'start_seconds': index*WINDOW_SECONDS,
                        'end_seconds': min((index+1)*WINDOW_SECONDS, coverage),
                        'count': len(chunk), 'coverage_seconds': measured_span,
                        'eligible': eligible, 'ready': ready,
                        'reason': result.get('quality', {}).get('reason') if not ready else None,
                        'motion_level': classification.get('motion_level') if ready else None,
                        'variance': statistics.variance([r['rssi_dbm'] for r in chunk]) if len(chunk)>1 else None,
                        'effective_rate_hz': (len(chunk)-1)/measured_span if measured_span else None,
                        'ground_truth': data['session'].get('ground_truth', 'unconfirmed')})
    eligible_count = sum(w['eligible'] for w in windows)
    valid_count = sum(w['ready'] for w in windows)
    metadata = data['session']
    return {'id': metadata['id'], 'label': label or metadata.get('label', metadata['id']),
            'source': source, 'source_sha256': source_sha256, 'source_kind': source_kind,
            'ground_truth': metadata.get('ground_truth', 'unconfirmed'),
            'ground_truth_source': metadata.get('ground_truth_source', 'not_observed'),
            'count': len(rows), 'coverage_seconds': coverage,
            'effective_rate_hz': (len(rows)-1)/coverage if coverage else None,
            'mean_dbm': statistics.mean(values),
            'sample_variance': statistics.variance(values) if len(values)>1 else None,
            'jitter_cv': statistics.pstdev(gaps)/statistics.mean(gaps) if gaps else None,
            'max_gap_seconds': max(gaps) if gaps else None,
            'windows_total': len(windows), 'windows_eligible': eligible_count,
            'windows_valid': valid_count, 'windows_abstained': len(windows)-valid_count,
            'valid_fraction': valid_count/eligible_count if eligible_count else None,
            'reasons': dict(Counter(w['reason'] or 'Ventana incompleta' for w in windows if not w['ready'])),
            'windows': windows}


def build_comparison(directory=None):
    directory = Path(directory or ROOT/'evidence/sessions')
    config = json.loads((ROOT/'project.json').read_text(encoding='utf-8'))
    known = {x['id']: x for x in config.get('recordings', [])}
    result = []
    ignored = []
    for path in sorted(directory.glob('*.json')):
        try:
            if path.stat().st_size > MAX_RECORDING_BYTES:
                raise ValueError('El archivo excede el límite de 16 MB.')
            raw = path.read_bytes()
            if len(raw) > MAX_RECORDING_BYTES:
                raise ValueError('El archivo excede el límite de 16 MB.')
            data = json.loads(raw.decode('utf-8-sig'))
            ident = data['session']['id']
            if ident != path.stem:
                raise ValueError('El identificador no coincide con el archivo')
            digest = hashlib.sha256(raw).hexdigest()
            record = known.get(ident)
            trusted = bool(record and record['sha256'] == digest)
            if record and not trusted:
                raise ValueError('La evidencia de referencia fue modificada')
            result.append(describe_session(data, source='evidence/sessions/'+path.name,
                          source_sha256=digest, label=record.get('label') if trusted else None,
                          source_kind=record['kind'] if trusted else 'unverified_recording'))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            ignored.append({'file': path.name, 'reason': str(exc)})
    declared = [s for s in result if s['ground_truth'] in {'still', 'walking'}
                and s['ground_truth_source'] == 'operator_label']
    conditions = sorted({s['ground_truth'] for s in declared})
    return {'version': 1, 'window_seconds': WINDOW_SECONDS,
            'method': {'variance': 'sample, ddof=1', 'jitter': 'population CV of all inter-sample intervals',
                       'windows': 'disjoint [start,end), 15 seconds, all samples retained',
                       'eligible': 'nominal window horizon within observed recording >=14 seconds; gaps stay in denominator',
                       'valid_fraction': 'ready windows / eligible windows; not detection accuracy',
                       'scope': 'Descriptive technical comparison; repeated windows are not independent human trials.'},
            'sessions': result, 'ignored_sessions': ignored,
            'physical': {'confirmed_sessions': len(declared), 'conditions': conditions,
                         'comparison_ready': set(conditions) == {'still', 'walking'},
                         'reason': ('Condiciones declaradas por el participante; contraste exploratorio.'
                                    if set(conditions) == {'still','walking'} else
                                    'Faltan capturas con quietud y cruces confirmados por el participante.')}}
