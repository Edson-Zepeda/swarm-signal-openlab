"""Negative audit regressions. All readings and interfaces are synthetic.

No netsh, hardware capture, or historical evidence writes are performed here.
"""
from __future__ import annotations
from dataclasses import replace
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import sys
import threading
import types

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import swarm_signal.analysis as analysis
import swarm_signal.collector as collector_module
import swarm_signal.server as server
from v1.src.sensing.rssi_collector import WifiSample


def sample(stamp=1000., rssi=-60.):
    return WifiSample(stamp, rssi, float('nan'), .8, 0, 0, 0, 'synthetic-fixture')


class FakeTimer:
    def __init__(self, duration, function):
        self.function, self.daemon = function, False
    def start(self):
        pass
    def cancel(self):
        pass


class FakeCollector:
    def __init__(self, on_sample, interface=None):
        self.on_sample, self.selected_interface = on_sample, interface
        self.last_error, self.error_count, self.latencies = None, 0, [.01]
        self.stops = 0
    def start(self):
        pass
    def stop(self):
        self.stops += 1


@pytest.fixture
def lab(monkeypatch, tmp_path):
    monkeypatch.setattr(server, 'VerifiedWindowsCollector', FakeCollector)
    monkeypatch.setattr(server.threading, 'Timer', FakeTimer)
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    instance = server.Lab(tmp_path / 'sessions')
    yield instance
    try:
        instance.stop()
    except (ValueError, KeyError):
        # The audited baseline cannot read deliberately broken catalog files.
        # The actual behavior is asserted above; fake fixtures own no hardware.
        pass


@pytest.fixture
def http(lab):
    class SilentHandler(server.Handler):
        def log_message(self, *args):
            pass
    SilentHandler.lab = lab
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), SilentHandler)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    worker.join(2)
    httpd.server_close()


def request(port, method, path, payload=None, raw=None):
    client = HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        data = raw if raw is not None else json.dumps(payload if payload is not None else {})
        client.request(method, path, body=data if method == 'POST' else None,
                       headers={'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'})
        response = client.getresponse()
        content = response.read().decode('utf-8-sig')
        return response.status, json.loads(content) if 'json' in response.getheader('Content-Type', '') else content
    finally:
        client.close()


def test_failed_save_can_retry_without_replacing_or_losing_session(lab, monkeypatch):
    lab.start(duration_seconds=15)
    lab.collector.on_sample(sample())
    ident = lab.session['id']
    writer = server.write_json
    def failed_write(*args):
        raise OSError('synthetic disk failure')
    with monkeypatch.context() as patch:
        patch.setattr(server, 'write_json', failed_write)
        with pytest.raises(OSError):
            lab.stop()
        status = lab.snapshot()
        assert status['status'] == 'save_error'
        assert status['pending_save'] and status['error']
        assert status['samples'][0]['rssi_dbm'] == -60
        with pytest.raises(ValueError, match='guardar'):
            lab.start(duration_seconds=15)
        assert lab.session['id'] == ident
        assert not list(lab.directory.glob('*.json'))
    assert server.write_json is writer
    final = lab.stop()
    assert final['pending_save'] is False and final['persistence']['status'] == 'saved'
    assert final['error'] is None
    assert final['session']['id'] == ident
    assert lab.saved(ident)['samples'] == final['samples']
    original = (lab.directory / f'{ident}.json').read_bytes()
    lab.stop()
    assert (lab.directory / f'{ident}.json').read_bytes() == original


def test_failed_http_stop_exposes_retry_state(http, lab, monkeypatch):
    lab.start(duration_seconds=15)
    lab.collector.on_sample(sample())
    with monkeypatch.context() as patch:
        def fail(*args):
            raise OSError('synthetic persistence failure')
        patch.setattr(server, 'write_json', fail)
        status, data = request(http, 'POST', '/api/stop')
        assert status == 503 and data['state']['pending_save'] is True
        assert data['state']['status'] == 'save_error'
    status, data = request(http, 'POST', '/api/stop')
    assert status == 200 and data['pending_save'] is False


def test_completed_snapshot_keeps_stop_time_and_diagnostics(lab):
    lab.start(duration_seconds=15)
    lab.collector.on_sample(sample())
    final = lab.stop()
    latest = lab.snapshot()
    disk = lab.saved(final['session']['id'])
    assert latest['session']['stopped_at'] == final['session']['stopped_at'] == disk['session']['stopped_at']
    assert latest['capture_diagnostics'] == disk['capture_diagnostics']


