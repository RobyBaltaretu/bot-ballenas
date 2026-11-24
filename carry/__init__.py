"""Carry de funding con dos patas (perpetuo corto + contado largo), PREPARADO Y SIN CONECTAR.

Nada de este paquete lo importa el bot, no decide nada y no puede enviar órdenes: trabaja con adaptadores simulados.
Va en un paquete aparte (no en la raíz) para no alterar la huella de promoción durante la prueba de dos semanas.
La fase 3 (conectarlo al bot, clasificar estos archivos en promocion.py) empieza después del 18/11/2026 y solo con la
aprobación de Roberto. Ver PLAN_CARRY.md.

  terreno.py     fase 0: qué monedas tienen contado líquido en Hyperliquid (solo lectura de la API pública)
  logica.py      fase 1: oportunidades, tamaño, riesgo de margen y reglas de salida (funciones puras)
  papel_spot.py  fase 2: cuenta de contado simulada con el libro real
  ejecucion.py   fase 2: abrir y cerrar las dos patas con deshacer/igualar si una falla
"""
