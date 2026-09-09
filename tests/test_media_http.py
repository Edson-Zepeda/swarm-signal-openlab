"""Media byte-range regressions. Tiny artificial files; no Wi-Fi or capture."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import threading

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import swarm_signal.server as server

DATA = bytes(range(256)) * 600  # Crosses the server's64KiB read boundary.


@pytest.fixture
def media_server(tmp_path, monkeypatch):
    directory = tmp_path / 'web' / 'media'
    directory.mkdir(parents=True)
    (directory / 'fixture.mp4').write_bytes(DATA)
    (directory / 'empty.mp4').write_bytes(b'')
    monkeypatch.setattr(server, 'ROOT', tmp_path)
    class QuietHandler(server.Handler):
        def log_message(self, *args):
            pass
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    thread.join(2)
    httpd.server_close()


def fetch(port, *, method='GET', path='/media/fixture.mp4', headers=None):
    connection = HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_full_media_get_advertises_seeking_and_exact_body(media_server):
    status, headers, body = fetch(media_server)
    assert status == 200 and body == DATA
    assert headers['Content-Type'] == 'video/mp4'
    assert headers['Content-Length'] == str(len(DATA))
    assert headers['Accept-Ranges'] == 'bytes'
    assert 'Content-Range' not in headers


@pytest.mark.parametrize('range_header,start,end', [
    ('bytes=0-1', 0, 1),
    ('bytes=65530-65550', 65530, 65550),
    ('bytes=153500-', 153500, len(DATA)-1),
    ('bytes=-73', len(DATA)-73, len(DATA)-1),
    ('bytes=153590-999999', 153590, len(DATA)-1),
    ('bytes=-999999', 0, len(DATA)-1),
])
def test_single_range_returns_only_the_requested_bytes(media_server, range_header, start, end):
    status, headers, body = fetch(media_server, headers={'Range': range_header})
    assert status == 206
    assert headers['Content-Range'] == f'bytes {start}-{end}/{len(DATA)}'
    assert headers['Content-Length'] == str(end-start+1)
    assert headers['Content-Type'] == 'video/mp4'
    assert headers['Accept-Ranges'] == 'bytes'
    assert body == DATA[start:end+1]


@pytest.mark.parametrize('range_header', [f'bytes={len(DATA)}-', 'bytes=9-8', 'bytes=-0', 'bytes='+'9'*4500+'-'])
def test_unsatisfiable_range_returns_416_without_body(media_server, range_header):
    status, headers, body = fetch(media_server, headers={'Range': range_header})
    assert status == 416 and body == b''
    assert headers['Content-Range'] == f'bytes */{len(DATA)}'
    assert headers['Content-Length'] == '0'


def test_empty_media_range_is_unsatisfiable(media_server):
    status, headers, body = fetch(media_server, path='/media/empty.mp4', headers={'Range': 'bytes=0-'})
    assert status == 416 and headers['Content-Range'] == 'bytes */0' and body == b''


@pytest.mark.parametrize('range_header', [None, 'bytes=0-1'])
def test_head_describes_full_representation_without_sending_body(media_server, range_header):
    status, headers, body = fetch(media_server, method='HEAD', headers={'Range': range_header} if range_header else {})
    assert status == 200 and body == b''
    assert headers['Content-Length'] == str(len(DATA))
    assert headers['Content-Type'] == 'video/mp4'
    assert headers['Accept-Ranges'] == 'bytes'
    assert 'Content-Range' not in headers


def test_stale_if_range_falls_back_to_complete_media(media_server):
    status, headers, body = fetch(media_server, headers={'Range': 'bytes=0-1', 'If-Range': 'Wed, 01 Jan 1997 00:00:00 GMT'})
    assert status == 200 and body == DATA and 'Content-Range' not in headers
    _, initial, _ = fetch(media_server, method='HEAD')
    status, headers, body = fetch(media_server, headers={'Range': 'bytes=0-1', 'If-Range': initial['Last-Modified']})
    assert status == 206 and body == DATA[:2]


def test_unsupported_multi_range_and_malformed_range_fall_back_safely(media_server):
    for header in ('bytes=0-1,10-11', 'items=0-1', 'bytes=bad-data'):
        status, headers, body = fetch(media_server, headers={'Range': header})
        assert status == 200 and body == DATA and 'Content-Range' not in headers


def test_head_also_rejects_rebinding_host(media_server):
    status, _, body = fetch(media_server, method='HEAD', headers={'Host': 'untrusted.invalid'})
    assert status == 403 and body == b''
