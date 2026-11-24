# Rediseño del panel (29/10/2026)

## Segunda versión: estilo app de bolsa (29/10/2026)

Roberto pidió un diseño más moderno, simple y limpio, en la línea de Trade Republic. Siguen siendo los mismos módulos y endpoints, sin dependencias nuevas; solo cambia la capa visual:

- **Tema claro u oscuro** según el sistema (`prefers-color-scheme`). Es blanco o negro, con el texto como color principal; verde y rojo solo para resultados, y siempre con signo y flecha. Usa la tipografía del sistema (Inter si está instalada), con cifras tabulares.
- **Navegación**: cinco pestañas (Inicio, Operaciones, Actividad, Estrategias y Más). En el móvil forman una barra inferior fija con iconos; en escritorio van arriba. Ballenas, Aprendizaje, Observabilidad, Configuración, el **modo experto** y el panel clásico están en **Más**.
- **Franja de estado** compacta: modo, «En vivo», «Retrasado» o «Sin señales», y solo lo que falla (bloqueos, incidentes, sin conexión → «Estado: desconocido»). El detalle va en Inicio.
- **Inicio**:
  - El saldo es la cifra grande, rotulada «Saldo SIMULADO (ficticio)», con su variación.
  - Debajo, un **gráfico de línea en SVG propio** hecho con `historial_saldo`, que guarda una muestra cada 5 min (unos 10 días como máximo). Periodos: 1D, 1S y Todo. Al pasar el dedo o el ratón se ven el valor y la hora de cada punto. Con menos de dos puntos no se dibuja nada y se explica por qué.
  - Después vienen «Todo en orden» o la lista de lo que requiere atención, las posiciones como lista (moneda, lado, entrada → marca, resultado, stop y su protección), un resumen en tarjetas y los avisos.
  - Plegados al final quedan los límites, el cerebro, el camino a real, los controles (pausa) y la emergencia.
- **Operaciones** y **Estrategias**: en el modo sencillo son listas tipo extracto, y los filtros quedan plegados. El modo experto vuelve a las tablas completas.
- **Diálogos**: en el móvil son hojas inferiores.

El panel nuevo está en `panel_web/`, en HTML, módulos JavaScript nativos y CSS propio. **No hay paso de compilación ni Node**: lo sirve `panel.py` desde el mismo origen. El panel antiguo sigue en **`/clasico`** como vuelta atrás.

Se decidió así porque este PC no tiene Node y Roberto eligió no instalarlo. No se usa React, Vite ni Tailwind, y no hay ninguna dependencia ni CDN.

## Cómo se activa

> **Excepción temporal (29/10/2026):** `config.json` tiene `panel.tunel_sin_clave: true` porque Roberto todavía no
> ha podido poner `PANEL_PASSWORD`. Con esa opción se entra por el túnel sin contraseña, como antes de la auditoría,
> pero en **solo lectura**: desde fuera no se manda ningún comando, ni siquiera con `comandos_remotos`.
> Hay una prueba que lo comprueba (`test_tunel_sin_clave_explicito_entra_solo_lectura`). Cuando haya contraseña en
> `.env`, la opción se ignora sola. Aun así, conviene quitarla de `config.json`.

1. **Antes de nada, si lo usas por Cloudflare Tunnel**: pon `PANEL_PASSWORD=` con una contraseña en `.env`. El `panel.py` actual rechaza (403) el acceso por túnel sin contraseña. Esto viene de la auditoría y no del rediseño, pero entra en vigor al reiniciar el panel.
2. Reinicia el panel: cierra y vuelve a abrir `INICIAR.bat` (el lanzador cierra el panel viejo y abre el nuevo). Reiniciar solo el bot con `/aplicarconfig` **no** reinicia el panel.
3. En el VPS: `sudo systemctl restart bot-ballenas-panel`.

## Construcción y paquete

- No hay construcción: los archivos de `panel_web/` se sirven tal cual. Para cambiar algo, edita el archivo y recarga la página.
- `herramientas\preparar-actualizacion.bat` ya incluye `panel_web/`, porque no tiene ningún `.json`.
- `despliegue/actualizar_vps.sh` **no copiaba** `.js`, `.css` ni `.svg`. Ya está corregido, y hay una prueba que lo vigila (`test_el_despliegue_incluye_los_archivos_del_panel`).
- Quien usa el panel no necesita Node ni nada aparte de Python.

## Servidor (`panel.py`)

| Ruta | Qué sirve | CSP | Caché |
|---|---|---|---|
| `GET /` | `panel_web/index.html` (con token y solo-lectura). Si no existe, el clásico | estricta: `script-src 'self'`, `style-src 'self'`, sin `unsafe-inline` | `no-store` |
| `GET /clasico` | `panel.html` (antiguo) | la de siempre (con `unsafe-inline`) | `no-store` |
| `GET /assets/…` | solo `panel_web/assets/**/*.{js,css,svg}`, nombres en minúscula, sin `..` y comprobando con `realpath` que no sale de la carpeta | estricta | `no-cache` (revalida) |
| `/api/*` | **sin cambios** de contrato ni de semántica | — | `no-store` |

