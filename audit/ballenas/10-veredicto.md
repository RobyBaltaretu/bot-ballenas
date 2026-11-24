# 10 · Veredicto (19/11/2026)

**Estado operativo: PAPER TRADING.** La operativa simulada es técnicamente aceptable, con las limitaciones de abajo.
**No es candidato a real:** no hay ninguna estrategia con ventaja demostrada ni promovida.

**Alcance:** se inspeccionaron todos los componentes críticos (decisión, riesgo, ejecución, simulador, contabilidad y
seguridad). No se verificó la ejecución contra el exchange real (nunca se ha operado en real) ni las vulnerabilidades de
las dependencias. El laboratorio con el listón nuevo seguía en marcha al cerrar el informe: su veredicto puede cambiar
la valoración del cerebro de 4 h.

## Respuestas

1. **¿Funciona técnicamente como pretende?** Sí en lo mecánico. Las 710 pruebas pasan, el ledger cuadra con la cuenta
   (+29,25 frente a +29,24 $) y órdenes, stops y conciliación hacen lo que dicen. Hay un defecto nuevo de riesgo (D1) y
   defectos operativos.
2. **Fallos más importantes:**
   - **D1:** la ampliación se salta los bloqueos y la exposición.
   - El panel está expuesto a internet sin contraseña.
   - No hay copias de seguridad ni alertas.
   - Falta un límite agregado del escenario de salto.
   - Una operación queda abierta para siempre en el ledger (kPEPE).
   - Arranque con 10–15 min de ciclos lentos.
3. **¿Cómo funciona el cerebro?**
   - Las estrategias técnicas proponen candidatas al cierre de vela.
   - Un ridge de 8 rasgos predice la R y abre si la predicción > 0,05.
   - En simulado decide en «exploración» con un modelo sin aprobar.
   - Lo que rechaza o en lo que se abstiene, la exploración amplia lo opera al 0,5 %.
   - La memoria por vecinos ajusta el tamaño, el régimen de BTC filtra la dirección y el riesgo dimensiona.
4. **Decisiones cuestionables:**
   - Operar estrategias negativas en el laboratorio (exploración sin filtro).
   - Cinco vías de decisión mezcladas en la misma evidencia.
   - Ampliar sin pasar los controles.
   - Largos contra un mercado bajista antes del 13/11.
5. **Evidencia favorable:**
   - Prometedor sin validar: el cerebro de 4 h con datos externos (OOS t 2,97, holdout +0,071 R).
   - Estructural, sin muestra en vivo: el carry de funding.
   - Prerregistrado y esperando muestra: fuerza_4h.
6. **Sin validación:** las 13 estrategias individuales (`no_supera`; la mayoría negativas fuera de muestra), las ballenas,
   las liquidaciones y la cartera de funding.
7. **¿Por qué gana y pierde?**
   - Gana por cortos en un mercado bajista: dos operaciones de momentum a tamaño completo hacen el 78 % del beneficio.
   - Pierde en todos los largos.
   - La R media es +0,06 (t 0,26): no hay ventaja medible. El beneficio en dólares sale del reparto del tamaño.
8. **Paper frente a real:** la mecánica es la misma. Pero en real solo operaría lo promovido (hoy, nada), y el simulado opera
   por vías que en real no existen. Además, el simulado no modela latencia ni cola, y sin el bot no corren sus stops.
9. **¿Apalancamiento y riesgo seguros?** Por operación sí: el tamaño se fija por riesgo con tres escenarios y el
   apalancamiento mínimo (hoy 1× en todas). Falta acotar el salto agregado. El `piloto_real` pendiente (50 %, todos los
   mercados, 5×) es agresivo para un primer real.
10. **Riesgos de los exchanges:**
    - Un solo exchange (Hyperliquid): riesgo de plataforma y liquidez de memecoins para los stops.
    - Binance/Bybit solo como datos: si fallan, el cerebro se abstiene.
11. **¿Errores que pongan en peligro el capital?**
    - Hoy no, porque es simulado.
    - En real, D1 (si la ampliación se habilitara en real, que hoy no existe) y el salto agregado.
    - El piloto escrito con un 50 % de pérdida máxima es el riesgo de configuración más grande.
12. **Mayor impacto potencial:**
    - Validar sin sesgo el cerebro de 4 h (R-06).
    - Llevar el carry a 30 cierres.
    - Mover el bot a una máquina siempre encendida con copias y alertas.
    - Separar la evidencia por vía (R-07).
13. **Pruebas que faltan para la rentabilidad:**
    - T-Q1, T-Q2 y T-Q3 (cerebro: listón nuevo, sin historia sustituida, por régimen).
    - Las muestras prerregistradas.
    - T-P2 (calibración con real mínimo).
14. **Imprescindible para real:**
    - Una estrategia con veredicto `supera` y holdout fresco, prerregistrada.
    - Promoción con `promocion.py` y aprobación expresa de Roberto.
    - R-01, R-02, R-03, R-04 y R-05 hechos.
    - Límites del primer real decididos por escrito (R-15).
    - Máquina estable.
15. **Siguiente ciclo:**
    - Primero: R-01 y R-02 (horas).
    - Después: R-03, R-04, R-08, R-09 y R-11 (operación).
    - En paralelo: R-06 (validación del cerebro) mientras el carry acumula.
    - Sin estrategias nuevas hasta que R-06 dé veredicto.

## Puntuaciones (0–10, con su criterio)

| Dimensión | Nota | Criterio verificable |
|---|---|---|
| Arquitectura | 7 | Capas claras y fallo cerrado. Pero `bot.py` es un monolito de 2200 líneas y el estado está en archivos JSON |
| Calidad de código | 7 | 710 pruebas en verde y análisis estático limpio. Funciones muy largas (`procesar_candidatas`, unas 240 líneas) y un defecto en código nuevo |
| Motor de decisiones | 4 | Determinista y trazable, pero decide con un modelo no aprobado y cinco vías mezcladas |
| Fundamentación estratégica | 3 | Análisis técnico clásico sin ventaja; solo el carry tiene una razón estructural |
| Validación cuantitativa | 8 | Walk-forward con purga, holdout sellado, pruebas múltiples, meseta, lookahead y prerregistro. Supervivencia y sustitución de datos sin resolver |
| Ejecución | 8 | CLOID, nada de reenvíos ciegos, cancelación confirmada, stops verificados y conciliación. **N/E en real** |
| Gestión de riesgo | 6 | Fórmulas correctas y muchos controles. D1, falta el límite agregado de salto y el piloto es agresivo |
| Realismo del simulado | 6 | Libro, marca, funding y velas reales; MODELO 3. Sin latencia ni cola, foto estática y stops solo con el bot vivo |
| Seguridad | 5 | Secretos y separación de real bien hechos. Panel expuesto sin clave y dependencias sin auditar |
| Resiliencia | 5 | Reinicios, bloqueo de instancia y escrituras seguras. PC doméstico, sin copias y arranque lento |
| Observabilidad | 7 | Ledger completo por `trade_id` y salud detallada. Sin alertas externas, log sin rotación y resumen sin cerebro |
| Preparación para real | 2 | Sin estrategia promovida ni ventaja, nunca probado en real y piloto agresivo |
