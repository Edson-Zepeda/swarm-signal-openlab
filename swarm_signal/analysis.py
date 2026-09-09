"""Upstream CommodityBackend, with a data-quality gate and explicit spectrum."""
from __future__ import annotations
from dataclasses import asdict
import math
import numpy as np
from v1.src.sensing.backend import CommodityBackend
from v1.src.sensing.classifier import PresenceClassifier
from v1.src.sensing.feature_extractor import RssiFeatureExtractor
from v1.src.sensing.rssi_collector import WifiSample

THRESHOLDS = {'variance': 0.3, 'motion': 0.1}


class RecordedCollector:
    """Replay only recorded WifiSample values, without synthetic generation."""
    sample_rate_hz = 2.0
    def __init__(self, samples):
        self.samples = samples
    def get_samples(self, n=None):
        return self.samples[-n:] if n else self.samples
    def start(self):
        pass
    def stop(self):
        pass


def analyze(samples):
    samples = [s for s in samples if math.isfinite(s.rssi_dbm) and math.isfinite(s.timestamp)]
    if samples:
        samples = [s for s in samples if s.timestamp >= samples[-1].timestamp - 15]
    if len(samples) < 4:
        return {'features': {'n_samples': len(samples)}, 'classification': None,
                'spectrum': [], 'quality': {'ready': False, 'reason': 'Datos insuficientes'}}
    stamps = np.array([s.timestamp for s in samples])
    dt = np.diff(stamps)
    if np.any(dt <= 0):
        return {'features': {'n_samples': len(samples)}, 'classification': None,
                'spectrum': [], 'quality': {'ready': False, 'reason': 'Marcas temporales inválidas'}}
    backend = CommodityBackend(RecordedCollector(samples),
        extractor=RssiFeatureExtractor(window_seconds=15),
        classifier=PresenceClassifier(presence_variance_threshold=THRESHOLDS['variance'],
                                      motion_energy_threshold=THRESHOLDS['motion']))
    features = backend.get_features()
    result = backend.get_result()
    usable = samples[-features.n_samples:]
    values = np.array([s.rssi_dbm for s in usable])
    spectrum = np.abs(np.fft.rfft((values - np.mean(values)) * np.hanning(len(values)))) ** 2 / len(values)
    hz = np.fft.rfftfreq(len(values), 1 / features.sample_rate_hz)
    classification = asdict(result)
    classification['motion_level'] = result.motion_level.value
    jitter = float(np.std(dt) / np.mean(dt))
    full = features.duration_seconds >= 14
    reliable = full and float(np.max(dt)) <= 2.0 and jitter <= .25
    reason = ('Completando ventana de 15 s' if not full else
              ('Pérdida de muestras' if float(np.max(dt)) > 2 else
               ('Muestreo irregular' if jitter > .25 else None)))
    return {'features': asdict(features), 'classification': classification if reliable else None,
            'spectrum': [{'hz': float(f), 'power': float(p)} for f, p in zip(hz[1:], spectrum[1:])],
            'quality': {'ready': reliable, 'nyquist_hz': features.sample_rate_hz / 2,
                        'max_gap_seconds': float(np.max(dt)), 'jitter_cv': jitter,
                        'full_window': full, 'reason': reason},
            'capabilities': sorted(c.name for c in backend.get_capabilities())}


def from_rows(rows):
    return [WifiSample(r['timestamp'], r['rssi_dbm'], float('nan'),
                       r.get('quality') if r.get('quality') is not None else float('nan'),
                       0, 0, 0, 'Wi-Fi') for r in rows]
