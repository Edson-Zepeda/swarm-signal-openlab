"""Verify the delivery's measured sources, calculations and matching public assets."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_signal.analysis import analyze, from_rows
from swarm_signal.evidence import build_evidence, reference_recording
from swarm_signal.experiment import build_comparison


def read(relative):
    def reject(value):
        raise ValueError(f'Nonfinite JSON value: {value}')
    return json.loads((ROOT / relative).read_text(encoding='utf-8'), parse_constant=reject)


def sha(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def main():
    checks = []
    def check(name, condition, detail=None):
        checks.append({'name': name, 'status': 'PASS' if condition else 'FAIL', 'detail': detail})

    raw, reference, config = reference_recording(ROOT)
    for recording in config['recordings']:
        check('original_recording:' + recording['id'], sha(recording['source']) == recording['sha256'])
    session = read('web/data/session.json')
    check('public_rows_are_original', session['samples'] == raw['samples'])
    check('public_source_hash', session['provenance']['source_sha256'] == reference['sha256'])
    samples = from_rows(raw['samples'])
    frames = [{'index': i, **analyze(samples[:i+1])} for i in range(len(samples))]
    check('every_replay_frame_recomputed', session['frames'] == frames, len(frames))
    final_analysis = analyze(samples)
    check('final_analysis_current', all(session[k] == value for k, value in final_analysis.items()))
    public = read('web/data/evidence.json')
    expected = build_evidence(ROOT)
    # A public code link is added at export time; the measured evidence remains identical.
    expected['stages'][5]['artifact_links'] = [{'label': 'Código de integración', 'url': 'code/check_backend.py'}]
    check('evidence_status_derived', public == expected)
    comparison = read('web/data/comparison.json')
    check('comparison_recomputed', comparison == build_comparison())
    check('physical_confirmation_not_invented', not public['physical_evidence_complete'] and
          all(r['ground_truth'] == 'unconfirmed' for r in comparison['sessions']))
    for stage in public['stages']:
        paths = [stage['artifact_url'], *[link['url'] for link in stage['artifact_links']]]
        for path in set(paths):
            check('artifact_exists:' + path, (ROOT/'web'/path).is_file())

    for item in read('evidence/revision/pdf_qa.json'):
        relative = 'docs/' + item['file']
        check('reviewed_pdf:' + item['file'], sha(relative) == item['sha256'])
        check('public_pdf:' + item['file'], sha(relative) == sha('web/' + relative))
    video = read('media/video_verification.json')
    check('video_reviewed_file', sha(video['output']) == video['sha256'])
    check('video_format', video['width'] == 1920 and video['height'] == 1080 and
          video['duration_seconds'] <= 120 and video['audio_present'] and video['subtitles_present'])
    check('video_visual_review', video.get('visual_review_status') == 'PASS')
    video_audit = read('media/video/provenance_audit.json')
    check('video_builder_preserved', sha('scripts/build_video.py') == video_audit['build_script_sha256'])
    for name in ('SwarmSignal_Demo.mp4', 'SwarmSignal_Demo.vtt', 'SwarmSignal_Demo.srt', 'SwarmSignal_Poster.jpg'):
        check('public_media:' + name, sha('media/' + name) == sha('web/media/' + name))
    for source in read('media/video/timeline.json')['source_provenance']:
        check('video_source:' + source['path'], sha(source['path']) == source['sha256'] and
              sha(source.get('snapshot_path', source['path'])) == source['sha256'])
    install = read('evidence/revision/installation.json')
    check('tested_bootstrap', sha('Iniciar.ps1') == install['bootstrap_sha256'])
    check('tested_requirements', sha('requirements.txt') == install['requirements_sha256'])
    regression = read('evidence/revision/regression_verification.json')
    check('test_report_matches_sources', sha(regression['test_report']) == regression['test_report_sha256'])
    for source, digest in regression['tested_sources'].items():
        check('tested_core:' + source, sha(source) == digest)
    result = {'at': datetime.now(timezone.utc).isoformat(), 'version': config['version'],
              'status': 'PASS' if all(c['status'] == 'PASS' for c in checks) else 'FAIL',
              'checks': checks, 'scope': 'Artifact consistency. Does not validate human presence or skipped upstream phases.'}
    path = ROOT/'evidence/revision/delivery_checks.json'
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'checks': len(checks),
                      'failed': [c for c in checks if c['status'] != 'PASS']}, ensure_ascii=False))
    if result['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
