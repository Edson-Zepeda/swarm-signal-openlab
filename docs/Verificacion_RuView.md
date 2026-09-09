# Verificación de RuView

**Resultado vigente registrado: 6 fases PASS, 0 FAIL y 3 SKIP; código de salida 0 (`PASS_WITH_SKIPS`).** La nueva ejecución del 9 de septiembre de 2026 identificó la aplicación en las consultas HTTP mediante un User-Agent explícito. `./verify` se ejecutó sin modificaciones, sobre RuView fijado en `d613a576ea848f96a9b15bac4e7f60b6be7c08e7`. Las tres fases omitidas no se presentan como ejecutadas.

La [nueva evidencia](../evidence/revision/verify_identified.json), registrada a las **07:09:26 UTC**, conserva configuración, estados, hashes y [log completo](../evidence/revision/verify_identified.log). Las 12 consultas de crates.io pasaron. Rust, PyO3 y la ejecución del contenedor siguieron omitidos; el manifiesto Docker publicado sí se consultó.

| Corrida del 09/09/2026 | PASS | FAIL | SKIP | Salida |
|---|---:|---:|---:|---:|
| Original, 06:18-06:19 UTC | 5 | 1 | 3 | 1 |
| Cliente identificado, registro 07:09 UTC | 6 | 0 | 3 | 0 |

El **FAIL con HTTP 403 se conserva como resultado histórico**. No se reemplazaron sus logs ni se cambió el hash esperado para conseguir una aprobación. Los registros originales, fechas, argumentos y hashes están en [verification_summary.json](../evidence/upstream/verification_summary.json). También se conservan las **45 unitarias**, las **5 integraciones con adaptación de idioma** y la **prueba CSI determinística** aprobadas en aquella ejecución.

## Resultados históricos del 9 de septiembre de 2026

| Ejecución | Resultado observado | Evidencia |
|---|---|---|
| Comandos del tutorial con `PYTHONPATH=archive/v1` | Error de colección: `No module named 'v1'` | [Unitarias](../evidence/upstream/10_pdf_unit_exact.log), [integración](../evidence/upstream/11_pdf_live_exact.log) |
| Unitarias, cambiando solo a `PYTHONPATH=archive` | 45 aprobadas; 1 advertencia de configuración `asyncio_mode` | [Salida](../evidence/upstream/04_unit_archive_pythonpath.log), [JUnit](../evidence/upstream/unit.xml) |
| Integración original con ruta de importación correcta | 5 omitidas por precheck de conectividad en inglés | [Salida](../evidence/upstream/07_live_original_precheck.log) |
| Integración, copia con precheck en español e inglés | 5 aprobadas en 37.26 segundos | [Salida](../evidence/upstream/08_live_spanish_precheck.log), [JUnit](../evidence/upstream/live_adapted.xml) |
| Verificador CSI original | PASS; hash idéntico al esperado | [Salida](../evidence/upstream/05_csi_proof_original.log) |
| `./verify` original completo | Código 1: 5 fases PASS, 1 FAIL y 3 SKIP | [Salida](../evidence/upstream/03_verify_original_shell.log) |

El reto menciona 36 unitarias. La versión fijada incluye esas 36 y nueve pruebas adicionales de disponibilidad en Linux y selección del recolector. Se reportan las 45 realmente ejecutadas. Los nombres históricos `10_pdf` y `11_pdf` identifican los comandos del tutorial enlazado por el PDF; el PDF no imprime esos comandos completos. Los registros `01` y `06` conservan también el intento con las rutas `v1/tests/...` obsoletas que siguen apareciendo en documentación interna.

## Adaptaciones y alcance

Los imports actuales usan `v1.src...`, por lo que la raíz correcta es `archive`. No fue necesario reescribir módulos ni sustituir dependencias.

