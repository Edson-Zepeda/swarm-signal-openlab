# SWARM / SIGNAL: evaluación crítica y plan de mejora

**Estado evaluado:** versión 1.0.0, commit `99de7de`. **Fecha:** 9 de septiembre de 2026. Este reporte se terminó antes de modificar la aplicación. La verificación posterior se publicará por separado.

## Dictamen

**Todavía no es un proyecto 10/10.** La evaluación documental independiente fue **7.8/10**, con una rúbrica propia y no oficial. El proyecto tiene mediciones auténticas, cálculos consistentes, una propuesta prudente y buena presentación. Sin embargo, falta una evidencia obligatoria de movimiento del participante y hay defectos de software que la batería original de 31 pruebas no cubría. No corresponde subir la nota por el número de gráficas ni por una animación adicional.

La ausencia de Skybrush **no resta puntos al reto base**: el documento lo presenta como opcional y exige recursos asignados que aún no fueron compartidos. La prueba física sí pertenece al reto obligatorio.

## Lo que impide considerarlo impecable

| Prioridad | Problema demostrado | Por qué importa | Resultado exigido a la corrección |
|---|---|---|---|
| Bloqueo de cumplimiento | Las 394 lecturas de las tres sesiones tienen condición física sin confirmar. | Una salida `active` demuestra ejecución, pero no que el participante se moviera ni que el algoritmo lo detectara correctamente. | Captura real con acción confirmada del participante y evidencia del monitor. Conservar resultados negativos; no fabricar etiquetas. |
| Alta | Una instalación interrumpida no se repara al ejecutar nuevamente el iniciador. | El proyecto funciona en el entorno del autor, pero puede fallar en el del evaluador. | Instalación limpia y recuperación de una instalación incompleta comprobadas. |
| Alta | Si falla el guardado, la sesión deja de estar activa y el siguiente intento de detener no vuelve a guardar. | Se pueden perder las mediciones más importantes del reto. | Estado de error visible, conservación de datos y reintento de guardado antes de permitir otra captura. |
| Alta | Un archivo de sesión corrupto rompe el catálogo y puede devolver un error después de haber iniciado una captura. | La interfaz y el estado real del receptor dejan de coincidir. | Aislar el archivo dañado, validar solicitudes y mantener transiciones coherentes. |
| Alta | Una señal regular de 11 muestras en 15 s se considera apta, aunque su frecuencia de Nyquist queda por debajo de toda la banda de movimiento del clasificador. | Se puede presentar un veredicto de quietud sin disponer de información para observar movimiento. | Mostrar la cobertura real de frecuencias y abstenerse cuando no existe información suficiente. |
| Alta | La exportación usa resúmenes fijos, puede acreditar archivos ausentes y cambia de referencia al encontrar una captura mayor. | La trazabilidad puede dejar de corresponder con el informe y el video. | Selección explícita, estados calculados desde evidencia existente y comprobaciones de consistencia. |
| Media | La entrada pública hace un salto automático de 342 px y esconde contexto y navegación. | El evaluador comienza por una gráfica sin saber claramente qué entrega está viendo. | Entrada en la parte superior, navegación estable y rutas directas a evidencia, propuesta y demo. |
| Media | La etapa del monitor abre JSON, los accesos a documentos están dispersos y los controles de reproducción discrepan. | Se hace difícil verificar el trabajo y usarlo en una revisión breve. | Evidencia visual directa, acciones consistentes y controles accesibles. |
| Media | El PDF resume netsh en una tabla, pero no incluye el output real solicitado; la propuesta enumera pruebas sin definir una decisión de avance. | Falta literalidad en la entrega y un criterio de ingeniería comprobable. | Output sanitizado dentro del informe y propuesta de una página con escenario, hipótesis, controles y regla de avance. |
| Media | Se detuvo el diagnóstico del HTTP 403 demasiado pronto. Una consulta que identifica explícitamente la aplicación respondió HTTP 200. | Documentar un error es válido; resolver su causa legítimamente aporta mucho más. | Repetir el verificador original con configuración documentada y conservar tanto el fallo inicial como las fases omitidas. |

## Qué debe sorprender, sin ampliar indebidamente el reto

1. **Una entrega que se pueda evaluar en minutos.** Ocho etapas con resultado, comando o procedimiento y evidencia correspondiente; enlaces directos al informe, propuesta y video.
2. **Un sistema que sabe cuándo no concluir.** Reglas de calidad explicables, cobertura de frecuencia visible y un motivo concreto cuando una ventana no admite interpretación.
3. **Una comparación reproducible de las tres capturas reales.** Contrastar muestreo, duración, variabilidad y ventanas aptas. No comparar supuesto desempeño humano entre sesiones sin etiquetas.
4. **Una propuesta de experimentación ejecutable.** Receptor fijo, transmisor conocido, quietud y cruces, repeticiones y un control que distinga movimiento del receptor. Definir qué resultado permite avanzar y cuál exige detener el desarrollo.
5. **Una demostración que se pueda defender.** Explicar RSSI, cuantización, ventana de 15 s, extracción, umbrales, sesgos y diferencia entre pruebas unitarias y validación física.
6. **Reproducción y recuperación comprobadas.** Arranque reparable, pruebas de los fallos descubiertos, evidencias históricas inmutables y descarga verificada.

Añadir IA predictiva sin datos etiquetados, declarar localización o signos vitales, simular un show ajeno al repositorio asignado o inflar una exactitud serían peores decisiones, aunque parezcan más vistosas.

## Orden de implementación

1. Corregir pérdida de evidencia, validación de datos, cobertura de frecuencias e instalación.
2. Derivar la entrega desde fuentes explícitas y preparar la comparación de capturas.
3. Corregir el recorrido web y la presentación de evidencias.
4. Refinar la propuesta y actualizar los documentos y el video a resultados coherentes.
5. Ejecutar pruebas de regresión, instalación limpia, revisión visual y comprobación de publicación/descarga.
6. Completar la evidencia física cuando el participante confirme disponibilidad. No acreditarla antes.

## Evidencia y límites de esta revisión

- [Revisión documental, rúbrica y cifras recalculadas](audit/EVALUACION_ANTES.md).
- [Revisión de instalación y entrega](audit/OPERACION_ANTES.md).
- [Revisión técnica y reproducciones](audit/TECNICA_ANTES.md).
- [Recorrido visual fresco](audit/UX_ANTES.md).
- Base normativa: `SWARM_OpenLab_Reto_Software.pdf`, páginas 2–6; [tutorial oficial](https://github.com/ruvnet/RuView/issues/36).

La nota es un juicio de revisión, no una calificación de VantTec. Las pruebas sintéticas permiten comprobar fallos del software; no se contabilizan como mediciones del WiFi ni como movimiento del participante. Corregir los defectos aumenta la calidad técnica, pero no reemplaza la evidencia física pendiente.
