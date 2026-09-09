"""Capture direct RSSI; verify the saved file or retain a recovery copy."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import json
import tempfile
import time
from swarm_signal.server import Lab, load_session, write_json


def finish_capture(lab, recovery_dir=None):
    """Retry persistence once; if needed save the intact snapshot separately."""
    failure = None
    for _ in range(2):
        try:
            lab.stop()
            # An automatic timer may already be joining the collector.
            while lab.stopping:
                time.sleep(.1)
            if lab.pending_save:
                raise OSError(lab.persistence_error or 'La captura sigue pendiente de guardar.')
            if not lab.session or 'stopped_at' not in lab.session:
                return {'status': 'not_started', 'path': None}
            path = lab.directory / (lab.session['id'] + '.json')
            saved = load_session(path)
            if saved['samples'] != lab.rows:
                raise OSError('El archivo no coincide con la captura en memoria.')
            return {'status': 'saved', 'path': str(path)}
        except (OSError, RuntimeError, ValueError) as exc:
            failure = str(exc)
    snapshot = lab.snapshot()
    if not snapshot.get('session'):
        raise RuntimeError(failure)
    snapshot['recovery'] = {'reason': failure, 'original_directory': str(lab.directory),
                            'requires_import': True}
    target = Path(recovery_dir) if recovery_dir else Path(tempfile.gettempdir()) / 'SwarmSignal-recovery'
    path = target / (snapshot['session']['id'] + '.json')
    try:
        write_json(path, snapshot)
        if load_session(path)['samples'] != snapshot['samples']:
            raise OSError('La copia de recuperación no coincide.')
    except (OSError, RuntimeError, ValueError) as exc:
        # Last resort: retain the complete snapshot in redirected console output.
        print('No se pudo escribir la recuperación. Conserva este JSON:', file=sys.stderr, flush=True)
        print(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), flush=True)
        raise RuntimeError(f'No se guardó ningún archivo: {exc}') from exc
    return {'status': 'recovery', 'path': str(path), 'error': failure}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Mide RSSI directo. No genera datos simulados.')
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--label', default='Observación ambiental')
    parser.add_argument('--condition', choices=['unconfirmed', 'still', 'walking'], default='unconfirmed')
    parser.add_argument('--interface', help='Interfaz exacta si hay varias conectadas.')
    parser.add_argument('--recovery-dir', help='Carpeta alternativa para recuperar un guardado fallido.')
    args = parser.parse_args(argv)
    lab = Lab(interface=args.interface)
    try:
        lab.start(args.label, args.seconds, args.condition)
        print('Capturando. Condición declarada:', args.condition, flush=True)
        while lab.active:
            time.sleep(3)
            state = lab.snapshot()
            classification, features = state.get('classification') or {}, state.get('features') or {}
            print(json.dumps({'samples': len(state['samples']), 'rssi_mean_dbm': features.get('mean'),
                              'variance': features.get('variance'), 'class': classification.get('motion_level'),
                              'quality': state.get('quality')}, ensure_ascii=False), flush=True)
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'Error de captura: {exc}', file=sys.stderr, flush=True)
        if not lab.active and not lab.pending_save:
            return 2
    try:
        result = finish_capture(lab, args.recovery_dir)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return 2
    if result['status'] == 'saved':
        print('Evidencia verificada:', result['path'], flush=True)
        return 0
    if result['status'] == 'recovery':
        print('Captura conservada para recuperación:', result['path'], flush=True)
        print('El guardado original falló:', result['error'], file=sys.stderr, flush=True)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
