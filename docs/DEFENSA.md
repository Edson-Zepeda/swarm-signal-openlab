# Defender lo que realmente se hizo

Esta guía prepara la explicación; no acredita que el participante ya la domine. Practica con el código y los registros abiertos. Conserva como pendiente cualquier acción física que todavía no hayas realizado.

## Una explicación de 90 segundos

«El adaptador mide intensidad WiFi en dBm. El programa guarda cada lectura con su tiempo y analiza ventanas de 15 segundos: variación, espectro y cambios acumulados. El clasificador aplica umbrales; ACTIVE no identifica una persona. En la captura original obtuvimos 30 muestras y varianza 1.289 dBm². No conocemos la condición humana de esa captura. Una sesión posterior tuvo muestreo irregular y el sistema se abstuvo. Por eso propongo empezar con un enlace fijo y un ensayo etiquetado, antes de llevar el sensor a un dron. Una alerta serviría para pedir una comprobación complementaria.»

Adapta el texto a lo que puedas explicar con tus palabras. No lo presentes como una experiencia física propia si no participaste en ella.

## Explicar con evidencia a la vista

| Pregunta | Respuesta que debe poder demostrarse |
|---|---|
| ¿Qué significa −60 dBm? | Es una lectura de intensidad en escala logarítmica. El paso de 1 dBm limita cambios pequeños; el archivo original conserva la muestra. No es distancia ni ubicación. |
| ¿Cómo sale 1.992 Hz? | Hay 29 intervalos entre 30 muestras. Se divide 29 entre 14.560914 s. La captura pidió 15 s; cobertura y duración solicitada no son idénticas. |
| ¿Qué significa varianza 1.289? | Se calcula la dispersión de los RSSI con divisor n−1. La unidad es dBm². No mide exactitud de presencia. |
| ¿Por qué FFT y Hann? | La FFT distribuye la variación entre frecuencias; Hann reduce fuga espectral. La señal se centra antes de calcularla. Con unos 2 Hz de muestreo solo se observa hasta aproximadamente 1 Hz, por debajo de parte de la banda nominal 0.5–3 Hz. |
| ¿Es potencia física? | El extractor suma magnitudes cuadradas normalizadas por n. Conservamos esa escala upstream; no son watts ni una densidad espectral calibrada. |
| ¿Qué hace CUSUM? | Acumula desviaciones frente al promedio para indicar cambios. Un cambio no revela su causa. Mostrar el resultado original, incluso si reporta cero cambios. |
| ¿Por qué puede no haber veredicto? | Una ventana corta, datos inválidos, huecos, irregularidad o cobertura insuficiente de frecuencias pueden impedir interpretar la señal. Mirar el motivo concreto de la ventana, no solo la tasa global. |
| ¿Qué demuestra un test aprobado? | Las unitarias usan entradas sintéticas para comprobar software; la integración prueba ejecución con el adaptador. Ninguna sustituye etiquetas humanas. La referencia CSI sintética acredita repetibilidad de su hash. |
| ¿Se detectó una persona? | Las capturas entregadas tienen condición sin confirmar. Se obtuvo una salida algorítmica; falta el ensayo físico pedido. Si se realiza después, mostrar su evidencia por separado y sus errores. |
| ¿Por qué medir con el dron apoyado? | Cambiar posición u orientación del receptor modifica el canal. La propuesta comienza fija; despegar no está validado. Un resultado negativo no declara un sector vacío. |

## Tres decisiones para recorrer en el código

1. **Leer sin inventar:** sigue desde el texto de netsh hasta una muestra. Explica cómo se reconoce Windows en español y qué sucede cuando no existe RSSI directo. El valor −80 por defecto del colector original no se usa como sustituto de una lectura fallida.
2. **Conservar antes de reemplazar:** recorre el final de una captura, el guardado y su reintento si falla. Explica por qué no debe empezar una sesión que destruya la anterior sin guardar. Localiza la prueba sintética correspondiente.
3. **Separar salida y evidencia:** encuentra dónde se comprueba la calidad antes de mostrar una clasificación y cómo el comparador evita tratar ventanas solapadas como ensayos independientes. Abre el JSON fuente y confirma sus timestamps.

Consulta los resultados vigentes en evidence/revision/ y el informe. Explica por separado el FAIL histórico del verificador y cualquier nueva ejecución, incluida su configuración y fases omitidas. No memorices un número de pruebas que pueda quedar obsoleto.

## Ensayo de defensa sin respuestas memorizadas

Elige una ventana que no hayas revisado. Antes de abrir su conclusión, cuenta muestras, calcula cobertura y tasa, localiza huecos y anticipa si merece interpretación. Después compárala con el resultado. Explica qué cambió en tu razonamiento si te equivocaste.

Abre un fallo conservado y responde: qué observaste, qué hipótesis probaste, qué cambiaste y qué evidencia descartaría tu explicación. Una respuesta «la IA lo corrigió» no demuestra comprensión.

## Uso de IA y autoría

Codex apoyó lectura del tutorial, diagnóstico, implementación, pruebas, diseño y redacción. Los registros permiten revisar las ejecuciones. Los fixtures sintéticos y la reproducción animada no se presentan como mediciones humanas. La propuesta es una hipótesis de ingeniería aún pendiente de contraste físico.

Después de practicar, el participante puede añadir una nota propia sobre lo que verificó, explicó o aprendió realmente. No hay una declaración de aprendizaje personal prellenada ni una defensa oral acreditada por este documento.
