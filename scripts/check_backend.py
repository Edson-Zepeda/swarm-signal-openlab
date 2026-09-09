"""Real 15-second integration built on CommodityBackend; no physical label inferred."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataclasses import asdict
from datetime import datetime, timezone
import json
import time
from swarm_signal import ROOT
from swarm_signal.collector import VerifiedWindowsCollector
from swarm_signal.analysis import analyze
from swarm_signal.server import write_json
from v1.src.sensing.backend import CommodityBackend, Capability
from v1.src.sensing.classifier import PresenceClassifier
from v1.src.sensing.feature_extractor import RssiFeatureExtractor

collector = VerifiedWindowsCollector()
backend = CommodityBackend(collector, RssiFeatureExtractor(window_seconds=15),
                           PresenceClassifier(presence_variance_threshold=.3, motion_energy_threshold=.1))
assert backend.get_capabilities() == {Capability.PRESENCE, Capability.MOTION}
assert not backend.is_capable(Capability.RESPIRATION)
assert not backend.is_capable(Capability.LOCATION)
print('CommodityBackend -> VerifiedWindowsCollector, 15 s...', flush=True)
try:
    backend.start()
    time.sleep(15)
finally:
    backend.stop()
result = backend.get_result()
samples = collector.get_samples()
assert len(samples) >= 4
assert all(-120 <= s.rssi_dbm <= -1 for s in samples)
raw_result = asdict(result)
raw_result['motion_level'] = result.motion_level.value
payload = {'time_utc': datetime.now(timezone.utc).isoformat(),
           'capabilities': sorted(c.name for c in backend.get_capabilities()),
           'checks_passed': 5, 'ground_truth': 'unconfirmed',
           'samples': [{'timestamp': s.timestamp, 'rssi_dbm': s.rssi_dbm,
                        'quality': s.link_quality, 'phase': 'unconfirmed'} for s in samples],
           'raw_backend_result': raw_result, 'application_result': analyze(samples)}
write_json(ROOT / 'evidence' / 'tutorial' / '06_commodity_backend.json', payload)
print(json.dumps({k:v for k,v in payload.items() if k != 'samples'}, indent=2, ensure_ascii=True), flush=True)
