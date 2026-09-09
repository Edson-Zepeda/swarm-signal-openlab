$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Instala Python 3.12 o superior y vuelve a ejecutar.' }
    & $projectPython -c "import sys; assert sys.version_info >= (3, 12), 'Se requiere Python 3.12 o superior'"
    if ($LASTEXITCODE -ne 0) { throw 'Se requiere Python 3.12 o superior.' }
    & $projectPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
}
Write-Host 'Abre http://127.0.0.1:8766. Usa Ctrl+C para cerrar.'
& $projectPython -m swarm_signal.server --port 8766
