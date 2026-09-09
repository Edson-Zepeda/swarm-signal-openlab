"""Tests with explicitly synthetic parser fixtures; no hardware claims."""
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from swarm_signal.collector import parse_netsh, redact_netsh
from swarm_signal.analysis import analyze
from v1.src.sensing.rssi_collector import WifiSample

ES = '''Nombre : Wi-Fi
Estado : conectado
SSID : private-network
AP BSSID : aa:bb:cc:dd:ee:ff
Señal : 86%
Rssi : -57
'''
EN = '''Name : Wi-Fi
State : connected
Signal : 72%
Rssi : -64 dBm
'''

@pytest.mark.parametrize('text,rssi,q', [(ES,-57,.86),(EN,-64,.72)])
def test_spanish_english_direct_measurement(text,rssi,q):
    reading = parse_netsh(text)
    assert (reading.rssi_dbm, reading.quality) == (rssi,q)

@pytest.mark.parametrize('bad', [ES.replace('Rssi : -57',''), ES.replace('-57','nan'),
    ES.replace('-57','0'), ES.replace('conectado','desconectado'),
    ES.replace('86%','180%'), ES.replace('Wi-Fi','Wi-Fi 2')])
def test_invalid_reading_is_rejected_not_fabricated(bad):
    with pytest.raises(ValueError):
        parse_netsh(bad)

def test_selected_interface_only():
    assert parse_netsh(EN + '\n' + ES.replace('Wi-Fi','Wi-Fi 2').replace('-57','-90')).rssi_dbm == -64

def test_missing_quality_not_reported_as_zero():
    assert parse_netsh(ES.replace('Señal : 86%','')).quality is None

def test_redaction_retains_reading_without_identifiers():
    result = redact_netsh(ES)
    assert 'private-network' not in result and 'aa:bb' not in result
    assert 'Rssi : -57' in result

def samples(values):
    return [WifiSample(1000+i/2, value, float('nan'), .86, 0,0,0,'fixture') for i,value in enumerate(values)]

@pytest.mark.parametrize('n',[0,1,2,3])
def test_insufficient_data_never_means_absence(n):
    result = analyze(samples([-60]*n))
    assert result['classification'] is None and not result['quality']['ready']

def test_constant_valid_signal_preserves_upstream_class_not_human_truth():
    result = analyze(samples([-60]*30))
    assert result['classification']['motion_level'] == 'absent'
    assert result['features']['variance'] == 0
    assert result['capabilities'] == ['MOTION','PRESENCE']

def test_spectrum_does_not_exceed_nyquist():
    result = analyze(samples([-60+4*math.sin(2*math.pi*.7*i/2) for i in range(30)]))
    assert max(p['hz'] for p in result['spectrum']) <= 1
    assert result['classification']['motion_level'] == 'active'

def test_duplicate_timestamps_rejected():
    s = samples([-60]*4)
    s[1] = s[0]
    assert analyze(s)['classification'] is None
