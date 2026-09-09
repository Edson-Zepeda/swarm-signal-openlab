# Auditoría técnica previa a las mejoras

Fecha: 2026-09-09. Base examinada: `99de7de05c98bb4597ad512aa8357204ec999e89`.

La aplicación tiene controles útiles: rechaza RSSI inventado en el lector de Windows, limita el servidor a localhost, comprueba Host/Origin, restringe los identificadores de archivo y protege las sesiones nuevas frente a temporizadores antiguos. Sin embargo, aún puede perder la posibilidad de guardar, mostrar una captura fallida que sigue activa y emitir una interpretación cuando la banda necesaria no está observada. Estos defectos impiden considerar terminada la mejora técnica.

## Método y evidencia

Se revisaron `swarm_signal/*.py`, las 31 pruebas existentes y los scripts de captura/exportación/arranque. Se ejecutaron pruebas negativas aisladas con datos, colectores, temporizadores y salida netsh **sintéticos**, nunca presentados como mediciones reales. No se ejecutó netsh ni se capturó movimiento físico. No se modificó la aplicación ni la evidencia histórica.

Reproductor: `../../tmp/swarm-audit-technical/probe_before.py`, desde la raíz del proyecto. Resultado completo: `../../tmp/swarm-audit-technical/probe_before.json`. Ejecución final: salida 0, aproximadamente 07:06:43–07:06:46 UTC. Desde la carpeta de trabajo superior se reproduce con:

```powershell
& '.\work\swarm\venv\Scripts\python.exe' '.\tmp\swarm-audit-technical\probe_before.py'
```

P1 significa que debe corregirse antes de cerrar la entrega; P2 es un defecto funcional o de validación que también debe quedar cubierto. La severidad considera este laboratorio local, no un servicio público expuesto.

## Hallazgos confirmados

### T01 · P1 · Error de guardado sin recuperación

**Ubicación:** `swarm_signal/server.py:95–120`, especialmente 97, 99 y 116.

`stop()` marca la captura inactiva antes de escribirla. Si la escritura falla, la siguiente llamada sale por la condición de sesión inactiva y no vuelve a guardar. La interfaz puede recibir `ready`, sin error persistente. Una captura nueva reemplaza las filas que permanecen únicamente en memoria.

**Reproducción:** `save_failure_retry` inyecta un error de disco en `write_json`. Resultado: excepción `SYNTHETIC disk failure`, `active=false`, `stopping=false`, reintento con `status=ready`, `error=null`, una muestra en memoria y cero archivos guardados.

**Aceptación:** separar fin de adquisición y persistencia; conservar el resultado pendiente y el error; permitir reintentar el guardado sin recapturar; bloquear el reemplazo de una sesión sin guardar; verificar que parar dos veces una sesión ya guardada siga siendo idempotente. El script de captura tampoco debe anunciar un archivo inexistente (`scripts/capture.py`).

### T02 · P1 · Un JSON dañado rompe el catálogo y deja capturas activas tras un error HTTP

**Ubicación:** `swarm_signal/server.py:44–49`, `57–85`, `122–149`.

El catálogo lee todos los JSON sin aislamiento ni validación de esquema. `start()` activa colector y temporizador antes de construir una respuesta que vuelve a leer ese catálogo.

**Reproducción:** un archivo temporal con `{ invalid fixture` hace que `/api/state` devuelva 404. `/api/start` devuelve 400 por el mismo error, pero `active_after_error=true` y el colector ya se creó.

**Aceptación:** excluir y reportar archivos inválidos individualmente, preservándolos para diagnóstico; validar los datos antes de exponerlos; mantener coherente la transición de arranque y su respuesta. Una sesión dañada no debe bloquear la captura o el acceso a las sesiones válidas.

### T03 · P1 · La banda de movimiento puede estar totalmente fuera de observación y producir un veredicto

