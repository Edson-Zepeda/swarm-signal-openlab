# Decisiones verificables

1. **Versión fija.** Se conserva el commit de RuView y el hash de cada módulo incluido. No se usa `main` como identidad de una ejecución.
2. **Español en Windows.** `Signal` y `Señal` se interpretan; salida UTF-8 se decodifica antes del fallback OEM. El estado e interfaz se seleccionan explícitamente.
3. **RSSI faltante.** Un error detiene la clasificación. No se rellena con -80 dBm ni se convierte porcentaje a intensidad en secreto.
4. **Datos auxiliares.** RuView genera ruido y contadores auxiliares. La interfaz y CSV solo incluyen RSSI, calidad, tiempo y etiqueta; no presentan esos auxiliares como mediciones.
5. **Ventana válida.** Al menos 14 s de cobertura para una captura nominal de 15 s, cuatro muestras como mínimo, huecos <=2 s y variación de intervalos <=25 %. Estos son controles de calidad propios, no precisión del detector.
6. **Clasificación interpretable.** Se mantienen varianza 0.3 y energía 0.1 del ejemplo de 15 s. La banda visible termina en Nyquist; la energía conserva la normalización upstream.
7. **Validación separada.** Pruebas de software sintéticas, integración con hardware, reproducción CSI y movimiento físico se reportan por separado.
8. **Publicación.** Solo registros sanitizados y capturas guardadas. El proceso que lee WiFi permanece en `127.0.0.1`.
9. **Condición física.** Sin intervención confirmada del participante, el entorno figura como `unconfirmed`. No se calcula sensibilidad o exactitud sin etiquetas.
10. **Propuesta SWARM.** Sensor transportado y luego inmóvil; ensayar cambios del receptor antes de intentar sensado en vuelo. Una alerta prioriza inspección y no confirma rescate.
