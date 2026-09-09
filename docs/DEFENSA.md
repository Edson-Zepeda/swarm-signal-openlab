# Explicarlo con tus propias palabras

**¿Qué mide realmente?** Intensidad de una conexión WiFi en dBm. No ve una silueta ni cuenta personas.

**¿Qué hace el pipeline?** Recoge RSSI, calcula características de una ventana y aplica umbrales de variación y energía espectral. Guarda muestra y tiempo para poder revisar la conclusión.

**¿Por qué FFT?** Permite estudiar cómo se distribuyen las variaciones entre frecuencias. Una ventana de Hann reduce fuga espectral. Con 2 muestras por segundo, el máximo observable es aproximadamente 1 Hz.

**¿Qué aporta CUSUM?** Busca cambios acumulados respecto al comportamiento medio. Su salida no identifica por sí sola la causa del cambio.

**¿Qué fue necesario corregir?** Rutas de importación antiguas, reconocimiento de Windows en español, RSSI faltante, calidad temporal y aislamiento entre capturas.

**¿Detectaste una persona?** Las capturas iniciales no tienen una condición física confirmada. El clasificador produjo `active`, pero eso no demuestra que el cambio se deba a una persona.

**¿Por qué aparece “sin veredicto”?** La aplicación rechaza ventanas demasiado cortas, interrumpidas o irregulares. Un número de confianza alto del algoritmo no compensa una mala medición.

**¿Pasaron todas las pruebas?** Pasaron 45 unitarias, 5 integraciones con una adaptación de idioma y 31 propias. La reproducción CSI coincide con su hash. El `./verify` ampliado conserva un error externo HTTP 403 y tres fases omitidas.

**¿Sirve mientras vuela el dron?** Todavía no está validado. Mover o girar el receptor modifica el canal; la propuesta comienza transportando el sensor y midiendo cuando está inmóvil.

**¿Qué probarías después?** Sesiones repetidas y etiquetadas de quietud, cruces de una persona y movimiento del receptor sin persona; luego otras geometrías y obstáculos. Comparar eventos omitidos, falsas alarmas y latencia.

**¿Cómo se usó IA?** Como apoyo para interpretar documentación, implementar, revisar y redactar. Los comandos y registros permiten verificar lo que se ejecutó. Revisa el código y repite el experimento antes de presentarlo como experiencia propia.
