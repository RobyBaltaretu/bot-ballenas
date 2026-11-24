// Explicación breve de cada estrategia (19/11/2026): qué hace, cómo funciona y qué persigue.
// Solo texto: no decide nada. Las claves son el nombre del módulo sin el intervalo (ruptura_4h -> ruptura).

export const EXPLICACIONES = {
  ruptura: {
    resumen: "Sube al tren cuando el precio rompe su máximo o mínimo reciente.",
    hace: "Entra en largo cuando el precio supera el máximo de las últimas N velas, o en corto cuando pierde el mínimo.",
    como: "Solo si la tendencia de fondo (media exponencial) va en el mismo sentido y la volatilidad se está despertando. El stop va a unos pocos ATR; si va bien, cobra una parte y sube el stop.",
    persigue: "Atrapar el inicio de movimientos fuertes. Acierta poco, pero cuando acierta gana varias veces lo que arriesga.",
  },
  retroceso: {
    resumen: "Compra las pausas dentro de una tendencia clara.",
    hace: "En plena tendencia, espera a que el precio retroceda hasta la media rápida y entre cuando vuelve a girar a favor.",
    como: "Exige que la tendencia sea limpia (eficiencia mínima), que las medias estén ordenadas y que la vela de giro cierre a favor.",
    persigue: "Entrar a mejor precio que con una ruptura, con un stop más corto y, por tanto, más ganancia por cada unidad de riesgo.",
  },
  reversion: {
    resumen: "Apuesta a que los excesos en un mercado lateral se corrigen.",
    hace: "Va contra el movimiento cuando el precio se aleja demasiado de su media: compra tras una caída exagerada y vende tras una subida exagerada.",
    como: "Solo si no hay tendencia (eficiencia baja), con RSI extremo y el precio muy lejos de su media, y cuando la vela ya empieza a girar. Objetivos cortos.",
    persigue: "Ganar muchas veces poco en mercados sin dirección, donde las demás estrategias de tendencia sufren.",
  },
  funding: {
    resumen: "Se pone en contra cuando casi todos apuestan al mismo lado.",
    hace: "Si el funding (lo que pagan unos traders a otros) está en un extremo histórico, opera en contra de la masa en cuanto el precio gira.",
    como: "Funding muy positivo = demasiados largos: busca un corto al perder la media rápida. Funding muy negativo = demasiados cortos: busca un largo.",
    persigue: "Aprovechar las aglomeraciones que acaban en una corrección brusca (cierres forzados de los que apostaron tarde).",
  },
  fuerza: {
    resumen: "Va largo en las monedas más fuertes y corto en las más débiles.",
    hace: "Compara todas las monedas entre sí y, cada cierto tiempo, compra las que más han subido y vende las que más han bajado en los últimos días.",
    como: "Mide el avance en ATR para que sea comparable entre monedas, reordena en cada rebalanceo y mantiene hasta el siguiente, con un stop amplio de seguridad y sin objetivo.",
    persigue: "Ganar del reparto entre ganadoras y perdedoras sin depender de si todo el mercado sube o baja.",
  },
  momentum: {
    resumen: "Sigue lo que cada moneda lleva semanas haciendo.",
    hace: "En cada rebalanceo, va a favor de la tendencia de varias semanas de la propia moneda: largo si sube con claridad, corto si baja.",
    como: "Solo si el movimiento supera un mínimo en ATR y el recorrido es limpio (eficiencia mínima). Mantiene hasta el siguiente rebalanceo, sin objetivo; el tamaño se ajusta a la volatilidad.",
    persigue: "Capturar tendencias largas y persistentes con pocas operaciones y bajos costes.",
  },
  carry: {
    resumen: "Cobra el funding sin apostar a que el precio suba o baje.",
    hace: "Abre dos patas a la vez: un corto en el perpetuo (que cobra el funding cuando es positivo) y la misma cantidad comprada al contado, que anula el movimiento del precio.",
    como: "Solo entra si el funding anual supera el listón, es positivo casi siempre, amortiza las cuatro comisiones y la base entre contado y perpetuo es pequeña. Sale si el funding se hunde, la base se abre, el contado pierde liquidez o el corto se acerca a su liquidación.",
    persigue: "Un rendimiento modesto y estable que no dependa de acertar la dirección. Su riesgo está en el margen, la base y que el funding cambie de signo.",
  },
  ballenas: {
    resumen: "Imita a las grandes cuentas cuando aumentan su posición con fuerza.",
    hace: "Vigila a las ballenas (cuentas grandes seleccionadas) y propone entrar en su misma dirección cuando su flujo es muy fuerte.",
    como: "Lee sus posiciones públicas y exige un aumento mínimo en dólares. Es una hipótesis de investigación: registra lo que habría pasado, sin operar por defecto.",
    persigue: "Comprobar si seguir el dinero grande aporta ventaja real antes de arriesgar nada con ello.",
  },
  liquidaciones: {
    resumen: "Busca rebotes tras una oleada de liquidaciones.",
    hace: "Detecta caídas bruscas del interés abierto con un movimiento de precio grande, señal de que se han liquidado muchas posiciones de golpe.",
    como: "Mide en una ventana de tiempo cuánto cae el interés abierto y cuánto se mueve el precio en ATR. Es una hipótesis de investigación: solo registra, no opera por defecto.",
    persigue: "Comprobar si tras una limpieza de posiciones el precio suele rebotar, y con qué margen.",
  },
};

/** Explicación de una clave como «ruptura_4h» (o nombre sin intervalo); undefined si no hay. */
export function explicacion(clave) {
  const nombre = String(clave).replace(/_(?=\d+[hm]$)/, "|").split("|")[0];
  return EXPLICACIONES[nombre];
}
