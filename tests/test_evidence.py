"""Negative evidence and export checks. All created recordings are synthetic fixtures."""
import hashlib
import json
from pathlib import Path
import pytest
from swarm_signal.evidence import build_evidence, reference_recording, test_counts as junit_counts
from swarm_signal.experiment import describe_session


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def fixture(rows):
    return {'session': {'id':'fixture', 'label':'Synthetic test only', 'ground_truth':'walking',
                        'ground_truth_source':'operator_label'},
            'samples':[{'timestamp':1000+t, 'rssi_dbm':v, 'quality':None, 'phase':'walking'} for t,v in rows]}


def config_fixture(root, *, kind='recorded_real_wifi'):
    path=root/'evidence/sessions/fixture.json'
    data=fixture([(i/2,-60) for i in range(30)])
    write(path,data)
    write(root/'project.json', {'reference_session':'fixture', 'recordings':[
        {'id':'fixture','source':'evidence/sessions/fixture.json','kind':kind,
         'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'ground_truth':'walking'}]})
    return path


def test_empty_delivery_never_credits_absent_evidence(tmp_path):
    result=build_evidence(tmp_path)
    assert result['completed']==0
    assert all(s['status']=='pending' and s['artifact_url'] is None for s in result['stages'])


def test_screenshot_alone_does_not_confirm_physical_movement(tmp_path):
    p=tmp_path/'evidence/ui/monitor-live.png';p.parent.mkdir(parents=True);p.write_bytes(b'SYNTHETIC IMAGE STUB')
    result=build_evidence(tmp_path)
    assert result['stages'][4]['status']=='partial'
    assert not result['physical_evidence_complete']


def test_failed_or_skipped_tests_are_not_counted_as_passed(tmp_path):
    path=tmp_path/'suite.xml'
    path.write_text('<testsuite><testcase/><testcase><failure/></testcase><testcase><skipped/></testcase></testsuite>')
    assert junit_counts(path)=={'total':3,'passed':1,'failed':1,'skipped':1}


def test_explicit_reference_preserves_operator_condition_and_ignores_larger_file(tmp_path):
    config_fixture(tmp_path)
    write(tmp_path/'evidence/sessions/large.json',fixture([(i/2,-55) for i in range(100)]))
    result, reference, _=reference_recording(tmp_path)
    assert reference['id']=='fixture' and len(result['samples'])==30
    assert result['session']['ground_truth']=='walking'


def test_tampered_recording_is_rejected(tmp_path):
    path=config_fixture(tmp_path)
    path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='SHA-256'):
        reference_recording(tmp_path)


def test_synthetic_source_cannot_be_exported_as_real_wifi(tmp_path):
    config_fixture(tmp_path,kind='synthetic')
    with pytest.raises(ValueError,match='real'):
        reference_recording(tmp_path)


def test_disjoint_windows_keep_every_boundary_sample_exactly_once():
    data=fixture([(i/2,-60+i%2) for i in range(61)])
    report=describe_session(data,source='SYNTHETIC')
    assert [w['count'] for w in report['windows']]==[30,30,1]
    assert sum(w['count'] for w in report['windows'])==61
    assert report['windows_eligible']==2


def test_missing_intervals_remain_in_quality_denominator():
    data=fixture([(i/2,-60) for i in range(30)]+[(i/2,-60) for i in range(60,91)])
    report=describe_session(data,source='SYNTHETIC')
    assert report['windows'][1]['count']==0
    assert report['windows'][1]['eligible'] and not report['windows'][1]['ready']
    assert report['windows_eligible']==3
    assert report['valid_fraction']==pytest.approx(2/3)


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),60,True])
def test_comparison_rejects_invalid_rssi_without_silently_dropping_it(bad):
    data=fixture([(i/2,-60) for i in range(30)])
    data['samples'][4]['rssi_dbm']=bad
    with pytest.raises(ValueError):
        describe_session(data,source='SYNTHETIC')


def test_zero_eligible_windows_produce_no_percent():
    report=describe_session(fixture([(0,-60),(0.5,-60)]),source='SYNTHETIC')
    assert report['windows_eligible']==0 and report['valid_fraction'] is None
