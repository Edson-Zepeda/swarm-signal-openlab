"""Package committed files and verify the ZIP and standalone deliverables."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm_signal.evidence import build_evidence

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main() -> None:
    if git("status", "--porcelain").strip():
        raise SystemExit("Commit all project changes before packaging.")
    commit = git("rev-parse", "HEAD").decode().strip()
    config = json.loads((ROOT/'project.json').read_text(encoding='utf-8'))
    version = config['version']
    state = build_evidence(ROOT)
    DEST = ROOT.parent / ('Entrega_SwarmSignal_v' + version)
    DEST.mkdir(parents=True, exist_ok=True)
    archive = DEST / "SwarmSignal_Proyecto.zip"
    manifest = {"commit": commit, "version": version, "files": [],
                "physical_movement": "confirmed_by_operator" if state['physical_evidence_complete'] else "pending",
                "skybrush_assigned_repository": "pending", "advanced_required_for_base": False}
    original = zipfile.ZipFile(io.BytesIO(git("archive", "--format=zip", "--prefix=SwarmSignal/", "HEAD")))
    with original, zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for item in original.infolist():
            data = original.read(item.filename)
            target.writestr(item, data)
            if not item.is_dir():
                manifest["files"].append({"path": item.filename, "bytes": len(data),
                                          "sha256": hashlib.sha256(data).hexdigest()})
        target.writestr("SwarmSignal/MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    with zipfile.ZipFile(archive) as verified:
        assert verified.testzip() is None
        for item in manifest["files"]:
            assert hashlib.sha256(verified.read(item["path"])).hexdigest() == item["sha256"]
    copied = []
    for relative in ["docs/SwarmSignal_Informe.pdf", "docs/SwarmSignal_Propuesta.pdf", "docs/SwarmSignal_Auditoria.pdf",
                     "media/SwarmSignal_Demo.mp4", "media/SwarmSignal_Demo.vtt",
                     "media/SwarmSignal_Demo.srt"]:
        source = ROOT / relative
        destination = DEST / source.name
        shutil.copyfile(source, destination)
        copied.append(destination)
        assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(destination.read_bytes()).digest()
    (DEST / "LEEME.txt").write_text(
        "SWARM / SIGNAL\n\n"
        "Laboratorio: https://edson-zepeda.github.io/swarm-signal-openlab/\n"
        "Video: https://edson-zepeda.github.io/swarm-signal-openlab/demo.html\n"
        "Codigo: https://github.com/Edson-Zepeda/swarm-signal-openlab\n\n"
        "El ZIP incluye codigo, datos, evidencias, informes y video.\n"
        "Para medir WiFi: extrae el ZIP y abre Iniciar.cmd en Windows con Python 3.10+.\n"
        "La web publica reproduce datos guardados.\n\n"
        + ("Movimiento confirmado por el participante.\n" if state['physical_evidence_complete'] else
           "Pendiente: confirmar movimiento fisico del participante.\n") +
        "Opcional Skybrush: requiere el repositorio asignado y tutorial del show.\n"
        f"Verificacion actual: {state['verification']['passed']} PASS, {state['verification']['failed']} FAIL, {state['verification']['skipped']} SKIP. Fallo inicial conservado.\n"
        f"Revision: {commit}\n", encoding="utf-8")
    files = sorted([archive, DEST/'LEEME.txt', *copied])
    expected = {p.name for p in files} | {'SHA256SUMS.txt'}
    extras = [p.name for p in DEST.iterdir() if p.name not in expected]
    if extras:
        raise RuntimeError(f'La carpeta de entrega contiene archivos ajenos: {extras}')
    (DEST / "SHA256SUMS.txt").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files), encoding="utf-8")
    print(json.dumps({"commit": commit, "archive": str(archive), "files": len(manifest["files"]),
                      "bytes": archive.stat().st_size, "zip_integrity": "PASS"}, indent=2))


if __name__ == "__main__":
    main()
