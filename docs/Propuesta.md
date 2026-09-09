# Un nodo que llega con el dron

Proponemos evaluar un nodo WiFi transportado por un dron de SWARM para priorizar la inspección de sectores accesibles después de un desastre. El dron coloca el nodo o se apoya, y un transmisor controlado establece el enlace. El sistema registra ventanas de 15 segundos y entrega alertas para una inspección complementaria. No identifica personas ni certifica que un sector esté vacío.

La prueba original registró 30 muestras en 14.56 segundos entre primera y última lectura, a 1.992 Hz. El RSSI medio fue -57.77 dBm, con varianza 1.289 dBm², y el clasificador produjo ACTIVE. Como no hubo etiquetas físicas, no podemos atribuir esa salida a movimiento humano. En la sesión extendida de 233 muestras, la ventana final se rechazó por muestreo irregular. Ambas observaciones justifican controlar la calidad antes de emitir una alerta.

El primer ensayo usaría receptor inmóvil. Desplazarlo o girarlo modifica la propagación; el control de vuelo no elimina ese factor. Compararemos quietud, cruces humanos y movimiento del receptor sin personas, con etiquetas sincronizadas, repeticiones y calibración separada de la evaluación. Después variaremos obstáculos y geometrías. Registraremos aciertos, omisiones, falsas alarmas, latencia y muestras perdidas antes de proponer alcance operativo.

La integración requiere portar el colector Windows a un nodo ligero, sincronizar telemetría, evaluar masa y energía, disponer de transmisor propio y descartar ventanas durante desplazamientos. El RSSI cuantizado y el muestreo cercano a 2 Hz limitan la información; un único enlace no ofrece coordenadas ni signos vitales confiables. CSI y varios receptores serían una etapa posterior con validación independiente. El beneficio esperado es aportar evidencia complementaria para decidir dónde inspeccionar primero, manteniendo la decisión final en el equipo de rescate.

Estado: propuesta experimental; movimiento humano no confirmado.
