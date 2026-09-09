"""Package committed files and verify the ZIP and standalone deliverables."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parent / "Entrega_SwarmSignal"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main() -> None:
    if git("status", "--porcelain").strip():
        raise SystemExit("Commit all project changes before packaging.")
    commit = git("rev-parse", "HEAD").decode().strip()
    DEST.mkdir(parents=True, exist_ok=True)
    archive = DEST / "SwarmSignal_Proyecto.zip"
    manifest = {"commit": commit, "files": [], "physical_movement": "pending",
                "skybrush_assigned_repository": "pending"}
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
    for relative in ["docs/SwarmSignal_Informe.pdf", "docs/SwarmSignal_Propuesta.pdf",
                     "media/SwarmSignal_Demo.mp4", "media/SwarmSignal_Demo.vtt",
                     "media/SwarmSignal_Demo.srt"]:
        source = ROOT / relative
        destination = DEST / source.name
        shutil.copyfile(source, destination)
        assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(destination.read_bytes()).digest()
    (DEST / "LEEME.txt").write_text(
        "SWARM / SIGNAL\n\n"
        "Laboratorio: https://edson-zepeda.github.io/swarm-signal-openlab/\n"
        "Video: https://edson-zepeda.github.io/swarm-signal-openlab/demo.html\n"
        "Codigo: https://github.com/Edson-Zepeda/swarm-signal-openlab\n\n"
        "El ZIP incluye codigo, datos, evidencias, informes y video.\n"
        "Para medir WiFi: extrae el ZIP y abre Iniciar.ps1 en Windows con Python 3.12+.\n"
        "La web publica reproduce datos guardados.\n\n"
        "Pendiente: confirmar movimiento fisico del participante.\n"
        "Avanzado Skybrush: requiere el repositorio asignado y tutorial del show.\n"
        "Verificacion upstream: CSI PASS; ./verify global FAIL por HTTP 403, con tres fases SKIP.\n"
        f"Revision: {commit}\n", encoding="utf-8")
    files = sorted(p for p in DEST.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (DEST / "SHA256SUMS.txt").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files), encoding="utf-8")
    print(json.dumps({"commit": commit, "archive": str(archive), "files": len(manifest["files"]),
                      "bytes": archive.stat().st_size, "zip_integrity": "PASS"}, indent=2))


if __name__ == "__main__":
    main()
