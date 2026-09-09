@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Iniciar.ps1" %*
if errorlevel 1 (
  echo.
  echo No se pudo abrir el laboratorio. Revisa el mensaje anterior.
  pause
  exit /b 1
)
