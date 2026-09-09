# Evaluación previa de SWARM / SIGNAL

Fecha: 9 de septiembre de 2026. Revisión del entregable antes de aplicar mejoras. Base Git: `99de7de05c98bb4597ad512aa8357204ec999e89`. Esta es una rúbrica propia de auditoría, no una calificación oficial de VantTec ni una predicción de admisión.

## Dictamen

**7.8/10 como entregable del reto base. Necesita una revisión y una prueba física para considerarlo completo.** El proyecto presenta mediciones reales, conserva errores y adapta correctamente varios problemas del tutorial. Sus cifras principales son verificables y no se atribuye precisión humana al score del algoritmo. La presentación es clara y la propuesta ocupa una cuartilla.

Todavía no merece 10/10 porque no acredita el ensayo de movimiento que exige el reto; por tanto, tampoco conoce qué tan bien detecta ese movimiento en su entorno. La propuesta identifica riesgos, pero no define un escenario suficientemente concreto ni una regla de avance experimental. Además, el arranque con una instalación incompleta falla y el diagnóstico del verificador puede profundizarse. Más animación, gráficos o pruebas sintéticas no resuelven esas carencias.

La documentación de un fallo sí tiene valor: la guía lo reconoce en su p. 6. El `FAIL` original de `./verify` no invalida toda la entrega. Aun así, impide afirmar que las ocho etapas terminaron exitosamente. **Skybrush es opcional y no resta puntos al reto base.** La defensa oral del participante no fue observada y no se califica como aprobada ni reprobada.

## Fuentes y método

- Requisitos: `SWARM_OpenLab_Reto_Software.pdf`, pp. 2–6; texto exacto en `tmp/swarm-brief/brief.txt` del workspace. Las instrucciones de la guía se interpretan como criterios del entregable, no como autorización para atribuir acciones al participante.
- Informe: `docs/SwarmSignal_Informe.pdf`, 9 pp., SHA-256 `0297501555111f73485f9c36625d11b4fce2eb333cd6ada9995c205d10b7802d`.
- Propuesta: `docs/SwarmSignal_Propuesta.pdf`, 1 p., SHA-256 `baadc4aeceff864dd2341e9b0b790af10f845f79035af670441b54931d13ae5a`.
- Evidencia: JSON de las etapas 01, 03, 04 y 06; output sanitizado de netsh; las tres sesiones guardadas; XML y resumen de verificación; captura del monitor. Se revisaron también README, DECISIONES, DEFENSA y PRUEBA_PENDIENTE.
- Se recalcularon estadísticas con `statistics` y una DFT directa con `cmath`, sin invocar el analizador del proyecto. Se contrastó el texto de las 10 páginas PDF y se inspeccionaron visualmente las páginas con gráficas, captura y propuesta. Los hashes coinciden con `evidence/pdf_qa.json`.

## Rúbrica propia

Se asigna el mismo peso al tutorial y a la propuesta, siguiendo la importancia equivalente que establece la guía en p. 6. Los pesos y descuentos son juicio de esta auditoría.

| Criterio | Peso | Puntos | Fundamento |
|---|---:|---:|---|
| Ejecución y evidencia de las ocho etapas | 40 | 30 | Se observan las lecturas, pipeline e integración; faltan el movimiento confirmado y un cierre satisfactorio del verificador. Hay detalles de arranque y evidencia literal por corregir. |
| Propuesta fundamentada y criterio SWARM | 40 | 30 | Una cuartilla, límites correctos y receptor fijo como primer paso. Falta observación física del desempeño, escenario operativo delimitado y regla experimental de avance. |
| Integridad de datos y rigor de conclusiones | 15 | 14 | Cifras recalculadas, datos reales separados de pruebas sintéticas, errores preservados. Faltan definición matemática compacta y justificación del filtro temporal. |
| Claridad y facilidad de evaluación | 5 | 4 | Documento legible y evidencia localizable. El evaluador aún debe abrir archivos auxiliares para ver el output de conectividad; la defensa escrita es general. |
| **Total** | **100** | **78** | **7.8/10. No incluye Skybrush ni acredita la capacidad oral del participante.** |

La ausencia de movimiento afecta dos dimensiones diferentes: falta una evidencia exigida en el tutorial y limita el fundamento empírico de la propuesta. No se descuentan puntos por carecer de un estudio clínico, un vuelo, localización, CSI físico o una campaña estadística grande: nada de eso es obligatorio en el reto base.

