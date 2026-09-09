# Decisiones verificables

1. **Versión fija.** Se conserva el commit de RuView y el hash de cada módulo incluido. No se usa `main` como identidad de una ejecución.
2. **Español en Windows.** `Signal` y `Señal` se interpretan; salida UTF-8 se decodifica antes del fallback OEM. El estado e interfaz se seleccionan explícitamente.
3. **RSSI faltante.** Un error detiene la clasificación. No se rellena con -80 dBm ni se convierte porcentaje a intensidad en secreto.
4. **Datos auxiliares.** RuView genera ruido y contadores auxiliares. La interfaz y CSV solo incluyen RSSI, calidad, tiempo y etiqueta; no presentan esos auxiliares como mediciones.
5. **Ventana válida.** La política `2.0-quality-audit` exige al menos 14 s de cobertura, huecos <=2 s, CV de intervalos <=5 % y desviación máxima respecto al intervalo medio <=15 %. La regla histórica permitía CV<=25 % y está conservada con el experimento original. No se interpolan ni descartan silenciosamente lecturas inválidas. Estos controles conservadores no son precisión del detector.
6. **Clasificación interpretable.** Se mantienen varianza 0.3 y energía 0.1. Se requieren al menos dos bins en la parte observable de la banda original de movimiento [0.5,3] Hz. A 2 Hz esa cobertura es parcial, aproximadamente hasta 1 Hz; una banda no observada no equivale a energía cero. Con muestreo irregular no se interpreta ni muestra el espectro. La normalización original se conserva para ventanas aptas.
7. **Validación separada.** Pruebas de software sintéticas, integración con hardware, reproducción CSI y movimiento físico se reportan por separado.
8. **Publicación.** Solo registros sanitizados y capturas guardadas. El proceso que lee WiFi permanece en `127.0.0.1`.
9. **Condición física.** Sin intervención confirmada del participante, el entorno figura como `unconfirmed`. No se calcula sensibilidad o exactitud sin etiquetas.
10. **Propuesta SWARM.** Sensor transportado y luego inmóvil; ensayar cambios del receptor antes de intentar sensado en vuelo. Una alerta prioriza inspección y no confirma rescate.
11. **Comparación.** Ventanas disjuntas de 15 s. Son elegibles por su horizonte nominal dentro de la grabación observada (>=14 s), no por tener buenos datos: los huecos permanecen en el denominador. La última ventana demasiado corta se muestra como no elegible. La fracción apta no es exactitud ni probabilidad.
12. **Persistencia y reproducción.** Una captura pendiente de guardado bloquea la siguiente; el guardado puede reintentarse. Archivos dañados se aíslan y reportan. Los derivados antiguos se recalculan con la política actual sin modificar las muestras originales; las referencias publicadas se validan con SHA-256.
13. **Entorno.** Python 3.10–3.11 usa NumPy 2.2.6 y SciPy 1.15.3; Python 3.12+ conserva las versiones del experimento original. Las pruebas de compatibilidad se reportan por entorno, sin atribuirles una nueva captura física.
