# Prueba física para cerrar el reto

**Pendiente:** demostrar el monitoreo mientras el participante se mueve frente al equipo. El software y las capturas ambientales existentes no confirman esa acción. No cambies sus etiquetas antiguas.

## Evidencia mínima solicitada

1. Abre el laboratorio local con WiFi conectado. Coloca la laptop fija y usa un router cuya ubicación conozcas. Identifica un paso que cruce el enlace; no atribuyas esa trayectoria a una red de ubicación desconocida.
2. Inicia una captura y declara **Caminando** únicamente si vas a realizar esa condición. Cruza frente al enlace durante el registro; no muevas laptop ni router. Anota interrupciones y otras personas en movimiento.
3. Toma una captura del dashboard mientras mide. Guarda la sesión, descarga el CSV/JSON y anota lo realizado y cuándo. El nombre y la captura deben permitir reconocer el mismo registro.
4. Conserva la salida que obtengas, aunque no haya detección. La etiqueta describe la acción observada; no significa que el algoritmo acertó.

La guía pide la evidencia del monitor durante el movimiento. No exige que se invente un resultado positivo. Si la prueba falla, documenta la condición, el resultado y lo que intentaste.

## Contraste recomendado para la propuesta

| Condición | Qué mantener o realizar | Qué permite contrastar |
|---|---|---|
| Quietud | Router y receptor fijos; participante quieto. Registrar movimiento de terceros. | Variación sin el cruce pedido. No equivale a una habitación vacía. |
| Cruces | Misma geometría; participante cruza el enlace; receptor fijo. | Diferencia frente a quietud, con referencia declarada. |
| Receptor en movimiento | Sin el cruce del participante; mover o girar solo el receptor. | Confusión por el propio sensor. Si alguien lo sostiene, declararlo: no es un control puro sin persona. |

Primero realiza un par de ensayo para comprobar el procedimiento. Después fija configuración y umbrales y guarda **tres pares nuevos de 60 s**, quietud y cruces, alternando el orden entre pares. No uses el ensayo inicial para reportar rendimiento de evaluación. Los nombres pueden ser Quietud 1, Cruces 1, etc.; declara la condición real también en la interfaz.

Registra antes de cada sesión: posición relativa de router y receptor, duración, condición, repeticiones, personas próximas e incidencias. Mantén el reloj del mismo equipo. Si hay una interrupción, conserva el registro y anota el tramo; no borres solo las ventanas desfavorables.

## Regla exploratoria de avance

Analiza ventanas consecutivas de 15 s **sin solaparlas**. Informa primero cuántas son utilizables y por qué se rechazan las demás. Compara la fracción de ventanas ACTIVE dentro de cada sesión; no trates cientos de muestras de una misma sesión como cientos de ensayos independientes.

Se propone avanzar a otra geometría solo si al menos **75% de las ventanas elegibles** son aptas en cada sesión y la fracción ACTIVE es mayor en cruces que en quietud **en los tres pares**. Si no se cumple, revisar muestreo, geometría o utilidad de RSSI antes de ampliar la propuesta. No bajar retrospectivamente el criterio para declarar éxito.

El 75% y la consistencia en tres pares son decisiones exploratorias propuestas, no requisitos oficiales, precisión lograda ni umbrales de seguridad. Incluso al cumplirlos, no se valida rescate ni detección de víctimas inmóviles. Si mover el receptor produce indicios semejantes, mantenerlo fijo y estudiar ese factor antes de intentar sensado en vuelo.

## Qué entregar después

Añade la captura viva y las sesiones nuevas sin sobrescribir los registros históricos. Explica la diferencia entre la acción declarada, la salida algorítmica y la interpretación permitida. Actualiza la propuesta con lo observado, incluidos falsos indicios y omisiones. El protocolo preparado no significa que la prueba se haya realizado.

Skybrush sigue separado: es opcional y requiere la copia de repositorio asignada por VantTec y el tutorial del show real.
