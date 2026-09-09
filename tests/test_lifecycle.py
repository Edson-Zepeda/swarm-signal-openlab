"""Synthetic lifecycle/security regressions. These tests never call netsh.

Fake collectors emit explicitly artificial values; local HTTP requests target
only an ephemeral test server backed by a temporary evidence directory.
"""
from __future__ import annotations

from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import swarm_signal.server as server
from swarm_signal.analysis import analyze
from swarm_signal.collector import decode_netsh, parse_netsh, redact_netsh
from v1.src.sensing.rssi_collector import WifiSample


def artificial_sample(timestamp=1000.0, rssi=-60.0):
    return WifiSample(timestamp, rssi, float('nan'), .8, 0, 0, 0, 'synthetic-test')


class ManualTimer:
    """No wall-clock timer: tests explicitly invoke callbacks, even stale ones."""
    def __init__(self, duration, function):
        self.duration = duration
        self.function = function
        self.daemon = False
        self.cancelled = False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True


class ArtificialCollector:
    def __init__(self, on_sample):
        self.on_sample = on_sample
        self.last_error = None
        self.error_count = 0
        self.latencies = [.012, .018]
        self.stop_entered = threading.Event()
        self.stop_release = threading.Event()
        self.block_stop = False

    def start(self):
        pass

    def stop(self):
        self.stop_entered.set()
        if self.block_stop:
            assert self.stop_release.wait(3), 'Test did not release artificial collector'


@pytest.fixture
def lab(monkeypatch, tmp_path):
    monkeypatch.setattr(server, 'VerifiedWindowsCollector', ArtificialCollector)
    monkeypatch.setattr(server.threading, 'Timer', ManualTimer)
    instance = server.Lab(tmp_path)
    yield instance
    if instance.collector:
        instance.collector.stop_release.set()
    instance.stop()


def test_start_cannot_replace_session_while_stop_is_joining(lab):
    lab.start(label='synthetic-first', duration_seconds=15)
    first_id = lab.session['id']
    collector = lab.collector
    collector.on_sample(artificial_sample())
    collector.block_stop = True
    errors = []

    def finish():
        try:
            lab.stop()
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=finish, daemon=True)
    worker.start()
    try:
        assert collector.stop_entered.wait(1)
        with pytest.raises(ValueError):
            lab.start(label='synthetic-second', duration_seconds=15)
        # A sample completing after stop began must not enter the saved run.
        collector.on_sample(artificial_sample(1000.5, -70))
        assert lab.session['id'] == first_id
    finally:
        collector.stop_release.set()
        worker.join(3)
    assert not worker.is_alive()
    assert not errors
    saved = lab.saved(first_id)
    assert saved['session']['label'] == 'synthetic-first'
    assert len(saved['samples']) == 1
    assert saved['samples'][0]['rssi_dbm'] == -60
    assert len(list(lab.directory.glob('*.json'))) == 1


def test_old_timer_and_old_collector_cannot_modify_next_session(lab):
    lab.start(label='synthetic-first', duration_seconds=15)
    old_id, old_timer, old_collector = lab.session['id'], lab.timer, lab.collector
    lab.stop()
    lab.start(label='synthetic-second', duration_seconds=15)
    new_id = lab.session['id']
    old_timer.function()
    old_collector.on_sample(artificial_sample())
    assert new_id != old_id
    assert lab.active
    assert lab.session['id'] == new_id
    assert lab.rows == []
    assert not (lab.directory / f'{new_id}.json').exists()


def test_completed_replay_cannot_change_from_a_late_callback(lab):
    lab.start(label='synthetic-fixed-record', duration_seconds=15)
    collector = lab.collector
    collector.on_sample(artificial_sample())
    final = lab.stop()
    collector.on_sample(artificial_sample(1000.5, -80))
    assert lab.rows == final['samples']
    assert lab.snapshot()['samples'] == lab.saved(final['session']['id'])['samples']