En Windows en español, `netsh` informa `Estado: conectado`; el test original busca `connected` y `state`. Se adaptó exclusivamente esa comprobación en una **copia externa**. El [diff](../evidence/upstream/live_precheck_locale.patch) y la [procedencia](../evidence/upstream/live_adaptation_provenance.json) documentan el cambio. Un análisis AST verificó que las **15 aserciones** permanecieron idénticas. El recolector, el extractor, el clasificador y `CommodityBackend` siguieron siendo los originales.

La integración sí leyó el adaptador Wi-Fi real: una ventana produjo 20 muestras, media de −57.00 dBm y varianza muestral de 0.9474 dBm². El clasificador devolvió `active` y `confidence=1.0`. **No hubo etiquetas de presencia o movimiento verificadas**; ese resultado demuestra ejecución, no exactitud de detección. El valor `confidence` es una heurística del código, no una probabilidad calibrada.

Las pruebas originales aceptan calidad de enlace 0, aunque en este equipo ese valor aparece porque el recolector no reconoce `Señal`. Su ruido fijo de −95 dBm y sus contadores de bytes incrementados artificialmente tampoco son mediciones. La prueba `test_rssi_varies_between_samples` imprime la variación, pero no contiene una aserción que la exija. Por eso, cinco pruebas aprobadas no eliminan estas limitaciones.

## Prueba CSI y verificación completa histórica

Se procesaron 100 de las 1,000 tramas de referencia sintética, obteniendo 100 vectores y 243,200 bytes canónicos. El SHA-256 calculado y el publicado coincidieron exactamente:

```text
f8e76f21a0f9852b70b6d9dd5318239f6b20cbcb4cdd995863263cecdc446f7a
```

No se regeneró el hash esperado ni se utilizó el fallback de tolerancia. La coincidencia se observó tanto con Python 3.11.9 / NumPy 2.3.4 / SciPy 1.16.2, elegidos por Git Bash, como con el entorno virtual registrado en el JSON. Esto comprueba reproducibilidad del procesamiento de la referencia; no equivale a captura CSI real, estimación de pose o validación de rescate.

La siguiente tabla describe exclusivamente el `./verify` original de las **06:18-06:19 UTC del 09/09/2026**. La fase 6 pasó después en la nueva ejecución; las demás conservaron su estado.

| Fase de `./verify` histórico | Estado original | Interpretación |
|---|---|---|
| 1. Procesamiento Python | PASS | Hash idéntico a la referencia publicada |
| 2. Búsqueda de patrones aleatorios | PASS | No hubo coincidencias del patrón buscado en `archive/v1/src` completo |
| 3. Pruebas Rust | SKIP | Cargo no instalado; `v2` fuera de la copia dispersa |
| 4. Compilación PyO3 | SKIP | Cargo no instalado; binding `python` fuera de la copia dispersa |
| 5. Invariante de identidad | PASS | Comprobación estática del script upstream |
| 6. Registro crates.io | FAIL | El script informó 12 consultas fallidas; el diagnóstico del primer endpoint obtuvo HTTP 403 |
| 7. Registro npm | PASS | Se pudo consultar `@ruvnet/rvagent` versión 0.2.0 |
| 8. Manifest de Docker | PASS | Manifest publicado con `amd64` y `arm64` |
| 9. Ejecutable HOMECORE | SKIP | Docker instalado, daemon no disponible |

El mensaje upstream «12 crates missing» agrupa cualquier fallo de `curl`. El [HTTP 403 original](../evidence/upstream/12_crates_http_diagnostic.log) no demostraba que los paquetes no existieran. El diagnóstico posterior identificó el cliente con `SwarmSignal/1.1 (+https://github.com/Edson-Zepeda/swarm-signal-openlab)`; las 12 consultas pasaron en la nueva corrida. No se instaló Rust, se inició Docker ni se ejecutaron contenedores para convertir los tres SKIP en PASS.

## Configuración de la nueva ejecución

La evidencia registra `CURL_HOME=project/tmp/identified-api`, aplicado solo al proceso del verificador, con un archivo `.curlrc` de este contenido:

