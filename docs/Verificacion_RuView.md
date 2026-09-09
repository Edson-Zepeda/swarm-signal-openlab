# Verificación de RuView

Se ejecutó el código fijado en `d613a576ea848f96a9b15bac4e7f60b6be7c08e7`. Pasaron **45 pruebas unitarias**, **5 pruebas de integración con una adaptación de idioma** y la **prueba determinística CSI**. El `./verify` completo terminó en **FAIL**, por una consulta al registro de paquetes que devolvió HTTP 403. No se presenta ese resultado como una verificación integral aprobada.

Los registros originales, sus fechas UTC, argumentos, códigos de salida y SHA-256 están en [verification_summary.json](../evidence/upstream/verification_summary.json). El repositorio upstream terminó limpio; no se alteraron sus fuentes, pruebas ni valores esperados.

## Resultados

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

## Prueba CSI y verificación completa

Se procesaron 100 de las 1,000 tramas de referencia sintética, obteniendo 100 vectores y 243,200 bytes canónicos. El SHA-256 calculado y el publicado coincidieron exactamente:

```text
f8e76f21a0f9852b70b6d9dd5318239f6b20cbcb4cdd995863263cecdc446f7a
```

No se regeneró el hash esperado ni se utilizó el fallback de tolerancia. La coincidencia se observó tanto con Python 3.11.9 / NumPy 2.3.4 / SciPy 1.16.2, elegidos por Git Bash, como con el entorno virtual registrado en el JSON. Esto comprueba reproducibilidad del procesamiento de la referencia; no equivale a captura CSI real, estimación de pose o validación de rescate.

| Fase de `./verify` | Estado | Interpretación |
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

El mensaje upstream «12 crates missing» agrupa cualquier fallo de `curl`. El [HTTP 403 observado](../evidence/upstream/12_crates_http_diagnostic.log) impide concluir que los paquetes no existan. No se intentó eludir ese rechazo. Tampoco se instaló Rust, se inició Docker o se descargaron imágenes para convertir un SKIP en PASS.

## Reproducción

Con una copia limpia del commit indicado, NumPy, SciPy y pytest instalados, ejecutar desde la carpeta de este proyecto:

```powershell
python evidence/upstream/reproduce.py --repo RUTA_A_RUVIEW --python RUTA_AL_PYTHON_DEL_ENTORNO
```

Añadir `--live` habilita unos 40 segundos de lecturas reales de Wi-Fi y genera una nueva copia de la adaptación de idioma. El script conserva logs y JUnit en `upstream-replay`; comprueba el commit y rechaza cambios en el código upstream. La ruta determinística del reproductor también se ejecutó y terminó con código 0.

Para reproducir por separado las nueve fases, revisar primero `verify` y ejecutar `./verify` desde Git Bash en la raíz de RuView. Ese comando consulta servicios externos y puede ejecutar Docker cuando esté disponible; su resultado depende del entorno y del estado actual de esos servicios.

Fuentes del alcance: [tutorial, issue #36](https://github.com/ruvnet/RuView/issues/36), [tests fijados](https://github.com/ruvnet/RuView/blob/d613a576ea848f96a9b15bac4e7f60b6be7c08e7/archive/v1/tests/unit/test_sensing.py), [verificador fijado](https://github.com/ruvnet/RuView/blob/d613a576ea848f96a9b15bac4e7f60b6be7c08e7/verify).
