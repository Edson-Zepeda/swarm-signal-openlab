# SWARM / SIGNAL

Laboratorio de sensado WiFi para el Open Lab de VantTec. Lee RSSI real en Windows, ejecuta el pipeline de RuView y conserva evidencia reproducible.

[Abrir laboratorio](https://edson-zepeda.github.io/swarm-signal-openlab/) · [Ver video](https://edson-zepeda.github.io/swarm-signal-openlab/demo.html) · [Descargar entrega](https://github.com/Edson-Zepeda/swarm-signal-openlab/releases/latest)

## Abrir

Windows 10/11, WiFi conectado y Python 3.10 o superior. Extrae la entrega y abre **Iniciar.cmd**. El iniciador instala las dependencias necesarias y repara instalaciones incompletas.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m swarm_signal.server
```

Abre **http://127.0.0.1:8766**. Para comprobar solo la instalación: `powershell -File Iniciar.ps1 -SoloVerificar`.

El servidor solo escucha en tu equipo. La web publicada reproduce capturas guardadas; no puede medir el WiFi de un visitante.

## Medir

1. Mantén la laptop y el router fijos.
2. Registra una captura en quietud y otra cruzando la trayectoria laptop-router.
3. Etiqueta únicamente la condición que realizaste. Repite en sesiones distintas.
4. Descarga CSV y compara la salida del algoritmo con las condiciones anotadas. Sigue [el protocolo](docs/PRUEBA_PENDIENTE.md) para conservar controles y repeticiones.

```powershell
.\.venv\Scripts\python scripts/capture.py --seconds 60 --condition unconfirmed
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest tests -q
```

Para marcar una condición física usa `--condition still` o `--condition walking` solo al realizarla. Los registros entregados inicialmente tienen condición **sin confirmar**.

## Entrega

- `docs/SwarmSignal_Informe.pdf`: procedimiento, gráficas, pruebas y resultados.
- `docs/SwarmSignal_Propuesta.pdf`: propuesta de una cuartilla para SWARM.
- `docs/SwarmSignal_Auditoria.pdf`: evaluación crítica y correcciones verificadas.
- `evidence/tutorial/`: entorno, netsh, lectura individual y ventana de 15 segundos.
- `evidence/sessions/`: mediciones crudas con marcas temporales.
- `evidence/upstream/`: comandos, errores originales, adaptaciones y verificación.
- `evidence/ui/`: capturas reales y revisión de interfaz.
- `web/`: laboratorio interactivo y reproducción.
- `media/SwarmSignal_Demo.mp4`: demostración narrada de 1:45, con subtítulos.

La prueba física de movimiento sigue pendiente. Los resultados completos y las limitaciones se conservan en los documentos y en `docs/PRUEBA_PENDIENTE.md`.

La comparación de capturas usa ventanas disjuntas de 15 segundos. La fracción de ventanas aptas mide calidad de datos; **no es exactitud de detección**. La entrega fija sus fuentes y versión en `project.json`. Los scripts del tutorial generan una carpeta nueva por ejecución y conservan los registros publicados.

## Comprobar la interfaz

Con el servidor local abierto:

```powershell
npm install
npx playwright install chromium
npm run test:ui
```

La comprobación pública se ejecuta con `node scripts/verify_public_ui.cjs`.

## Qué concluye

Se ejecuta `WindowsWifiCollector → RssiFeatureExtractor → PresenceClassifier`, además de `CommodityBackend`. El resultado `active` significa que se superaron umbrales de variación y energía; por sí solo no identifica una persona. Un resultado `absent` tampoco demuestra que un lugar esté vacío.

El score de RuView es heurístico, no exactitud medida. Este proyecto no detecta signos vitales ni localiza personas. La FFT se limita a la frecuencia de Nyquist medida. Datos insuficientes, interrumpidos o desactualizados no generan un veredicto en la interfaz.

La política revisada exige cobertura temporal de al menos 14 segundos, huecos de hasta 2 segundos, CV de intervalos ≤5%, desviación máxima ≤15% y dos bins en la parte observable de la banda de movimiento. Son criterios conservadores de ingeniería, no umbrales de exactitud validados. No se interpolan lecturas. [Decisiones](docs/DECISIONES.md).

## Procedencia

[Tutorial oficial #36](https://github.com/ruvnet/RuView/issues/36), consultado el 9 de septiembre de 2026. RuView fijado en `d613a576ea848f96a9b15bac4e7f60b6be7c08e7`.

Se incluyen sin modificaciones los cinco módulos necesarios de `archive/v1/src/sensing/`, bajo licencia MIT original en `vendor/ruview/LICENSE`. La adaptación española y la validación viven en `swarm_signal/collector.py`; no se alteran los umbrales para conseguir una detección.

La batería upstream vigente tiene más pruebas que las 36 del tutorial. El detalle de pruebas pasadas, omitidas y fallidas está en el informe y los logs. La prueba determinística CSI es distinta de validar presencia humana mediante RSSI.

La revisión identificó correctamente el cliente de la API de crates.io y volvió a ejecutar `./verify` sin modificarlo: 6 fases PASS y 3 SKIP, código 0. El fallo inicial permanece en la evidencia histórica. [Registro actual](evidence/revision/verify_identified.json).

Las dependencias básicas están separadas de pruebas (`requirements-dev.txt`) y producción de documentos/video (`requirements-media.txt`). La automatización de GitHub ejecuta las pruebas sin hardware en Python 3.10, 3.11 y 3.12. Los resultados de instalación local y revisión están en `evidence/revision/`.

## Avanzado Skybrush

Pendiente de la copia del repositorio asignada por VantTec y del tutorial del show real. No se sustituye esa integración por una animación genérica.

## Uso de IA

Codex ayudó a interpretar documentación, revisar defectos, implementar la aplicación, generar pruebas y redactar los entregables. Las mediciones proceden del adaptador real; los fixtures de pruebas están identificados como sintéticos. La demostración no atribuye al participante acciones físicas que no confirmó.