## Cumplimiento literal de las ocho etapas

| Etapa | Requisito de la guía | Estado previo | Evidencia y observación |
|---|---|---|---|
| 1 | Clonar y preparar Python/NumPy/SciPy, p. 3 | Cumplida en el equipo de ejecución | Informe p. 2; `01_environment.json`; commit upstream fijo. El reto admite Python 3.10+, y README explica por qué este paquete requiere 3.12+. El lanzador debe tolerar una instalación parcial. |
| 2 | `netsh wlan show interfaces`, captura u output **en el documento**, p. 3 | Ejecución cumplida; presentación literal parcial | `02_netsh.txt` contiene output real sanitizado. Informe p. 2 solo resume resultados. Incluir un extracto auténtico en el PDF cierra la ambigüedad sin exponer identificadores. |
| 3 | Una lectura con WindowsWifiCollector, p. 3 | Cumplida | Informe p. 2; `03_single_reading.json`: −60 dBm original. El −59 dBm de netsh es otra lectura. Calidad 0 original se explica como problema de idioma. |
| 4 | Pipeline completo durante 15 s y clasificación, p. 3 | Cumplida | Informe p. 3; `04_pipeline_15s.json`: 30 muestras, 15 s solicitados, 14.56 s entre primera y última, ACTIVE algorítmico. No se presenta como presencia confirmada. |
| 5 | Dashboard vivo mientras el participante se mueve, p. 3 | **Parcial; falta requisito físico** | Informe pp. 4–5; `monitor-live.png` muestra lectura real. Las sesiones completas y todas sus muestras tienen condición `unconfirmed`. La imagen no demuestra el movimiento pedido. Conviene conservar también la ejecución del monitor del tutorial si se usa una interfaz propia como adaptación. |
| 6 | Prueba propia con CommodityBackend y explicación, p. 3 | Cumplida | Informe p. 6; `06_commodity_backend.json`: 30 muestras reales, 5 comprobaciones; backend y aplicación analizan la misma ventana detenida. |
| 7 | Unitarias e integración con resultados y fallos, p. 3 | Cumplida con adaptación documentada | Informe p. 6; 45 unitarias actuales, 5 SKIP originales y 5 PASS tras localizar solo el precheck. Las 36 históricas no son motivo para eliminar las 9 nuevas. Las 31 propias son adicionales. |
| 8 | Ejecutar `./verify` y documentar resultado, pp. 3–4 | Ejecución documentada; éxito global pendiente | Informe p. 7; 5 PASS, 1 FAIL, 3 SKIP. CSI específico PASS con referencia sintética. No debe resumirse como «todo pasó». La guía permite documentar errores e intentos, p. 6. |

## Hallazgos priorizados