**Ubicación:** `swarm_signal/analysis.py:39–61`; banda original en `vendor/ruview/v1/src/sensing/feature_extractor.py:45,240`.

La puerta de calidad solo exige duración, huecos y jitter. No comprueba cobertura espectral. La energía de una banda sin bins se convierte en cero; el clasificador puede interpretarla como quietud.

**Reproducción:** 11 muestras regulares durante 15 s, espaciadas 1.5 s: frecuencia de muestreo 0.6667 Hz, Nyquist 0.3333 Hz. La banda original de movimiento comienza en 0.5 Hz. El resultado fue `quality.ready=true`, `motion_band_power=0`, `present_still`, confianza 1.0. Son valores sintéticos de una prueba negativa, no presencia humana observada.

**Aceptación:** declarar las bandas y su cobertura efectiva; distinguir energía no disponible de energía cero; abstenerse cuando la banda requerida no sea observable. Con muestreo nominal de 2 Hz solo existe cobertura parcial de 0.5–3 Hz: debe conservarse esa limitación explícita y separar la salida heurística original de una interpretación validada por la aplicación. No se solicita alterar el código vendorizado ni afirmar que RSSI demuestra presencia humana.

La FFT también presupone espaciado uniforme a partir del intervalo medio, mientras se acepta jitter de hasta 25%. Es una limitación metodológica identificada por lectura, **no una desviación numérica cuantificada en esta auditoría**. La mejora debe definir una política verificable de remuestreo o abstención, con prueba de recuperación de una frecuencia conocida y casos de jitter/huecos.

### T04 · P1 · La exportación puede certificar evidencia inexistente y cambiar su procedencia

**Ubicación:** `scripts/export_web.py:20–34,41–52`.

Hay resultados y estados fijados en texto. Cualquier JSON de sesiones se publica como `recorded_real_wifi`; la condición se reemplaza por `unconfirmed` en procedencia, aunque la sesión declare otra. El exportador no valida que todos los artefactos correspondientes existan antes de marcarlos completos.

**Reproducción:** exportación dentro de una carpeta temporal con una única sesión sintética, sin artefactos del tutorial. Cinco etapas (01, 02, 03, 04 y 07) aparecen completas con archivos ausentes; la etapa 07 afirma 45 pruebas unitarias y 5 de hardware. `session.ground_truth=walking` contradice `provenance.ground_truth=unconfirmed`, y el fixture se etiqueta como Wi-Fi real.

**Aceptación:** derivar cifras y estados de archivos existentes y validados; ausencia o resultado insuficiente implica pendiente/parcial; preservar condición declarada y distinguirla de validación física; requerir procedencia verificable antes de afirmar captura real. La nueva exportación debe poder convivir con la evidencia histórica sin reescribirla. Implementación a cargo de la coordinación principal.

### T05 · P2 · Descargar CSV falla mientras se está midiendo

**Ubicación:** `web/app.js:289–300`; `swarm_signal/server.py:175–177`.

La web construye la descarga con el identificador actual cuando ya hay muestras. El servidor busca ese identificador solo en disco, donde aún no existe hasta detener la captura.

**Reproducción:** una captura activa con una muestra devuelve 404 en `/api/export.csv?id=<id_actual>`. Sin `id`, la misma ruta devuelve 200 y la fila esperada.

**Aceptación:** resolver el identificador actual contra una instantánea consistente de memoria; mantener la búsqueda validada de sesiones históricas. Probar descarga activa, completada, desconocida e identificador malicioso.

### T06 · P2 · Un cuerpo JSON de tipo incorrecto inicia la captura

**Ubicación:** `swarm_signal/server.py:202–208`; validación parcial en `57–69`.

**Reproducción:** `POST /api/start` con cuerpo `[]` y origen local autorizado devuelve 200 e inicia una captura con valores por defecto. No es un objeto de solicitud válido.