def test_stopping_twice_preserves_original_saved_evidence(lab):
    lab.start(label='synthetic-once', duration_seconds=15)
    lab.collector.on_sample(artificial_sample())
    final = lab.stop()
    path = lab.directory / (final['session']['id'] + '.json')
    original_bytes = path.read_bytes()
    lab.stop()
    assert path.read_bytes() == original_bytes
    assert final['capture_diagnostics']['raw_rssi_only'] is True
    assert final['session']['ground_truth_source'] == 'not_observed'


@pytest.mark.parametrize('timestamps', [
    [0, .5, 1, 1.5],
    [0, .5, 1, 14.5],
    [0, .2, 1.2, 1.4, 2.4, 2.6, 3.6, 3.8, 4.8, 5, 6, 6.2,
     7.2, 7.4, 8.4, 8.6, 9.6, 9.8, 10.8, 11, 12, 12.2, 13.2, 13.4, 14.4],
])
def test_incomplete_or_gapped_capture_has_no_presence_verdict(timestamps):
    result = analyze([artificial_sample(t) for t in timestamps])
    assert result['classification'] is None
    assert result['quality']['ready'] is False
    assert result['quality']['reason']


def test_valid_regular_window_still_uses_original_classifier():
    result = analyze([artificial_sample(i / 2) for i in range(30)])
    assert result['quality']['ready'] is True
    assert result['classification']['motion_level'] == 'absent'
    assert result['features']['n_samples'] == 30


def test_utf8_spanish_output_keeps_measured_quality():
    fixture = 'Nombre : Wi-Fi\nEstado : conectado\nSeñal : 84%\nRssi : -58\n'
    decoded = decode_netsh(fixture.encode('utf-8'))
    assert decoded == fixture
    assert parse_netsh(decoded).quality == .84


def test_identifiers_are_redacted_even_when_field_name_is_corrupted():
    # Both identifiers are invented fixtures, not values from this computer.
    fixture = ('Direcci├│n : aa:bb:cc:dd:ee:ff\n'
               'Unknown field : 12345678-1234-1234-1234-123456789abc\nRssi : -58')
    cleaned = redact_netsh(fixture)
    assert 'aa:bb:cc:dd:ee:ff' not in cleaned
    assert '12345678-1234-1234-1234-123456789abc' not in cleaned
    assert 'Rssi : -58' in cleaned


@pytest.fixture
def local_http(lab):
    class TestHandler(server.Handler):
        def log_message(self, *args):
            pass

    TestHandler.lab = lab
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), TestHandler)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    worker.join(2)
    httpd.server_close()


def request(port, method, path, headers):
    connection = HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        connection.request(method, path, body='{}' if method == 'POST' else None,
                           headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_rebinding_host_cannot_read_local_evidence(local_http):
    status, payload = request(local_http, 'GET', '/api/state',
                              {'Host': f'attacker.invalid:{local_http}'})
    assert status == 403
    assert 'samples' not in payload


def test_cross_origin_page_cannot_start_wifi_capture(local_http, lab):
    status, _ = request(local_http, 'POST', '/api/start', {
        'Host': f'127.0.0.1:{local_http}', 'Origin': 'https://attacker.invalid',
        'Content-Type': 'application/json',
    })
    assert status == 403
    assert lab.session is None


def test_local_origin_can_start_and_stop_artificial_capture(local_http, lab):
    origin = f'http://127.0.0.1:{local_http}'
    headers = {'Host': f'127.0.0.1:{local_http}', 'Origin': origin,
               'Content-Type': 'application/json'}
    status, state = request(local_http, 'POST', '/api/start', headers)
    assert status == 200 and state['status'] == 'collecting'
    assert lab.active
    status, state = request(local_http, 'POST', '/api/stop', headers)
    assert status == 200 and not lab.active
    assert lab.saved(state['session']['id'])['samples'] == []