@pytest.mark.parametrize('invalid', ['{ broken', '{}', '[]', '{"session":{"id":"bad"},"samples":[]}'])
def test_invalid_catalog_does_not_start_hidden_capture_or_block_state(http, lab, invalid):
    broken = lab.directory / 'invalid.json'
    broken.write_text(invalid, encoding='utf-8')
    status, data = request(http, 'GET', '/api/state')
    assert status == 200 and data['catalog_errors']
    assert not lab.active
    status, data = request(http, 'POST', '/api/start', {'duration_seconds': 15})
    assert status == 200 and data['status'] == 'collecting' and lab.active
    assert data['catalog_errors'][0]['file'] == 'invalid.json'
    assert broken.read_text(encoding='utf-8') == invalid


def test_valid_catalog_survives_bad_neighbor_and_recomputes_legacy_replay(lab):
    lab.start(duration_seconds=15)
    for i in range(11):
        lab.collector.on_sample(sample(1000 + i * 1.5, -60 + math.sin(i)))
    ident = lab.stop()['session']['id']
    path = lab.directory / (ident + '.json')
    content = json.loads(path.read_text(encoding='utf-8'))
    content['classification'] = {'motion_level': 'present_still', 'confidence': 1.0}
    content['frames'] = [{'index': 0, 'classification': {'motion_level': 'present_still'}}]
    path.write_text(json.dumps(content), encoding='utf-8')
    original = path.read_bytes()
    (lab.directory / 'broken.json').write_text('[]', encoding='utf-8')
    fresh = server.Lab(lab.directory)
    state = fresh.snapshot()
    assert state['classification'] is None
    assert len(state['frames']) == 11
    assert state['catalog_errors'] and len(state['sessions']) == 1
    assert path.read_bytes() == original


def test_active_session_csv_and_json_resolve_current_id(http, lab):
    lab.start(duration_seconds=15)
    lab.collector.on_sample(sample())
    ident = lab.session['id']
    status, csv_text = request(http, 'GET', f'/api/export.csv?id={ident}')
    assert status == 200 and '1000.0,-60.0,0.8,unconfirmed' in csv_text
    assert not (lab.directory / f'{ident}.json').exists()
    status, state = request(http, 'GET', f'/api/session?id={ident}')
    assert status == 200 and len(state['samples']) == 1
    assert request(http, 'GET', '/api/export.csv?id=unknown')[0] == 404
    assert request(http, 'GET', '/api/export.csv?id=..%2Fsecret')[0] == 400


@pytest.mark.parametrize('raw', ['[]', 'null', '12', '"hello"', '{"duration_seconds":NaN}',
    '{"label":"one","label":"two"}', '{"label": []}', '{"ground_truth": []}',
    '{"duration_seconds":true}', '{"interface": 42}', '{"unexpected":1}', '{"label":""}'])
def test_bad_start_json_never_mutates_lab(http, lab, raw):
    status, _ = request(http, 'POST', '/api/start', raw=raw)
    assert status == 400
    assert not lab.active and lab.session is None


def test_stop_also_requires_valid_empty_object(http, lab):
    lab.start(duration_seconds=15)
    assert request(http, 'POST', '/api/stop', raw='[]')[0] == 400
    assert lab.active
    assert request(http, 'POST', '/api/stop', {'surprise': 1})[0] == 400
    assert lab.active


def test_explicit_interface_reaches_collector(http, lab):
    status, data = request(http, 'POST', '/api/start', {'interface': 'Wi-Fi 2'})
    assert status == 200
    assert lab.collector.selected_interface == 'Wi-Fi 2'
    assert data['session']['interface'] == 'Wi-Fi 2'


RENAMED = 'Nombre : Wi-Fi 2\nEstado : conectado\nSeñal : 80%\nRssi : -58\n'


def test_connected_renamed_interface_is_discovered_without_hardware(monkeypatch):
    monkeypatch.setattr(collector_module, 'read_netsh', lambda: RENAMED)
    instance = collector_module.VerifiedWindowsCollector()
    instance._validate_interface()
    assert instance.selected_interface == 'Wi-Fi 2'
    assert instance._read_sample().rssi_dbm == -58


def test_ambiguous_connected_interfaces_require_explicit_choice(monkeypatch):
    text = RENAMED + RENAMED.replace('Wi-Fi 2', 'Other Wi-Fi').replace('-58', '-90')
    monkeypatch.setattr(collector_module, 'read_netsh', lambda: text)
    with pytest.raises(ValueError, match='varias'):
        collector_module.VerifiedWindowsCollector()._validate_interface()
    explicit = collector_module.VerifiedWindowsCollector(interface='Other Wi-Fi')
    explicit._validate_interface()
    assert explicit._read_sample().rssi_dbm == -90


def test_disconnect_cannot_reuse_other_interface_reading(monkeypatch):
    text = RENAMED.replace('conectado', 'desconectado') + RENAMED.replace('Wi-Fi 2', 'Other Wi-Fi')
    monkeypatch.setattr(collector_module, 'read_netsh', lambda: text)
    explicit = collector_module.VerifiedWindowsCollector(interface='Wi-Fi 2')
    with pytest.raises(ValueError, match='conectada'):
        explicit._validate_interface()


