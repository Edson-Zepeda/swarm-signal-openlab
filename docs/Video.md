# Video de Swarm Signal · revisión 1.1

[Ver video](../media/SwarmSignal_Demo.mp4) · [Subtítulos](../media/SwarmSignal_Demo.vtt)

**1:48 · 1920 × 1080 · 30 fps.** Nueve capítulos con narración en español, gráficos animados, transiciones y reproducción fluida de las lecturas guardadas.

| Inicio aproximado | Contenido | Base verificable |
|---|---|---|
| 00:00 | Señal y evidencia | Capturas reales, sin etiquetas humanas verificadas |
| 00:10 | Pipeline del tutorial | 30 muestras; media −57.77 dBm |
| 00:22 | Referencia de 120 s | 233 lecturas; reproducción acelerada |
| 00:34 | Comparación de tres capturas | 3/8, 0/3 y 2/4 ventanas cumplen calidad |
| 00:47 | Abstención | CV temporal 33.6 % en la última ventana; límite actual 5 % |
| 00:58 | Cobertura de frecuencias | Esquema teórico a 2 muestras/s; banda original 0.5–3 Hz |
| 01:09 | Pruebas | 125 propias actuales; 45 unitarias y 5 integraciones históricas |
| 01:20 | Reproducibilidad | CSI sintético: hash exacto; verificación actual: 6 PASS, 3 SKIP |
| 01:36 | Siguiente paso | Receptor fijo y condiciones declaradas; prueba física pendiente |

La comparación utiliza ventanas disjuntas de 15 segundos. El denominador conserva los huecos de las ventanas elegibles; la fracción final demasiado corta queda fuera. Los cocientes describen **calidad del muestreo**, no exactitud de detección humana. Las etiquetas de las sesiones describen el contexto registrado; la comparación no demuestra una relación causal con la carga de CPU.

La última ventana irregular no presenta picos espectrales. Se muestran sus intervalos temporales y la abstención del analizador revisado. El diagrama de cobertura es **teórico**: a 2 muestras/s el límite de Nyquist es 1 Hz y solo se observa parte de la banda 0.5–3 Hz. No representa un espectro medido ni una medición de respiración. Los nodos móviles son una propuesta, no una prueba de vuelo.

La nueva ejecución de `./verify` identificó honestamente el cliente de consulta y conservó el script original: seis fases aprobadas y tres omitidas. La ejecución inicial con HTTP 403 permanece en el historial. La coincidencia del hash CSI corresponde a una referencia sintética y no sustituye las fases omitidas.

## Fuentes y versiones

El constructor lee explícitamente [project.json](../project.json), las tres sesiones cuyos hashes aparecen en ese manifiesto, [comparison.json](../web/data/comparison.json), el XML de la revisión, la verificación actual y el resumen upstream histórico. La sesión de referencia se reanaliza con la política actual sin modificar sus datos originales.

El [timeline](../media/video/timeline.json) registra tiempos, narración, versión de análisis y hashes. Sus entradas `snapshot_path` resuelven copias exactas de las fuentes utilizadas, incluido el XML de **125 pruebas**, bajo `media/video/sources/revision/`. La [auditoría de procedencia](../media/video/provenance_audit.json) comprueba esas copias y el MP4 final. Las reglas `-text` preservan sus bytes al descargar o clonar.

La edición 1.0 permanece en la versión publicada anterior. Sus 31 pruebas propias, el fallo HTTP 403 y el analizador original son hechos históricos; no se presentan como estado actual. El analizador v1 y su XML también permanecen congelados en `media/video/sources/`.

La voz es **sintética**, `es-MX-JorgeNeural`, generada con Microsoft Edge TTS. Solo se envió la narración pública al servicio, sin muestras ni identificadores de red. El MP4 incluye audio AAC y subtítulos opcionales; también se entregan SRT y VTT.

## Reconstrucción y revisión

El constructor requiere las dependencias de `requirements-media.txt`, FFmpeg y ffprobe:

```powershell
python scripts/build_video.py
```

`--preview` genera los nueve fotogramas de revisión. El audio se reutiliza cuando coincide el hash del guion; si no puede actualizarse, el constructor se detiene para evitar publicar narración desfasada. La codificación de video utiliza dos hilos y nunca inicia una captura de Wi-Fi. El servidor local admite rangos de bytes para que los capítulos puedan buscar su posición en Edge.

La [verificación final](../media/video_verification.json) incluye resolución, duración, cuadros por segundo, decodificación completa, presencia y niveles de audio, sincronización de subtítulos y fotogramas extraídos del MP4. La inspección visual se realiza sobre esos cuadros decodificados, además de las vistas previas.
