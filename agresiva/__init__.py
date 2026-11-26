"""Cuenta AGRESIVA simulada (25/11/2026, pedida por Roberto): señales propias de 15 min al estilo de los canales de
señales (stop corto, cinco objetivos, apalancamiento alto) para medir con números si ese estilo es viable.

Es un experimento aparte, como el carry: proceso propio (`python -m agresiva.motor`), cuenta propia
(papel_agresiva.json), registro propio (registro/agresiva.jsonl) y sección propia del panel. Ningún archivo del bot lo
importa (una prueba lo exige), no toca papel.py, el ledger, el riesgo ni el cerebro, y no puede enviar órdenes: solo lee
la API pública de Hyperliquid y se niega a funcionar si config.json no está en modo simulado. No existe camino a real.

  logica.py    reglas de entrada, plan de la señal, tamaño, liquidación y recorrido de cada vela (funciones puras)
  cuenta.py    la cuenta agresiva y su gemela conservadora: abrir, avanzar, cerrar, frenos y quiebra
  motor.py     el proceso en vivo (velas reales de Hyperliquid, solo lectura)
  historia.py  prueba con historia de 15 min (Binance pública) y simulación de miles de secuencias (ruina)
"""
