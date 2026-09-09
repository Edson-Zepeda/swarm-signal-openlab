param([switch]$SoloVerificar, [ValidateRange(1024,65535)][int]$Puerto = 8766)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
try {
    if (-not (Test-Path -LiteralPath $projectPython)) {
        $swarmLaunchers = @(
            @{ Name='py'; Args=@('-3.12') },
            @{ Name='py'; Args=@('-3') },
            @{ Name='python'; Args=@() }
        )
        $swarmCreated = $false
        foreach ($swarmLauncher in $swarmLaunchers) {
            if (-not (Get-Command $swarmLauncher.Name -ErrorAction SilentlyContinue)) { continue }
            & $swarmLauncher.Name @($swarmLauncher.Args) -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>$null
            if ($LASTEXITCODE -ne 0) { continue }
            & $swarmLauncher.Name @($swarmLauncher.Args) -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de Python.' }
            $swarmCreated = $true
            break
        }
        if (-not $swarmCreated) { throw 'Instala Python 3.10 o superior y vuelve a abrir Iniciar.cmd.' }
    }
    & $projectPython -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'El entorno existente requiere Python 3.10 o superior.' }
    & $projectPython -m pip --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & $projectPython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo reparar pip en el entorno.' }
    }
    $swarmCheck = @'
from importlib.metadata import version, PackageNotFoundError
from pip._vendor.packaging.requirements import Requirement
from pathlib import Path
import sys
try:
    expected = [Requirement(line.strip()) for line in Path('requirements.txt').read_text().splitlines() if '==' in line]
    active = [req for req in expected if not req.marker or req.marker.evaluate()]
    sys.exit(0 if all(version(req.name) in req.specifier for req in active) else 1)
except PackageNotFoundError:
    sys.exit(1)
'@
    & $projectPython -c $swarmCheck
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Preparando las dependencias del laboratorio...'
        & $projectPython -m pip install --disable-pip-version-check -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'La instalacion no termino. Puedes volver a abrir Iniciar.cmd para reintentar.' }
    }
    & $projectPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Hay dependencias incompatibles en el entorno.' }
    & $projectPython -c "import swarm_signal.server; print('Entorno verificado.')"
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo cargar el laboratorio.' }
    if ($SoloVerificar) { exit 0 }
    Write-Host "Abre http://127.0.0.1:$Puerto. Usa Ctrl+C para cerrar."
    & $projectPython -m swarm_signal.server --port $Puerto
    if ($LASTEXITCODE -ne 0) { throw 'El laboratorio no inicio. Comprueba que el puerto este disponible.' }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
