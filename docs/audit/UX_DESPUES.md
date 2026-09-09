# Auditoría UX — después de las correcciones

**Fecha:** 9 de septiembre de 2026.  
**Resultado observado:** 39 de 39 comprobaciones de interfaz aprobadas en la corrida conservada del dashboard, anterior al reemplazo final del video.  
**Ejecución:** [qa.json](../../evidence/revision/ui/qa.json), navegador Edge 152 aislado, sin cuentas ni perfil personal.  
**Superficies:** servidor local real `http://127.0.0.1:8766/` y distribución estática servida bajo `/swarm-signal-openlab/`. Esta ejecución valida la revisión local; no sustituye una comprobación posterior del despliegue público.

## Qué cambió y cómo se comprobó

| Hallazgo anterior | Corrección implementada | Evidencia de cierre |
|---|---|---|
| UX01. La entrada saltaba 342 px y ocultaba la navegación. | Se eliminó el fragmento añadido durante la carga. Las vistas usan `?view=…`; los enlaces antiguos siguen funcionando. El historial restaura la vista anterior. | Entrada nueva con `scrollY=0`; enlaces de Propuesta, Evidencia y Monitor comprobados. [Entrada final](../../evidence/revision/ui/01-public-entry.png). |
| UX02. Entrega, video y propuesta estaban dispersos. | Accesos persistentes en la cabecera del contenido: entrega, video, propuesta PDF, código y ZIP. Propuesta y video también conducen a los documentos. | Navegación de entrega y regreso con el navegador; documentos y demo responden correctamente dentro de la subruta. [Evidencia](../../evidence/revision/ui/04-evidence.png). |
| UX03. La página pública no explicaba cómo medir. | «Medir en mi equipo» abre tres pasos: extraer el ZIP, abrir `Iniciar.cmd` y declarar únicamente la condición observada. Distingue reproducción pública y receptor local. | Diálogo con nombre accesible, foco interior, Escape y devolución del foco comprobados. [Ayuda](../../evidence/revision/ui/03-local-help.png). |
| UX04. La etapa 5 llevaba únicamente a JSON. | La tarjeta muestra y enlaza la captura real del monitor; conserva los datos originales como enlace separado. Los demás artefactos aceptan imagen, código o log. | La imagen responde correctamente; las ocho tarjetas y el conteo se derivan del archivo actual. La etapa física permanece parcial. |
| UX05. El botón principal no permitía pausar. | La acción principal alterna entre reproducción y pausa, en sincronía con el control del gráfico. | Reproducción a 8×, pausa estable, siete posiciones y correspondencia exacta de muestras y análisis registrados. |
| UX06. Un «Sin veredicto» no ofrecía un siguiente paso. | El criterio conduce al comparador de tres capturas reales o a la preparación de otra captura. Errores de conexión retienen el último dato con un estado explícito. Un guardado fallido conserva «Reintentar guardado». | Comparador verificado contra sus fuentes. Desconexión, recuperación y guardado se probaron con estados controlados de interfaz; no representan experimentos físicos. [Comparador](../../evidence/revision/ui/02-comparison.png). |
| UX07. Los gráficos no identificaban la ventana interpretada. | Se marca el intervalo de hasta 15 s en RSSI y se repite en el espectro. La varianza móvil conserva su ventana de 5 s y la tarjeta explica que usa la captura. No se reconstruye una FFT que el análisis haya rechazado. | Posiciones de reproducción verificadas contra los frames exportados. Donde la fuente no aporta espectro, se dibujan cero barras. |
| UX08. Faltaban nombres y valores útiles para interacción accesible. | El deslizador anuncia segundos actuales y totales. Los diálogos están nombrados; captura enfoca su nombre y vuelve a «Sin etiqueta» al abrir otra sesión. Los enlaces de evidencia incluyen la etapa en su nombre accesible. | Teclado, foco, selección explícita de adaptador y condición física comprobados. Axe no detectó incidencias en las superficies revisadas. |

## Evidencia cuantitativa de la revisión

