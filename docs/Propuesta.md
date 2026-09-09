# Un nodo que llega con el dron

Proponemos ensayar un enlace WiFi sobre un paso despejado de un simulacro: router propio a un lado y receptor fijo al opuesto. Un dron de SWARM transportaría y depositaría el nodo; mediría inmóvil. La hipótesis es que los cruces humanos produzcan más ventanas ACTIVE que la quietud. Una alerta pediría inspección complementaria; no identificaría personas ni declararía un sector vacío.

La ventana original tuvo 30 muestras, 14.56 segundos de cobertura y 1.992 Hz; produjo ACTIVE con varianza 1.289 dBm². No hubo condición humana confirmada. En la sesión de 233 muestras, la ventana final se rechazó por irregularidad temporal. Observamos funcionamiento y límites de muestreo, pero todavía no eficacia de detección humana.

Tras un par de ensayo, fijaremos geometría y configuración. Compararemos tres pares nuevos de 60 segundos, quietud y cruces, alternando el orden; registraremos también el movimiento del receptor como posible confusor. Usaremos ventanas de 15 segundos sin solapamiento. Avanzaremos a otra geometría solo si al menos 75% de las ventanas elegibles son aptas en cada sesión y la fracción ACTIVE es mayor durante cruces en los tres pares. Si no se cumple, revisaremos muestreo, geometría o utilidad del RSSI. Esta regla es exploratoria, no exactitud alcanzada ni un estándar de seguridad.

Mover o girar el receptor cambia el canal; el control de vuelo no elimina ese efecto. Integrarlo exige portar el colector Windows, evaluar masa y energía, sincronizar telemetría y descartar mediciones durante desplazamientos. La cuantización de 1 dBm y el muestreo cercano a 2 Hz limitan la información: no se validan coordenadas, signos vitales, víctimas inmóviles ni alcance entre escombros. Sensar en vuelo o usar CSI requiere experimentos posteriores. La decisión de rescate seguirá en manos del equipo humano.

Estado: propuesta experimental; movimiento humano no confirmado.