@pytest.mark.parametrize('bad', [True, 3, float('nan'), '2'])
def test_invalid_collection_rates_are_rejected(bad):
    with pytest.raises(ValueError):
        collector_module.VerifiedWindowsCollector(sample_rate_hz=bad)


def test_netsh_errors_never_fabricate_or_reuse_samples(monkeypatch):
    instance = collector_module.VerifiedWindowsCollector(interface='Wi-Fi 2')
    emitted = []
    instance.on_sample = emitted.append
    def fail():
        instance._running = False
        raise RuntimeError('synthetic netsh failure')
    monkeypatch.setattr(instance, '_read_sample', fail)
    instance._running = True
    instance._sample_loop()
    assert emitted == [] and instance.get_samples() == []
    assert instance.error_count == 1 and instance.last_error == 'synthetic netsh failure'


@pytest.mark.parametrize('bad', [60., -121., 0., float('nan'), float('inf'), True])
def test_invalid_rssi_blocks_analysis_instead_of_being_dropped(bad):
    readings = [sample(1000 + i/2) for i in range(30)]
    readings[10] = replace(readings[10], rssi_dbm=bad)
    result = analysis.analyze(readings)
    assert result['classification'] is None and not result['quality']['ready']
    assert result['quality']['invalid_samples'] == 1
    assert result['features']['n_samples'] == 30


@pytest.mark.parametrize('row', [
    {'timestamp': 1, 'rssi_dbm': 60}, {'timestamp': float('nan'), 'rssi_dbm': -60},
    {'timestamp': 1, 'rssi_dbm': '-60'}, {'timestamp': True, 'rssi_dbm': -60},
    {'timestamp': 1, 'rssi_dbm': -60, 'quality': float('nan')},
    {'timestamp': 1, 'rssi_dbm': -60, 'quality': 80},
    {'timestamp': 1, 'rssi_dbm': -60, 'phase': []}, None,
])
def test_loaded_rows_are_strictly_validated(row):
    with pytest.raises(ValueError):
        analysis.from_rows([row])


def test_row_bounds_and_order_are_checked():
    row = {'timestamp': 1, 'rssi_dbm': -60, 'quality': None}
    assert math.isnan(analysis.from_rows([row])[0].link_quality)
    for invalid in ([row, row], [row] * 10_001, {'samples': []}):
        with pytest.raises(ValueError):
            analysis.from_rows(invalid)


def test_no_motion_bins_cannot_mean_still():
    readings = [sample(1000 + i*1.5, -60+3*math.sin(2*math.pi*.1*i*1.5)) for i in range(11)]
    result = analysis.analyze(readings)
    assert result['quality']['nyquist_hz'] == pytest.approx(1/3)
    assert result['quality']['motion_band']['bins'] == 0
    assert result['quality']['motion_band']['available'] is False
    assert result['features']['motion_band_power'] is None
    assert result['classification'] is None
    assert result['upstream_classification']['motion_level'] == 'present_still'


def test_only_one_motion_bin_is_explicitly_insufficient():
    result = analysis.analyze([sample(1000+i*.92) for i in range(17)])
    assert result['quality']['motion_band']['bins'] == 1
    assert result['quality']['motion_band']['minimum_bins'] == 2
    assert result['classification'] is None


def test_partial_motion_coverage_and_known_frequency_recovery():
    frequency = .7
    result = analysis.analyze([sample(1000+i/2, -60+4*math.sin(2*math.pi*frequency*i/2)) for i in range(30)])
    band = result['quality']['motion_band']
    assert result['quality']['ready']
    assert band['configured_hz'] == [.5, 3]
    assert band['coverage'] == 'partial' and band['bins'] >= 2
    assert .5 <= band['observed_hz'][0] <= band['observed_hz'][1] <= 1
    peak = max(result['spectrum'], key=lambda x: x['power'])['hz']
    assert abs(peak-frequency) <= 2/30
    assert result['classification']['motion_level'] == 'active'


@pytest.mark.parametrize('jitter', [.01, .04])
def test_small_controlled_jitter_preserves_frequency_within_one_bin(jitter):
    stamps = [1000+i/2 + (jitter if i % 2 else 0) for i in range(30)]
    result = analysis.analyze([sample(t, -60+3*math.sin(2*math.pi*.7*(t-1000))) for t in stamps])
    if jitter == .01:
        assert result['quality']['ready']
        peak = max(result['spectrum'], key=lambda x: x['power'])['hz']
        assert abs(peak-.7) <= .07
    else:
        assert not result['quality']['ready']
        assert result['spectrum'] == [] and result['features']['motion_band_power'] is None