| Prioridad | Hallazgo y evidencia | Por qué importa | Mejora y criterio de cierre |
|---|---|---|---|
| P0: requisito pendiente | **No existe un ensayo físico confirmado.** Informe p. 5 y 394 muestras de las tres sesiones guardadas: todas `unconfirmed`. También son desconocidas las condiciones de las 30 muestras originales y 30 de integración. | Se cumple adquisición, pero no la demostración de movimiento de la guía. Sin referencia física no se sabe si ACTIVE fue un acierto o una falsa alarma. | Realizar con el participante el cruce frente al enlace conocido y guardar captura viva, sesión y condición verdadera. Añadir quietud como control. Conservar resultados desfavorables. La IA puede preparar y analizar; no puede ejecutar ni confirmar esa acción física por él. |
| P1: propuesta | **«Sectores accesibles después de un desastre» sigue siendo amplio.** Propuesta p. 1; informe p. 8. No queda claro dónde estarán transmisor, receptor y trayectoria esperada, ni por qué el indicio cambiaría la inspección. | Un caso genérico puede parecer una extrapolación del escritorio a rescate, aunque los límites estén bien advertidos. | Elegir un escenario experimental concreto: enlace conocido sobre un paso accesible, dron transporta/deposita el nodo y mide inmóvil. Describir quién usa la alerta y qué comprobación complementaria provoca; sin prometer encontrar víctimas inmóviles o detrás de escombros. |
| P1: decisión experimental | **El «criterio de avance» es una lista de métricas, no una regla.** Informe p. 8. | Contar errores no decide si la idea merece una segunda prueba. | Definir antes de medir una hipótesis y una puerta de avance exploratoria: contraste repetible frente a quietud, cantidad de ventanas válidas y límites acordados de falsas alarmas. Etiquetar esos límites como objetivos propuestos, no como rendimiento alcanzado ni estándar de seguridad. Si no se cumplen, detener la extrapolación y revisar geometría/tecnología. |
| P1: facilidad de ejecución | **Iniciar.ps1 falla si ya hay .venv sin NumPy.** Reproducción de la revisión técnica en `tmp/partial-install-before.log`: `ModuleNotFoundError`. | El evaluador puede recibir un enlace y no lograr abrir el laboratorio después de una instalación interrumpida. | Comprobar dependencias, reparar la instalación incompleta y mostrar el enlace solo después de que el servicio pueda arrancar. Probar ese estado concreto además de una instalación limpia. |
| P1: cierre de verificación | **El 403 fue documentado correctamente, pero el diagnóstico quedó corto.** Informe p. 7 y `12_crates_http_diagnostic.log`. La revisión técnica informa que un User-Agent identificable obtiene HTTP 200 en el primer endpoint. | No parece demostrado que el fallo sea inevitable; tampoco debe confundirse 403 con paquete inexistente. | Guardar diagnóstico reproducible y volver a ejecutar el verificador original con configuración HTTP explícita, si procede. Preservar el FAIL original y separar el nuevo entorno y resultado. Un 200 aislado no significa que todas las fases ya pasaron. |
| P1: evidencia literal | **Output de netsh fuera del PDF.** Informe p. 2; guía p. 3. | El evaluador debe reconstruir la evidencia entre varios archivos; no es la forma literal solicitada. | Incluir el extracto real sanitizado de estado, adaptador, banda, RSSI y señal, con fuente y momento. No recrearlo como una captura de ejecución nueva. |
| P2: calidad matemática | **Faltan fórmulas breves y fundamento del filtro temporal propio.** Informe pp. 3–4; DECISIONES §5. | Un evaluador puede preguntar qué significa 1.289, por qué CV 0.25 y por qué una sesión a 1.940 Hz termina sin veredicto. | Definir varianza muestral, tasa `(n−1)/cobertura`, jitter poblacional y ventana final. Explicar 14 s, 2 s y CV 25% como guardas de ingeniería iniciales; comparar su efecto sin ajustarlas retrospectivamente para producir ACTIVE. |
| P2: comparación útil | **Se grafica bien una sesión, pero no se comparan las tres conservadas.** Informe pp. 4–5. | Ya existen datos para mostrar el efecto de muestreo degradado sin inventar movimiento. | Tabla/figura compacta con tamaño, cobertura, tasa, máximo hueco y abstención final. Referirse a «sesión con muestreo degradado», sin atribuir causalmente la diferencia a carga CPU si no se registró esa carga. |
| P2: defensa y IA | **DEFENSA es una guía de respuestas, no evidencia de aprendizaje personal.** Informe p. 9; `docs/DEFENSA.md`. | El reto evalúa el manejo del participante y su criterio. Un PDF bien redactado no acredita que pueda interpretar una salida nueva. | Preparar una explicación verificable de tres decisiones de código y un ejercicio de lectura de una ventana no vista. Registrar lo que el participante realmente explique o repita. No redactar en su nombre «aprendí» o «me moví» sin confirmación. |

P0 significa que no puede cerrarse honestamente el reto completo mientras falte esa acción. P1 y P2 son prioridades de mejora del entregable, no nuevas obligaciones oficiales.

## Comprobación independiente de cifras

Las estadísticas se recalcularon desde las muestras crudas, sin importar funciones de `swarm_signal`. No se encontraron discrepancias materiales con los números publicados.

| Registro | n | Cobertura s | Tasa Hz | Media dBm | Varianza muestral dBm² | Observación |
|---|---:|---:|---:|---:|---:|---|
| Pipeline original | 30 | 14.560914 | 1.991633 | −57.766667 | 1.288506 | Coincide con informe p. 3. |
| CommodityBackend | 30 | 14.679760 | 1.975509 | −58.800000 | 0.717241 | Coincide con informe p. 6. |
| Sesión 062522 | 233 | 119.595671 | 1.939870 | −58.918455 | 1.057977 | Media/varianza de **toda** la sesión; no confundir con ventana final. |
| Sesión 063702 | 43 | 57.480455 | 0.730683 | −58.186047 | 1.488372 | Máximo hueco 3.442834 s; final inválido. |
| Sesión 064317 | 118 | 59.496496 | 1.966502 | −59.838983 | 0.717442 | Final válido; condición humana desconocida. |

