"""Original RuView pipeline with explicit conservative quality gates.

No resampling or invented readings. RSSI heuristics do not validate human
presence, and at 2 Hz the original motion band is only partially observed.
"""
from __future__ import annotations
from dataclasses import asdict
import math
from numbers import Real
import numpy as np
from v1.src.sensing.backend import CommodityBackend
from v1.src.sensing.classifier import PresenceClassifier
from v1.src.sensing.feature_extractor import RssiFeatureExtractor
from v1.src.sensing.rssi_collector import WifiSample

THRESHOLDS = {'variance': 0.3, 'motion': 0.1}
ANALYSIS_VERSION = '2.0-quality-audit'
MAX_ROWS = 10_000
MAX_JITTER_CV = .05
MAX_INTERVAL_DEVIATION = .15
MIN_MOTION_BINS = 2
PHASES = {'unconfirmed', 'still', 'walking'}


def finite_number(value):
    return isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and math.isfinite(value)


def validate_rows(rows):
    """Validate without coercing, discarding, sorting or changing source rows."""
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError(f'Las muestras deben ser una lista de hasta {MAX_ROWS} filas.')
    previous = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f'Muestra {index}: se esperaba un objeto.')
        stamp, rssi, quality = row.get('timestamp'), row.get('rssi_dbm'), row.get('quality')
        if not finite_number(stamp) or stamp < 0:
            raise ValueError(f'Muestra {index}: marca temporal inválida.')
        if previous is not None and stamp <= previous:
            raise ValueError(f'Muestra {index}: las marcas temporales deben aumentar.')
        if not finite_number(rssi) or not -120 <= rssi <= -1:
            raise ValueError(f'Muestra {index}: RSSI inválido; se admiten [-120, -1] dBm.')
        if quality is not None and (not finite_number(quality) or not 0 <= quality <= 1):
            raise ValueError(f'Muestra {index}: calidad inválida; se admite null o [0, 1].')
        phase = row.get('phase', 'unconfirmed')
        if not isinstance(phase, str) or phase not in PHASES:
            raise ValueError(f'Muestra {index}: condición inválida.')
        previous = stamp
    return rows


class RecordedCollector:
    """Compatibility adapter for recorded, prevalidated measurements."""
    sample_rate_hz = 2.0
    def __init__(self, samples):
        self.samples = samples
    def get_samples(self, n=None):
        return self.samples[-n:] if n else self.samples
    def start(self):
        pass
    def stop(self):
        pass


def _unavailable(count, reason, invalid=0):
    return {'analysis_version': ANALYSIS_VERSION, 'analysis_policy_version': ANALYSIS_VERSION, 'features': {'n_samples': count},
            'classification': None, 'upstream_classification': None, 'spectrum': [],
            'quality': {'ready': False, 'reason': reason, 'invalid_samples': invalid,
                        'spectral_method': 'uniform_spacing_approximation_no_resampling'}}


def _band(hz, low, high, minimum_bins=1):
    selected = hz[(hz >= low) & (hz <= high)]
    return {'configured_hz': [low, high],
            'observed_hz': [float(selected[0]), float(selected[-1])] if len(selected) else None,
            'bins': len(selected), 'minimum_bins': minimum_bins,
            'available': len(selected) >= minimum_bins,
            'coverage': 'none' if not len(selected) else ('full' if hz[-1] >= high else 'partial')}