## Contratos que usa el frontend (verificados en el código)

| Endpoint | Método | Respuesta (lo que se usa) | Autenticación | Consumidor |
|---|---|---|---|---|
| `/api/datos` | GET | `{ahora, bot: panel_datos.json, edad_datos_seg, bot_vivo, sistema_resumen, aprendizaje, resultados_comandos}` | Basic si hay `PANEL_PASSWORD`; local sin cabeceras de túnel | `estado.js` (cada 10 s), Inicio, Ballenas, Aprendizaje, Estrategias |
| `/api/operaciones` | GET | `{total, pagina, paginas, filas, resumen, problemas_ledger, valores}`; `?formato=csv` | ídem | Operaciones (filtros, paginación, CSV) |
| `/api/operacion?id=` | GET | operación del ledger (`eventos`, `ordenes`, fills, PnL…) o 404 | ídem | Detalle y cronología |
| `/api/feed` | GET | `{eventos, ultimo_seq, primer_seq_disponible, hay_mas, perdidos, bot_ts, obsoleto}` (`desde`, `limite`, `tipo`) | ídem | Actividad (carga inicial y sondeo) |
| `/api/feed/stream` | GET (SSE) | `event: evento` (id = seq), `event: estado`, `retry: 3000`, cierre a los 5 min | ídem | Actividad (EventSource) |
| `/api/feed/tipos` | GET | `{tipo: descripción}` | ídem | Actividad |
| `/api/estrategia?clave=` | GET | laboratorio, estado, vigilancia, aprendizaje y operaciones | ídem | diálogo de una estrategia |
| `/api/laboratorio` | GET | `{generado, run_id, filas:[{clave, estado, oos_*, holdout_*}]}` | ídem | Estrategias |
| `/api/observabilidad` | GET | `{ahora, sistema, incidentes, logs, componentes_log}` (`nivel`, `componente`, `traza`, `q`) | ídem | Observabilidad |
| `/api/diagnostico` | GET | JSON para descargar (sin saldo ni secretos) | ídem | Observabilidad |
| `/api/config` | GET | `{secciones, campos[{ruta, tipo, valor…}], aviso, puede_editar}` | ídem | Configuración |
| `/api/config/historial` | GET | `{cambios:[{ts, origen, cambios, copia_anterior, copia_disponible}]}` | ídem | Configuración |
| `/api/glosario` | GET | `{clave: {titulo, texto}}` | ídem | botones ⓘ |
| `/api/resultado?id=` | GET | resultado del comando o `{pendiente: true}` | ídem | confirmación de pausa, cierre y config |
| `/api/caso` | GET | sin uso en el panel nuevo (sigue disponible) | ídem | — |
| `/api/comando` | POST | `/pausa`, `/reanudar`, `/cerrarbot` (con `CERRAR-BOT` y alcance exacto) | token en cabecera, mismo origen, límite, solo local salvo `comandos_remotos` | Inicio (zona secundaria) |
| `/api/incidente` | POST | reconocer un incidente | ídem | Observabilidad |
| `/api/config` | POST | previsualizar o `confirmar: true` | ídem | Configuración |
| `/api/config/restaurar` | POST | restaurar una copia | ídem | Configuración |

**Endpoints nuevos: ninguno.** No ha hecho falta ningún dato que el backend no diera. Brechas detectadas, que quedan para más adelante y serían de solo lectura:

- La lista de posiciones no dice si **los objetivos (TP)** están verificados en el exchange, solo el stop (`stop_verificado`). Bastaría con un campo `tp_verificado` en `panel_datos.json`.
- En el ledger, el estado de la orden de entrada se queda en «aceptada» aunque luego haya fills. El panel no lo deduce: muestra el estado registrado y los fills aparte en la cronología.

## Arquitectura de información

- **Monitorización**:
  - Inicio: primero «¿requiere tu atención?»; después 6 indicadores, las posiciones con su protección y los avisos. Plegados quedan los límites, el cerebro y el camino a real. Al final van la pausa y la emergencia, también plegada.
  - Operaciones, con su detalle y cronología.
  - Actividad: bot, ballenas y mercado, fuentes, y todo junto.
- **Investigación**: Estrategias y laboratorio, Ballenas y datos externos, Aprendizaje e investigación.
- **Sistema**: Observabilidad (sin saldo ni posiciones) y Configuración.
- Una franja fija muestra el modo, si el bot está activo, la frescura, si las entradas están permitidas o bloqueadas, los incidentes y si el panel es de solo lectura. Sin conexión con el panel muestra «estado actual: desconocido».
- El modo experto añade columnas, filtros, trazas e identificadores, y los datos completos de cada operación o evento. No cambia ningún permiso.

## Matriz requisito → componente → prueba → resultado