def test_single_large_interval_deviation_abstains_even_with_low_cv():
    stamps = [1000+i/2 for i in range(30)]
    stamps[-1] += .09
    result = analysis.analyze([sample(t) for t in stamps])
    assert result['quality']['jitter_cv'] < .05
    assert result['quality']['max_interval_deviation'] > .15
    assert result['classification'] is None and result['spectrum'] == []


def test_comparison_route_returns_object_and_uses_lab_directory(http, lab, monkeypatch):
    module = types.ModuleType('swarm_signal.experiment')
    paths = []
    def comparison(directory):
        paths.append(directory)
        return {'status': 'synthetic_test_only', 'groups': []}
    module.build_comparison = comparison
    monkeypatch.setitem(sys.modules, 'swarm_signal.experiment', module)
    status, data = request(http, 'GET', '/api/comparison')
    assert status == 200 and data == {'status': 'synthetic_test_only', 'groups': []}
    assert paths == [lab.directory]


def test_collect_once_auto_selects_without_prior_start(monkeypatch):
    monkeypatch.setattr(collector_module, 'read_netsh', lambda: RENAMED)
    reading = collector_module.VerifiedWindowsCollector().collect_once()
    assert reading.interface == 'Wi-Fi 2' and reading.rssi_dbm == -58


def test_capture_cli_writes_verified_recovery_on_persistent_save_failure(lab, monkeypatch, tmp_path):
    from scripts.capture import finish_capture
    lab.start(duration_seconds=15)
    lab.collector.on_sample(sample())
    ident = lab.session['id']
    with monkeypatch.context() as patch:
        def fail(*args):
            raise OSError('synthetic disk failure')
        patch.setattr(server, 'write_json', fail)
        result = finish_capture(lab, tmp_path / 'alternate-disk-fixture')
        assert result['status'] == 'recovery'
        path = Path(result['path'])
        recovered = server.load_session(path)
        assert recovered['session']['id'] == ident
        assert recovered['samples'] == lab.rows
        assert recovered['recovery']['requires_import']
        assert not (lab.directory / f'{ident}.json').exists()


def test_capture_cli_never_announces_missing_file(lab, monkeypatch, tmp_path, capsys):
    import scripts.capture as capture
    lab.start(duration_seconds=15)
    lab.collector.on_sample(sample())
    def fail(*args):
        raise OSError('synthetic all disks unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(server, 'write_json', fail)
        patch.setattr(capture, 'write_json', fail)
        with pytest.raises(RuntimeError, match='No se guardó ningún archivo'):
            capture.finish_capture(lab, tmp_path / 'alternate-disk-fixture')
        console = capsys.readouterr()
        recovery = json.loads(console.out)
        assert recovery['samples'] == lab.rows
        assert 'Evidencia verificada' not in console.out


def test_replay_cache_uses_bytes_not_only_file_timestamp_and_size(lab):
    lab.start(duration_seconds=15)
    for i in range(30):
        lab.collector.on_sample(sample(1000+i/2))
    ident = lab.stop()['session']['id']
    path = lab.directory / (ident + '.json')
    fresh = server.Lab(lab.directory)
    first = fresh.resolve(ident)
    stamp = path.stat()
    raw = path.read_bytes()
    assert b'-60.0' in raw
    path.write_bytes(raw.replace(b'-60.0', b'-70.0'))
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    second = fresh.resolve(ident)
    assert path.stat().st_size == stamp.st_size
    assert first['features']['mean'] == -60 and second['features']['mean'] == -70
    assert first['replay_source']['sha256'] != second['replay_source']['sha256']
    assert second['analysis_policy_version'] == '2.0-quality-audit'


def test_extreme_tiny_timestamp_intervals_abstain_without_nonfinite_output():
    result = analysis.analyze([sample(i * 1e-310) for i in range(4)])
    assert result['classification'] is None
    assert result['quality']['reason']
    json.dumps(result, allow_nan=False)


def test_failed_start_cleanup_remains_retryable(lab, monkeypatch):
    class FailingStart(FakeCollector):
        def start(self):
            raise RuntimeError('synthetic startup failure')
        def stop(self):
            self.stops += 1
            if self.stops == 1:
                raise RuntimeError('synthetic delayed shutdown')
    monkeypatch.setattr(server, 'VerifiedWindowsCollector', FailingStart)
    with pytest.raises(ValueError):
        lab.start(duration_seconds=15)
    assert lab.pending_save and not lab.active and not lab.stopping
    with pytest.raises(ValueError, match='guardar'):
        lab.start(duration_seconds=15)
    state = lab.stop()
    assert not state['pending_save']
    assert state['capture_diagnostics'] is not None
