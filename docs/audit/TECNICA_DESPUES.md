# Correcciones técnicas y aceptación

Fecha: 2026-09-09. Comparación contra `5c8e242`. Política actual: `2.0-quality-audit`.

**Primera aceptación del core: 90 pruebas aprobadas, cero fallos y cero errores.** Incluye las 31 pruebas anteriores y 59 casos nuevos de regresión y validación. Se ejecutaron con datos, lectores, temporizadores y servidores de prueba aislados; no se utilizó netsh ni se produjo una captura física. No se cambió el código vendorizado ni la evidencia histórica. La suite conjunta vigente incluye también las correcciones posteriores y se conserva en [own_tests.xml](../../evidence/revision/own_tests.xml).

[Resultado XML](../../evidence/revision/core_tests.xml) · [Log](../../evidence/revision/core_tests.log) · [Comandos y hashes de código probado](../../evidence/revision/core_acceptance.json)

## Aceptación por hallazgo

| Hallazgo | Corrección comprobada | Pruebas representativas |
|---|---|---|
| T01 · Guardado | El fallo conserva muestras, identificador, error y estado pendiente. Bloquea una captura nueva. Reintentar detener escribe la misma sesión; repetir un guardado exitoso no cambia sus bytes. | `test_failed_save_can_retry_without_replacing_or_losing_session`, `test_failed_http_stop_exposes_retry_state` |
| T01 · Cierre y recuperación | Se preservan fecha de cierre y diagnóstico. El CLI verifica el archivo antes de anunciarlo; si no puede guardar, conserva una copia alternativa. Si tampoco puede escribir esa copia, entrega el JSON completo en la salida y termina con error. | `test_completed_snapshot_keeps_stop_time_and_diagnostics`, `test_capture_cli_writes_verified_recovery_on_persistent_save_failure`, `test_capture_cli_never_announces_missing_file` |
| T02 · Catálogo y estado | Los JSON dañados se reportan individualmente en `catalog_errors`; no bloquean sesiones válidas ni generan arranques ocultos. No se modifica el archivo rechazado. | `test_invalid_catalog_does_not_start_hidden_capture_or_block_state`, `test_valid_catalog_survives_bad_neighbor_and_recomputes_legacy_replay` |
| T03 · Cobertura y FFT | Una banda no observable o insuficiente queda sin energía disponible ni clasificación. Se declara cobertura parcial a 2 Hz. El espectro se inhibe cuando el muestreo incumple la política. | `test_no_motion_bins_cannot_mean_still`, `test_only_one_motion_bin_is_explicitly_insufficient`, `test_partial_motion_coverage_and_known_frequency_recovery`, pruebas de jitter |
| T04 · Exportación | La coordinación principal implementa y prueba la exportación basada en evidencia. Su aceptación se registra en la suite conjunta, no se atribuye a estas 90 pruebas del core. | `tests/test_evidence.py`; resultado conjunto `evidence/revision/own_tests.xml` |
| T05 · CSV activo | La resolución por identificador devuelve una instantánea consistente de la sesión actual; los identificadores históricos siguen validados. | `test_active_session_csv_and_json_resolve_current_id` |
| T06 · API JSON | Se exige objeto JSON, tipos y límites válidos. Se rechazan campos desconocidos, duplicados, NaN, cuerpos no objeto y parámetros inesperados al detener, sin iniciar una captura. Se conservan Host/Origin. | `test_bad_start_json_never_mutates_lab`, `test_stop_also_requires_valid_empty_object`, pruebas de seguridad anteriores |
| T07 · Interfaz Windows | Se detecta la única interfaz conectada. Si hay varias, se exige selección explícita; nunca se elige arbitrariamente la primera. Una interfaz desconectada no reutiliza datos de otra. | `test_connected_renamed_interface_is_discovered_without_hardware`, `test_ambiguous_connected_interfaces_require_explicit_choice`, `test_disconnect_cannot_reuse_other_interface_reading`, `test_explicit_interface_reaches_collector` |
| T08 · Filas inválidas | Se validan lista, tamaños, tipos, finitud, rango RSSI, calidad, fases y orden temporal. Valores imposibles o NaN en la señal bloquean el análisis con conteo explícito; no se eliminan silenciosamente. | `test_invalid_rssi_blocks_analysis_instead_of_being_dropped`, `test_loaded_rows_are_strictly_validated`, `test_row_bounds_and_order_are_checked` |

El cierre de un lector que no termina sigue siendo reintentable y bloquea otra captura. Las pruebas también comprueban que los errores netsh no fabrican muestras, que una lectura individual autodetecta la interfaz y que `/api/comparison` devuelve el objeto calculado para la carpeta del laboratorio.

## Política de análisis

La ventana usa los últimos 15 segundos reales; requiere al menos 14 segundos cubiertos y cuatro muestras para calcular características. No se reduce la ventana a un número nominal de muestras. Los intervalos deben ser crecientes y compatibles con este colector; intervalos inferiores a 1 ms se rechazan para evitar resultados numéricos no finitos.

No hay interpolación. La FFT supone espaciado aproximadamente uniforme y solo se publica si el coeficiente de variación de los intervalos es **≤5 %**, la desviación relativa máxima frente al intervalo medio es **≤15 %**, y el hueco máximo es **≤2 s**. Cuando falla esta condición se conservan las estadísticas temporales y el RSSI; el espectro se vacía y las características espectrales quedan en `null`. La razón de abstención permanece visible.

