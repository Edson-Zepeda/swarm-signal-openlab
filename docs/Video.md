# Video de Swarm Signal

[Ver el video](../media/SwarmSignal_Demo.mp4) · [Subtítulos](../media/SwarmSignal_Demo.vtt)

**1:45 · 1920 × 1080 · 30 fps.** Narración en español, gráficos animados, transiciones y ocho capítulos. La identidad visual usa fondo oscuro, lima, cian y tipografía grande.

| Tiempo | Contenido | Evidencia |
|---|---|---|
| 00:00 | Señal y alcance | Reproducción de una captura real |
| 00:11 | Pipeline del tutorial | 30 muestras; media −57.77 dBm |
| 00:24 | Captura de 120 segundos | 233 lecturas; recorrido acelerado |
| 00:38 | Abstención por calidad | CV temporal 33.6 %; clasificación vacía |
| 00:51 | Espectro de la última ventana | Nyquist efectivo de 0.94 Hz |
| 01:03 | Pruebas de software | 45 unitarias, 5 integraciones adaptadas y 31 propias |
| 01:14 | Reproducibilidad | CSI PASS; verificación global FAIL por HTTP 403 |
| 01:31 | Propuesta SWARM | Receptor fijo y nodos móviles, por validar |

Las curvas representan exclusivamente las muestras guardadas del tutorial y de la sesión `20260909T062522_420b46`. La visualización acelera su reproducción; no muestra una interfaz que finja estar en vivo. Los picos espectrales no se presentan como respiración, y no se asignan etiquetas de presencia o movimiento a las capturas. El diagrama de drones es una propuesta, no una prueba de vuelo.

La prueba CSI utiliza la referencia **sintética** del repositorio. Su coincidencia de hash se distingue del resultado global de `./verify`: cinco fases PASS, una FAIL y tres SKIP. Las 31 pruebas propias corresponden al XML guardado que figura en la procedencia del video.

El XML utilizado está congelado en [sources/own_tests.xml](../media/video/sources/own_tests.xml), recuperado sin cambios del commit `b6dae0c`. Su SHA-256 coincide con el registrado al construir el video. La [auditoría de procedencia](../media/video/provenance_audit.json) comprueba las cinco fuentes contra sus bytes locales y los objetos de Git; las reglas `-text` conservan los bytes de las fuentes verificadas al descargar o clonar.

La voz es **sintética**, `es-MX-JorgeNeural`, generada con Microsoft Edge TTS a partir del guion del video. Solo se envió el texto explicativo al servicio; las muestras y los identificadores de red no se enviaron. El MP4 incluye audio AAC y subtítulos opcionales en español, también entregados como SRT y VTT.

## Reproducción y revisión

El [script](../scripts/build_video.py) requiere Python con NumPy, Pillow y `edge-tts`, además de FFmpeg y ffprobe. Ejecutar:

```powershell
python scripts/build_video.py
```

Con los MP3 almacenados y el mismo guion, la reconstrucción utiliza el audio local. `--preview` genera los ocho fotogramas de revisión. Las futuras codificaciones se limitan a dos hilos para reducir la interferencia con capturas simultáneas.

[Timeline y hashes de las fuentes](../media/video/timeline.json) · [Verificación del archivo final](../media/video_verification.json)

La revisión comprende dimensiones, duración, frecuencia de fotogramas, presencia de audio y subtítulos, decodificación del MP4 y fotogramas representativos extraídos del archivo final. Los resultados detallados se conservan en el JSON de verificación.