```text
user-agent = "SwarmSignal/1.1 (+https://github.com/Edson-Zepeda/swarm-signal-openlab)"
max-time = 25
```

La identificación corresponde a esta aplicación y a su repositorio. El timeout limita cada consulta de curl a 25 segundos. No se modificó el perfil de shell ni la configuración permanente del usuario. El SHA-256 de `verify` siguió siendo `f67c92dbebe2ef843636588e85bb9f6ec602bbd7607f467c72675f601e91ce2a`; la expectativa CSI siguió siendo la indicada arriba. Estos valores y el hash del nuevo log están en `verify_identified.json`.

## Reproducción

Con una copia limpia del commit indicado, NumPy, SciPy y pytest instalados, ejecutar desde la carpeta de este proyecto:

```powershell
python evidence/upstream/reproduce.py --repo RUTA_A_RUVIEW --python RUTA_AL_PYTHON_DEL_ENTORNO
```

Añadir `--live` habilita unos 40 segundos de lecturas reales de Wi-Fi y genera una nueva copia de la adaptación de idioma. El script conserva logs y JUnit en `upstream-replay`; comprueba el commit y rechaza cambios en el código upstream. La ruta determinística del reproductor también se ejecutó y terminó con código 0.

### Repetir las nueve fases con identificación local al proceso

Desde PowerShell, sustituye `RUTA_A_RUVIEW` por la copia del commit fijado. Ajusta la ruta de Git Bash si está instalado en otro lugar. El siguiente bloque crea la configuración y el log en una carpeta temporal; no escribe dentro de RuView ni modifica variables de entorno permanentes. No se ha vuelto a ejecutar el verificador al redactar esta guía.

```powershell
$taskRepo = (Resolve-Path 'RUTA_A_RUVIEW').Path
$taskBash = 'C:\Program Files\Git\bin\bash.exe'
$taskCurlDir = Join-Path ([IO.Path]::GetTempPath()) ('swarm-curl-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskCurlDir | Out-Null
$taskCurlConfig = @'
user-agent = "SwarmSignal/1.1 (+https://github.com/Edson-Zepeda/swarm-signal-openlab)"
max-time = 25
'@
[IO.File]::WriteAllText(
    (Join-Path $taskCurlDir '.curlrc'),
    $taskCurlConfig,
    [Text.UTF8Encoding]::new($false)
)
$taskLog = Join-Path $taskCurlDir 'verify_identified_replay.log'

Push-Location -LiteralPath $taskRepo
try {
    & $taskBash -c 'CURL_HOME="$1" ./verify' 'swarm-verify' ($taskCurlDir -replace '\\', '/') 2>&1 |
        Tee-Object -FilePath $taskLog
    $taskExit = $LASTEXITCODE
}
finally {
    Pop-Location
}
Write-Output "Código de salida: $taskExit"
Write-Output "Configuración y log: $taskCurlDir"
```

`CURL_HOME` se asigna en Git Bash únicamente al comando `./verify` y a sus procesos hijos. La carpeta temporal queda disponible para revisar `.curlrc` y el log; no se sustituye `evidence/upstream/` ni `evidence/revision/`. Antes de ejecutar, comprueba el commit y el SHA-256 indicados y revisa `verify`: consulta servicios externos y puede ejecutar Docker si está disponible. El resultado de una reproducción nueva depende de ese entorno y del estado de los servicios; no está garantizado que repita los conteos registrados.

Fuentes del alcance: [tutorial, issue #36](https://github.com/ruvnet/RuView/issues/36), [tests fijados](https://github.com/ruvnet/RuView/blob/d613a576ea848f96a9b15bac4e7f60b6be7c08e7/archive/v1/tests/unit/test_sensing.py), [verificador fijado](https://github.com/ruvnet/RuView/blob/d613a576ea848f96a9b15bac4e7f60b6be7c08e7/verify).