| Requisito | Componente / archivo | Prueba | Resultado |
|---|---|---|---|
| Inspección y contratos | este documento | revisión del código de `panel.py`, `config_panel.py`, `feed.py`, `ledger.py` | hecho |
| Mismo origen, sin Node ni CDN | `panel.py` (`/`, `/assets`), `panel_web/` | `test_panel_web.test_sin_recursos_externos`, `test_raiz_sirve_el_panel_nuevo…` | OK |
| Sin path traversal; MIME y caché | `panel.asset_web`, `TIPOS_WEB` | `test_no_se_sale_de_la_carpeta…`, `test_assets_con_su_tipo…` | OK |
| CSP estricta, sin scripts ni estilos en línea | `CSP_WEB`, `index.html` | `test_html_sin_scripts_ni_estilos_en_linea` | OK |
| Vuelta atrás | `/clasico`, y `/` usa el clásico si falta `panel_web` | `test_clasico_sigue…`, `test_sin_carpeta_nueva…` | OK |
| Endpoints sin cambios | `panel.py` | `test_todos_los_endpoints_existentes_siguen_respondiendo` + las pruebas del panel existentes | OK |
| Sin `innerHTML` ni `eval`; texto con `textContent` | `dom.js` (`h`) | `test_sin_innerhtml_ni_eval` | OK |
| Imports resueltos (lo que haría un build) | todos los módulos | `test_todos_los_imports_resuelven` | OK |
| Token fuera de URL y de localStorage | `api.js` | `test_el_token_no_se_guarda…` | OK |
| Sin comandos ni rutas de escritura nuevas | vistas | `test_ninguna_ruta_nueva_de_escritura` | OK |
| Paquete y VPS incluyen el panel | `actualizar_vps.sh` | `test_el_despliegue_incluye…` | OK (corregido) |
| Inicio: atención, frescura, bloqueos, protección | `vistas/inicio.js` | `tests/web/pruebas_estados.js` (22 casos con fixtures simuladas, en el navegador) | 22/22 OK |
| Saldo simulado rotulado junto a la cifra | `inicio.js` | ídem («SIMULADO (ficticio)») | OK |
| Stop sin confirmar o sin conciliación → desconocido | `inicio.proteccion` | ídem | OK |
| Dato ausente nunca es 0 | `formato.js` | ídem | OK |
| Shadow | `inicio.js`, `app.js` | ídem (render shadow) | OK |
| Bot apagado o datos viejos | `inicio.atenciones` | ídem | OK |
| API caída | `app.pintarFranja`, `inicio.js` | manual en el navegador, parando el panel de prueba | OK |
| SSE: reconexión, sondeo, deduplicación, búfer | `vistas/actividad.js` | manual: En vivo → Desconectado → Sondeo → En vivo | OK |
| Detalle con cronología | `vistas/operaciones.js` | manual con la operación WLD real (simulada) | OK |
| Configuración: diff, aviso de riesgo, confirmación | `vistas/configuracion.js` | manual en un panel de prueba que solo deja previsualizar; `config.json` intacto (hash) | OK |
| Accesibilidad (nombres, etiquetas, foco, diálogo modal) | todas las vistas | auditoría con script en las 8 vistas: 0 botones sin nombre, 0 campos sin etiqueta | OK |
| Móvil sin scroll horizontal | `app.css` | 375 px: `scrollWidth == clientWidth` en las 8 vistas | OK (corregido en Observabilidad) |
| Pruebas Python | — | `.venv\Scripts\python -m unittest discover -s tests -t .` | **424 OK** |

Las pruebas de navegador (24 casos con el gráfico de precio) están en `tests/web/pruebas_estados.js`: con el panel abierto, se pegan en la consola (F12) y devuelven `{ok, fallos}`. No se ejecutan desde Python porque no hay motor de JavaScript sin Node.

## Limitaciones

- No hay pruebas automáticas de JavaScript en CI. Las de navegador se ejecutan a mano, y el resto se comprobó en el navegador integrado, en escritorio y a 375 px.
- Los assets se piden como `/assets/v-<huella>/...`. La huella (`panel.version_web()`) cambia al tocar cualquier archivo, así que ninguna caché (la del móvil o la de Cloudflare) puede servir JS o CSS viejos.
- Hay dos gráficos de línea, los dos con `assets/js/grafico.js`:
  - **Saldo**, en Inicio: usa `historial_saldo`, con una muestra cada 5 min.
  - **Precio de la moneda**, en el detalle de cada operación:
    - Marca la entrada, el stop y el objetivo, y en las cerradas también la salida.
    - Periodos: «Operación», 1D, 1S y 1M.
    - Los datos salen de `GET /api/velas` (solo lectura). Ese endpoint lee las velas **cerradas** de 1 h o 4 h que el bot ya archiva en `datos_archivo/velas/`, sin hacer ninguna petición al exchange. En las posiciones abiertas añade el último precio de marca de `panel_datos.json`.
    - La línea une los cierres de las velas, así que los máximos y mínimos dentro de cada vela no se ven (el gráfico lo indica).
    - Si una moneda no tiene velas archivadas para ese periodo, se avisa en lugar de dibujar.
- Las horas se muestran en la zona horaria del navegador. El ledger y los registros técnicos van en UTC, y así se indica.
- El panel clásico sigue con su CSP con `unsafe-inline` y su `innerHTML`. No se ha tocado, porque es la vuelta atrás.