- Los timestamps son únicos dentro de cada archivo; los RSSI y tiempos inspeccionados son finitos. No hay etiquetas físicas confirmadas ni un conjunto independiente de positivos/negativos.
- Ventana final de la sesión 062522: 29 muestras, cobertura 14.965116 s, tasa 1.871018 Hz, jitter `std_poblacional(intervalos)/media(intervalos) = 0.335916`, máximo hueco 1.433953 s. La tasa global y la abstención final son compatibles porque describen unidades temporales distintas.
- DFT directa de la ventana original, después de restar la media y aplicar Hann: suma de `|DFT|²/n` en 0.5–3 Hz = **1.426279756784043**, total sin DC = **6.118932395760033**. Coincide con el JSON a error numérico despreciable. Pico = 0.13277555 Hz; paso de frecuencia = 0.06638778 Hz; Nyquist = 0.99581664 Hz.
- Esa suma conserva la normalización upstream; no debe llamarse potencia física en watts ni densidad espectral calibrada. El PDF la llama energía relativa. La banda nominal de 3 Hz excede Nyquist y el documento sí lo advierte. No permite concluir respiración por tener un pico cerca de esa banda.
- XML: 45 unitarias aprobadas; integración original 5 omitidas; copia localizada 5 aprobadas; propias 31 aprobadas. Los conteos son correctos. No equivalen a 81 ensayos en personas ni a 100% de exactitud.
- SHA CSI calculado y esperado coinciden con `f8e76f21a0f9852b70b6d9dd5318239f6b20cbcb4cdd995863263cecdc446f7a`; la referencia está declarada sintética. Acredita repetibilidad de esa ejecución, no captura CSI real.

## Revisión de metodología y presentación

Los JSON conservan la granularidad necesaria para revisar el muestreo. La separación entre medición real, prueba de software, reproducción y propuesta es una fortaleza material. No se estiman sensibilidad, especificidad, precisión o causalidad con etiquetas desconocidas. Tampoco se atribuyen coordenadas o signos vitales a un único enlace RSSI. Debe mantenerse esa disciplina al mejorar el diseño.

Las gráficas tienen unidades, tamaños de muestra y referencias; el eje RSSI acotado es apropiado y no oculta un cero significativo. Se distingue cobertura real de duración solicitada. El monitor de la figura 5 pertenece a otra sesión y la leyenda lo declara. La propuesta ocupa una página legible, sin problemas visibles de composición. Una mejora científica más útil que añadir decoración sería sombrear las bandas del espectro y marcar el tramo temporal que causa abstención, con leyendas breves.

La presentación animada y las gráficas reconstruidas son material explicativo. La captura del monitor es evidencia de adquisición. Ninguna de ellas debe convertirse por su diseño en evidencia de un movimiento físico no observado. Un registro «quietud» tampoco equivale a una habitación vacía: ese matiz ya está bien establecido en PRUEBA_PENDIENTE.

## Plan para acercarse a una entrega excelente

1. Resolver el arranque parcial y completar el diagnóstico reproducible de `./verify`, conservando la procedencia anterior.
2. Añadir al informe el output real de conectividad, definiciones matemáticas mínimas y comparación de sesiones por calidad temporal.
3. Concretar la propuesta sin exceder una cuartilla: escenario, geometría del enlace, decisión que apoya, hipótesis, prueba inicial y puerta de avance. Mantener masa/energía/portabilidad como restricciones por resolver, sin inventar especificaciones del dron.
4. Preparar un protocolo que facilite el ensayo humano real y su evidencia. Repeticiones y contraste ayudan a alcanzar excelencia, pero una campaña grande no es un requisito literal del reto. No declarar el ensayo terminado por haber implementado el protocolo.
5. Incorporar y analizar el ensayo cuando el participante efectivamente lo realice. Reportar los errores que aparezcan y ajustar la propuesta a lo observado. No optimizar los umbrales con el mismo conjunto que se presenta como evaluación.
6. Validar que el participante puede ejecutar y explicar una ventana y un fallo. Su dominio oral sigue sin observarse hasta ese momento.

Las mejoras de software y documentos pueden elevar sustancialmente la calidad. **No pueden, por sí solas, acreditar una detección humana ni convertir la propuesta en una tecnología validada para rescate.** El pendiente de Skybrush permanece separado: se necesita la copia asignada por VantTec y el tutorial del show real, y solo aplica si se decide completar el reto avanzado.