- **39/39 comprobaciones aprobadas**, incluyendo doce combinaciones de ancho y vista: 320, 390, 768 y 1440 px para Monitor, Evidencia y Propuesta. Demo se comprobó además a 320, 390 y 768 px.
- **Sin desbordamiento horizontal global.** En móvil, la tabla de comparación se transforma en registros apilados para mantener visibles muestras, frecuencia, irregularidad y ventanas válidas.
- Texto base de **16 px**; etiquetas principales y ejes de **14 px** en las medidas verificadas. Se respeta la preferencia de movimiento reducido.
- **233 muestras reales y 233 frames** en la reproducción pública; la descarga CSV conserva las 233 filas. El deslizador se contrastó en siete posiciones.
- El comparador muestra **233, 43 y 118 muestras**; ventanas aptas/elegibles **3/8, 0/3 y 2/4**, respectivamente. Son métricas de calidad técnica; no son exactitud ni comparaciones entre personas quietas y caminando.
- La matriz actual muestra **7/8 etapas verificadas** y mantiene parcial la confirmación del movimiento físico. El estado se lee de los artefactos actuales, sin fijarlo en la interfaz.
- La corrida conservada incluye el video anterior de **104.8 s**, **1920 × 1080**, capítulos funcionales, audio decodificado y subtítulos en español. La comprobación del reemplazo multimedia se registra separadamente en `demo-qa.json`; no se modifica el resultado histórico de 39/39.
- **Cero excepciones JavaScript** y cero fallos de recursos estáticos solicitados. La prueba de subruta en localhost registra por separado el intento esperado de encontrar una API local; el host público omite ese intento.

## Comprobación adicional del video local

El recorrido de 39/39 había probado el video mediante el servidor estático de QA, que admite solicitudes parciales. Una comprobación adicional sobre el servidor real del proyecto descubrió que los capítulos volvían al inicio: al solicitar 46.9 s, el reproductor estaba en 2.51007 s después de esperar. El archivo sí decodificaba; faltaba soporte de rangos HTTP en su entrega local. Se conservan el [resultado fallido de 6/7](../../evidence/revision/ui/demo-before-range.json) y el [diagnóstico observado](../../evidence/revision/ui/local-video-range-before.json).

Tras corregir el servidor, la prueba del mismo recorrido pasó **7/7**: el capítulo de 46.9 s avanzó hasta **48.710068 s**, con audio decodificado, sin error del reproductor y con los nueve capítulos alineados. Esta prueba utilizó el clip de 108 s y se conserva en [demo-range-fixed.json](../../evidence/revision/ui/demo-range-fixed.json).

El reemplazo final, con los resultados actualizados de las pruebas de software, volvió a pasar **7/7** sobre el servidor real: **108.3 s**, **1920 × 1080**, nueve capítulos, audio y subtítulos. El contenedor dura 108.3 s; el timeline de video tiene 108.266667 s. Se verificó que ambos coinciden dentro de un fotograma aproximadamente. El resultado final está en [demo-qa.json](../../evidence/revision/ui/demo-qa.json) y la [captura del reproductor final](../../evidence/revision/ui/07-demo-updated.png). La navegación móvil y Axe conservaron sus resultados sin incidencias.

## Comparación visual

Ambas entradas usan un viewport de **1440 × 900**. Se conservan los originales de la auditoría anterior.

| Antes | Después |
|---|---|
| [Entrada que ocultaba cabecera y navegación](screens/01-public-entry.png) | [Entrada completa y acceso a entrega](../../evidence/revision/ui/01-public-entry.png) |
| [Evidencia anterior](screens/03-evidence.png) | [Evidencia con artefactos diferenciados](../../evidence/revision/ui/04-evidence.png) |
| Sin comparación conjunta de capturas | [Comparador con métricas reales](../../evidence/revision/ui/02-comparison.png) |

Capturas complementarias: [Monitor móvil](../../evidence/revision/ui/monitor-390.png), [Evidencia móvil](../../evidence/revision/ui/evidencia-390.png), [Propuesta](../../evidence/revision/ui/05-proposal.png), [video](../../evidence/revision/ui/06-demo.png). Las capturas de esta revisión se abrieron e inspeccionaron visualmente; muestran reproducción o interfaz, nunca una nueva ejecución física declarada como evidencia.

## Límites que permanecen

La mejora de experiencia no verifica presencia humana, respiración, pulso ni despliegue en drones. Ninguna de las tres condiciones físicas se confirmó durante esta auditoría. No se inició una captura real desde la suite de interfaz; las pruebas de solicitudes de inicio y fallos usaron respuestas controladas, identificadas como `fixtureOnly` en el JSON.

Los resultados de Axe y teclado no equivalen a una certificación WCAG ni a una sesión completa con lector de pantalla. Tampoco son una prueba con reclutadores reales. El arranque, las pruebas científicas, las dependencias y el cumplimiento íntegro del PDF tienen evidencias separadas. La revisión corrige las barreras observadas sin justificar una calificación perfecta.

## Reproducción de la comprobación

Con las dependencias de desarrollo instaladas y el receptor local iniciado, ejecutar `npm run test:ui`. La suite actual es `scripts/verify_revision_ui.cjs`; guarda sus resultados en `evidence/revision/ui/` y conserva los informes históricos de `evidence/ui/`. Las rutas de dependencias y el ejecutable del navegador se pueden especificar mediante `SWARM_NODE_MODULES`, `SWARM_AXE_PATH` y `SWARM_BROWSER_EXECUTABLE`; no se utiliza un perfil personal.