def analyze(samples):
    if not isinstance(samples, (list, tuple)) or len(samples) > MAX_ROWS:
        return _unavailable(0, 'Lista de muestras inválida', 1)
    invalid = 0
    for sample in samples:
        stamp, rssi = getattr(sample, 'timestamp', None), getattr(sample, 'rssi_dbm', None)
        quality = getattr(sample, 'link_quality', None)
        # WifiSample uses NaN for unavailable quality; strict JSON rows use null.
        quality_missing = isinstance(quality, Real) and math.isnan(quality)
        if (not finite_number(stamp) or stamp < 0 or not finite_number(rssi)
                or not -120 <= rssi <= -1 or (not quality_missing and
                (not finite_number(quality) or not 0 <= quality <= 1))):
            invalid += 1
    if invalid:
        return _unavailable(len(samples), 'Muestras inválidas; no se descartan silenciosamente', invalid)
    if any(b.timestamp <= a.timestamp for a, b in zip(samples, samples[1:])):
        return _unavailable(len(samples), 'Marcas temporales inválidas')
    if samples:
        samples = [s for s in samples if s.timestamp >= samples[-1].timestamp - 15]
    if len(samples) < 4:
        return _unavailable(len(samples), 'Datos insuficientes')
    stamps = np.array([s.timestamp for s in samples])
    dt = np.diff(stamps)
    if np.min(dt) < .001:
        return _unavailable(len(samples), 'Intervalos incompatibles con el colector RSSI')
    backend = CommodityBackend(RecordedCollector(samples),
        extractor=RssiFeatureExtractor(window_seconds=15),
        classifier=PresenceClassifier(presence_variance_threshold=THRESHOLDS['variance'],
                                      motion_energy_threshold=THRESHOLDS['motion']))
    # Actual time window, not nominal-rate count, determines the analysis rows.
    features = backend.extractor.extract(samples)
    result = backend.classifier.classify(features)
    raw_classification = asdict(result)
    raw_classification['motion_level'] = result.motion_level.value
    values = np.array([s.rssi_dbm for s in samples])
    hz = np.fft.rfftfreq(len(values), 1 / features.sample_rate_hz)[1:]
    jitter = float(np.std(dt) / np.mean(dt))
    deviation = float(np.max(np.abs(dt / np.mean(dt) - 1)))
    full = features.duration_seconds >= 14
    regular = jitter <= MAX_JITTER_CV and deviation <= MAX_INTERVAL_DEVIATION
    gap_ok = float(np.max(dt)) <= 2.0
    motion = _band(hz, .5, 3.0, MIN_MOTION_BINS)
    breathing = _band(hz, .1, .5)
    for band in (motion, breathing):
        band['sampling_valid'] = regular and gap_ok
        band['available'] = band['available'] and band['sampling_valid']
    reliable = full and gap_ok and regular and motion['available']
    reason = ('Completando ventana de 15 s' if not full else
              ('Pérdida de muestras' if not gap_ok else
               ('Muestreo irregular: espectro no disponible' if not regular else
                ('Banda de movimiento insuficiente' if not motion['available'] else None))))
    feature_data = asdict(features)
    spectrum = []
    if regular and gap_ok:
        power = np.abs(np.fft.rfft((values - np.mean(values)) * np.hanning(len(values)))) ** 2 / len(values)
        spectrum = [{'hz': float(f), 'power': float(p)} for f, p in zip(hz, power[1:])]
        if not motion['available']:
            feature_data['motion_band_power'] = None
        if not breathing['available']:
            feature_data['breathing_band_power'] = None
    else:
        for name in ('motion_band_power', 'breathing_band_power', 'dominant_freq_hz', 'total_spectral_power'):
            feature_data[name] = None
    classification = dict(raw_classification) if reliable else None
    if classification:
        classification['scope'] = 'Heurística RSSI; banda parcial; sin validación de presencia humana'
    return {'analysis_version': ANALYSIS_VERSION, 'analysis_policy_version': ANALYSIS_VERSION, 'features': feature_data,
            'classification': classification, 'upstream_classification': raw_classification,
            'upstream_classification_scope': 'Salida original sin validación de calidad; no es un veredicto observado',
            'spectrum': spectrum,
            'quality': {'ready': reliable, 'nyquist_hz': features.sample_rate_hz / 2,
                        'max_gap_seconds': float(np.max(dt)), 'jitter_cv': jitter,
                        'max_interval_deviation': deviation, 'max_jitter_cv': MAX_JITTER_CV,
                        'max_interval_deviation_allowed': MAX_INTERVAL_DEVIATION,
                        'full_window': full, 'reason': reason, 'invalid_samples': 0,
                        'motion_band': motion, 'breathing_band': breathing,
                        'spectrum_available': regular and gap_ok,
                        'spectral_method': 'uniform_spacing_approximation_no_resampling'},
            'capabilities': sorted(c.name for c in backend.get_capabilities())}


def from_rows(rows):
    validate_rows(rows)
    return [WifiSample(r['timestamp'], r['rssi_dbm'], float('nan'),
                       r.get('quality') if r.get('quality') is not None else float('nan'),
                       0, 0, 0, 'recorded') for r in rows]
