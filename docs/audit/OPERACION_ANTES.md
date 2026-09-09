# Auditoría inicial: instalación, entrega y reproducción

Evaluación del estado `99de7de`, antes de aplicar las correcciones. Fecha: 9 de septiembre de 2026. Este documento registra hallazgos; no presenta los cambios propuestos como realizados.

| Prioridad | Hallazgo confirmado | Consecuencia | Corrección verificable |
|---|---|---|---|
| Alta | `Iniciar.ps1` instala dependencias únicamente si no existe `.venv/Scripts/python.exe`. Una interrupción deja una instalación que no se repara. | El evaluador no puede abrir el proyecto, aunque las pruebas del entorno del autor pasen. | Comprobar Python y dependencias siempre; reparar solo lo faltante, devolver error real y verificar el arranque desde una instalación limpia y una incompleta. |
| Alta | `scripts/export_web.py` elige la captura con más muestras, fija `ground_truth=unconfirmed` y contiene cifras/estados del tutorial escritos a mano. | Una nueva captura puede cambiar la demostración sin decisión explícita; el estado de entrega puede quedar desactualizado. | Fijar la sesión de referencia en un manifiesto y derivar números/estados de sus archivos, con comprobaciones de integridad y procedencia. |
| Media | `run_tutorial.py` y `check_backend.py` vuelven a escribir los archivos originales del tutorial. | Al reproducir la prueba se puede perder la evidencia que sustenta el informe y el video. | Crear una carpeta distinta por ejecución; mantener la referencia publicada inmutable. |
| Media | Dependencias de ejecución, pruebas y producción documental están juntas; no hay instalación automatizada de prueba desde cero. | Se instala más de lo necesario y no existe evidencia de que otro entorno pueda ejecutar la entrega. | Separar dependencias por uso y verificar una instalación limpia; automatizar comprobaciones del núcleo y la entrega. |
| Media | El empaquetador escribe siempre en la misma carpeta y el estado físico está fijado a `pending`. | Una publicación nueva puede mezclar archivos anteriores o conservar un estado obsoleto. | Versionar la carpeta de entrega y derivar el estado del manifiesto. Validar el ZIP completo y su descarga pública. |
| Media | El HTTP 403 del verificador se documentó, pero faltaba identificar la causa antes de darlo por externo. | Se abandona una posible solución legítima y reproducible. | Usar la identificación de cliente exigida por la API, registrar configuración y ejecutar el verificador original; conservar el FAIL histórico y cada SKIP. |

## Reproducciones efectuadas

1. Se creó un entorno virtual vacío en una copia temporal de la aplicación y se ejecutó el iniciador original. Imprimió la dirección del laboratorio, omitió instalar dependencias y terminó con `ModuleNotFoundError: No module named 'numpy'`. Registro: `tmp/partial-install-before.log`.
2. La resolución limpia de `requirements.txt` con Python 3.12 sí encontró las versiones publicadas de NumPy, SciPy y demás dependencias. Esto descarta que los números de versión sean el problema del iniciador. Registro: `tmp/install-audit.json`.
3. La consulta de solo lectura a `https://crates.io/api/v1/crates/wifi-densepose-core`, con `User-Agent: SwarmSignal/1.1 (+https://github.com/Edson-Zepeda/swarm-signal-openlab)`, devolvió HTTP 200. Es una identificación explícita de la aplicación, sin credenciales ni alteración de fuentes. No equivale todavía a que las nueve fases de `./verify` hayan pasado. Registro: `tmp/crates-api-before.json`.

## Fuentes consultadas

- [Tutorial oficial vigente](https://github.com/ruvnet/RuView/issues/36).
- [Política de acceso de crates.io](https://crates.io/data-access).
- [Incidencia sobre identificación de clientes en crates.io](https://github.com/rust-lang/crates.io/issues/13783).
- [NumPy 2.5.3](https://pypi.org/project/numpy/2.5.3/) y [SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/).

## Alcance

Instalar Rust, arrancar Docker, añadir modelos de aprendizaje automático o crear una animación de drones ajena al repositorio asignado no resuelve los requisitos pendientes del reto base. La mejora con mayor valor es asegurar una prueba humana documentada, una propuesta contrastable y una entrega fácil de comprobar.
