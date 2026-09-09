"""Capture real tutorial stages 2-4 and own CommodityBackend integration.

Network identifiers are removed from the public evidence. Human motion is
not inferred from a class label. Run from this project's root directory.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dataclasses
from datetime import datetime, timezone
import importlib.metadata
import json
import platform
import time
import traceback
from swarm_signal import ROOT
from swarm_signal.collector import read_netsh, redact_netsh, parse_netsh
from swarm_signal.analysis import analyze
from swarm_signal.server import Lab, write_json
from v1.src.sensing.rssi_collector import WindowsWifiCollector
from v1.src.sensing.feature_extractor import RssiFeatureExtractor
from v1.src.sensing.classifier import PresenceClassifier


def main():
    evidence = ROOT / 'evidence' / 'tutorial'
    evidence.mkdir(parents=True, exist_ok=True)
    raw = read_netsh()
    (evidence / '02_netsh.txt').write_text(redact_netsh(raw), encoding='utf-8')
    env = {'time_utc': datetime.now(timezone.utc).isoformat(),
           'python': sys.version, 'os': platform.platform(),
           'packages': {p: importlib.metadata.version(p) for p in ['numpy', 'scipy', 'pytest']},
           'source_commit': 'd613a576ea848f96a9b15bac4e7f60b6be7c08e7',
           'network_identifiers': 'redacted',
           'strict_netsh_reading': dataclasses.asdict(parse_netsh(raw))}
    write_json(evidence / '01_environment.json', env)
    original = WindowsWifiCollector(interface='Wi-Fi', sample_rate_hz=2)
    sample = original.collect_once()
    single = {'time_utc': datetime.now(timezone.utc).isoformat(),
              'source': 'upstream WindowsWifiCollector.collect_once',
              'sample': dataclasses.asdict(sample),
              'unmeasured_upstream_fields': ['noise_dbm', 'tx_bytes', 'rx_bytes', 'retry_count'],
              'link_quality_issue': 'Original parser recognizes Signal only; Spanish Señal ignored.'}
    write_json(evidence / '03_single_reading.json', single)
    print('Original WindowsWifiCollector:', sample.rssi_dbm, 'dBm, quality:', sample.link_quality, flush=True)
    print('Collecting original 15-second pipeline...', flush=True)
    original.start()
    time.sleep(15)
    original.stop()
    samples = original.get_samples()
    extractor = RssiFeatureExtractor(window_seconds=15)
    features = extractor.extract(samples)
    result = PresenceClassifier(presence_variance_threshold=0.3).classify(features)
    classification = dataclasses.asdict(result)
    classification['motion_level'] = result.motion_level.value
    payload = {'time_utc': datetime.now(timezone.utc).isoformat(),
               'duration_requested_seconds': 15, 'ground_truth': 'unconfirmed',
               'source': 'unmodified upstream collector/extractor/classifier',
               'features': dataclasses.asdict(features), 'classification': classification,
               'samples': [{'timestamp': s.timestamp, 'rssi_dbm': s.rssi_dbm,
                            'quality': None, 'phase': 'unconfirmed'} for s in samples]}
    write_json(evidence / '04_pipeline_15s.json', payload)
    print(json.dumps({k: payload[k] for k in ('features', 'classification')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