**Aceptación:** exigir objeto JSON, tipos correctos y límites explícitos; rechazar estructuras, valores no finitos y etiquetas inválidas con 400 sin alterar la sesión. Preservar los controles existentes de Host, Origin, longitud e identificadores. Este hallazgo no demuestra un acceso remoto que eluda esos controles.

### T07 · P2 · El nombre fijo del adaptador impide medir en instalaciones válidas

**Ubicación:** `swarm_signal/server.py:74`; `swarm_signal/collector.py:102`; interfaz de arranque `server.py:218–223`.

El parser permite seleccionar una interfaz, pero el servidor siempre usa `Wi-Fi`. La aplicación no ofrece esa selección.

**Reproducción:** salida netsh sintética con `Nombre: Wi-Fi 2`, `Estado: conectado`, `Señal: 80%`, `Rssi: -58`. Arrancar el laboratorio falla con `No se encontró la interfaz Wi-Fi.`; el mismo parser con el nombre explícito `Wi-Fi 2` obtiene −58 dBm.

**Aceptación:** descubrir interfaces conectadas y seleccionar la única disponible, o permitir elección explícita; múltiples interfaces deben tener selección determinista y transparente. Probar el recorrido completo API/colector, no solo el parser.

### T08 · P2 · El análisis acepta RSSI imposible y oculta descartes

**Ubicación:** `swarm_signal/analysis.py:28,65–68`.

Los datos cargados no pasan por las restricciones del lector netsh. Se eliminan valores no finitos sin contabilizar el descarte y se aceptan RSSI fuera del rango físico admitido por el propio colector.

**Reproducción:** 30 filas regulares con RSSI +60 dBm producen `quality.ready=true`, media +60 y clasificación `absent`. En otra serie de 30 filas, un NaN interior se descarta: se analizan 29, con `ready=true`, razón nula y ninguna advertencia por la fila inválida.

**Aceptación:** validación común de filas y sesiones al cargar y analizar; tipos numéricos finitos, rango RSSI y calidad válidos, orden temporal, límites de tamaño. Los rechazos deben ser explícitos y bloquear la interpretación de esa ventana; no corregir silenciosamente la evidencia original.

## Cobertura de pruebas que falta

Las pruebas existentes verifican parser español/inglés, RSSI inválido directo, redacción, mínimo de datos, Nyquist máximo, duplicados, huecos, carreras de temporizadores y Host/Origin. Son valiosas, pero no cubren los ocho recorridos anteriores. En particular, comprobar que el eje no supera Nyquist (`tests/test_signal.py:61`) no garantiza que la banda utilizada por el clasificador sea observable. Probar `stop()` dos veces en un guardado exitoso (`tests/test_lifecycle.py:133`) no cubre un primer guardado fallido.

Cada hallazgo debe tener una prueba de regresión que falle sobre esta base y pase tras la corrección. Añadir casos de FFT con señal conocida, muestreo insuficiente, jitter controlado, pérdida de muestras y validación de catálogo/API. Las nuevas ejecuciones deben producir evidencia con nombre nuevo; no sobrescribir `evidence/own_tests.xml` ni resultados upstream históricos.

## Arranque, dependencias y entrega

La revisión del arranque identifica que una `.venv` existente evita la instalación, aunque le falten dependencias. La coordinación principal confirmó la reproducción en `tmp/partial-install-before.log` y conserva la responsabilidad sobre arranque, requirements, exportación, empaquetado y la matriz de entrega. Su verificación debe incluir instalación limpia, instalación parcial y ejecución desde el ZIP descargado. Esta auditoría no declara resueltas esas verificaciones.

No se identifica aquí un defecto confirmado en las comprobaciones de árbol limpio, hashes del paquete o preservación de bytes por `.gitattributes`. Tampoco se vuelve a ejecutar ni se modifica la verificación upstream histórica. Un diagnóstico posterior de acceso externo debe registrarse como ejecución nueva, sin reemplazar el HTTP 403 que ocurrió en la primera ejecución.