La banda original de movimiento es **0.5–3 Hz**. Se publican su intervalo configurado, bins observados, alcance efectivo y cobertura. Se exigen **dos bins** como mínimo para emitir la heurística: es una condición operativa de observabilidad, **no un umbral validado de detección humana**. Si no se cumplen cobertura o muestreo, la energía de esa banda es `null` y no hay clasificación. A 2 Hz el Nyquist máximo es 1 Hz: la cobertura sigue siendo parcial y no permite concluir que no hubo movimiento fuera de la parte observada.

`upstream_classification` conserva la salida original como diagnóstico separado y claramente identificado; `classification` contiene únicamente la salida admitida por las puertas de calidad. Ninguna de ellas convierte las capturas sin etiqueta en evidencia de presencia humana ni calibra la confianza del clasificador como probabilidad real.

## Archivos históricos y procedencia

Las sesiones cargadas se validan y se reanalizan con la política actual; sus características y cuadros v1 no se reutilizan como análisis actual. La caché usa **SHA-256 de los bytes y versión de política**, y `replay_source` identifica la fuente. Una prueba modifica los bytes conservando tamaño y fecha del archivo y comprueba que la caché se invalida. Otra comprueba que reanalizar no cambia un solo byte del JSON original.

Antes de editar el analizador se guardó su versión exacta en [analysis-v1.py](../../media/video/sources/analysis-v1.py), SHA-256 `9cd8f9a95d70b16bd00f86148a7b6cf09bc5d53c9d43a96c1f98903dde75f7fa`. La [comprobación de cinco fuentes](../../evidence/revision/video_source_provenance.json) corresponde a ese momento y a la edición histórica, antes de volver a renderizar el video.

Posteriormente se generó la edición revisada del video, que utiliza doce fuentes congeladas bajo `media/video/sources/revision/`. El [timeline vigente](../../media/video/timeline.json) identifica esas copias mediante `snapshot_path`; su [auditoría actual](../../media/video/provenance_audit.json) conserva los hashes del video y de sus fuentes. Los resultados del video histórico no sustituyen los de la edición vigente.

## Prueba negativa sobre la versión anterior

Se copiaron únicamente los archivos originales del commit `5c8e242` a una carpeta temporal y se ejecutaron los mismos 59 casos nuevos contra esa copia. Resultado: **49 fallos, 10 aprobados y 3 errores adicionales de limpieza** del catálogo defectuoso. Esos tres errores son entradas adicionales del XML, no tres pruebas nuevas. Las APIs nuevas ausentes también producen fallos; los defectos originales ya estaban reproducidos individualmente en `TECNICA_ANTES.md`.

[Log anterior](../../evidence/revision/core_baseline.log) · [XML anterior](../../evidence/revision/core_baseline.xml)

Después de las correcciones, los 59 casos y los 31 anteriores pasan juntos: **90/90**, salida 0. Comando desde el proyecto:

```powershell
python -m pytest tests/test_signal.py tests/test_lifecycle.py tests/test_audit_regressions.py -q -o addopts= --junitxml=../../tmp/swarm-audit-technical/core_after.xml
```

La aceptación conjunta del proyecto incorpora además exportación, comparación, arranque e interfaz. Este informe acredita el core y el CLI de captura; la prueba física con condiciones declaradas sigue requiriendo una ejecución real del participante.

## Cierre posterior de la revisión

La comprobación del MP4 nuevo encontró un fallo adicional en el servidor local: faltaban respuestas HTTP por rangos, necesarias para saltar a un capítulo. Se añadieron GET parcial, HEAD, cabeceras de tamaño y validación de rangos; 17 pruebas comprueban bytes, respuestas 206/416 y compatibilidad del archivo completo. También se acotó el comparador a 10,000 filas, 3,600 segundos y 16 MB por archivo, con cinco casos adicionales que evitan bloqueos por fechas corruptas.

La suite final completa contiene **125 pruebas aprobadas en Python 3.12.14 y 3.11.9**. Los hashes de los archivos realmente probados, los comandos y ambos XML están registrados en [regression_verification.json](../../evidence/revision/regression_verification.json). Los 90 casos anteriores son una etapa documentada de esta revisión, no el conteo final.

## Corrección posterior de reproducción local

La revisión del reproductor en Edge detectó que el servidor entregaba el MP4 completo sin soporte de rangos: el archivo se reproducía, pero los capítulos no podían buscar su posición. `Handler` ahora anuncia `Accept-Ranges: bytes`, responde con 206 a un rango válido y con 416 a uno no satisfacible, limita la copia al rango pedido y conserva MIME, tamaño y fecha del archivo abierto. HEAD describe el archivo completo sin enviar su cuerpo. Las solicitudes múltiples o malformadas se ignoran y reciben el archivo completo, comportamiento permitido por HTTP.

Las **17 pruebas** de `tests/test_media_http.py` verifican descarga completa, rangos cerrados, abiertos y de sufijo, límites y archivos vacíos, HEAD, If-Range y rechazo de Host no autorizado. Usan archivos artificiales y no capturan Wi-Fi. Se incorporan a la suite conjunta; la revisión del navegador verifica además el salto real entre capítulos.
