// Núcleo 3D de la portada (18/11/2026, pedido por Roberto; mejorado el mismo día): un «cerebro» de partículas con
//   · esfera exterior y núcleo interior que late (más rápido cuando llegan novedades),
//   · constelación: líneas finas entre partículas vecinas, como una red neuronal,
//   · tres anillos giroscópicos en 3D con un satélite cada uno,
//   · hilos de datos de las fuentes a la esfera y de la esfera a los resultados, con pulsos que viajan,
//   · ONDAS que recorren la esfera cuando el bot hace algo (señal, entrada, error…, vía el bus de eventos),
//   · polvo de fondo con paralaje y una entrada animada,
//   · interacción: sigue al cursor, se arrastra para girarla (con inercia) y un clic lanza una onda.
// Las cifras de las columnas son datos reales del bot; la esfera es decoración. Canvas 2D propio, sin librerías
// ni recursos externos (CSP estricta). ~30 fps, menos partículas en móvil, se para fuera de pantalla, con la pestaña
// oculta y con «reducir movimiento» (entonces dibuja un solo fotograma).

import {alEvento, reducido} from "./anim.js";
import {h, reemplazar} from "./dom.js";
import {hay, num, pct} from "./formato.js";

const AUREO = Math.PI * (3 - Math.sqrt(5));
const suave = (t) => 1 - Math.pow(1 - t, 3);

function puntosEsfera(n, radio = 1) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const y = 1 - (i / (n - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const a = AUREO * i;
    out.push([Math.cos(a) * r * radio, y * radio, Math.sin(a) * r * radio, Math.random() * Math.PI * 2]);
  }
  return out;
}

/** Pares de vecinos más cercanos entre un subconjunto de puntos (la «red neuronal»). */
function constelacion(puntos, cuantos, vecinos = 2) {
  const paso = Math.max(1, Math.floor(puntos.length / cuantos));
  const idx = [];
  for (let i = 0; i < puntos.length; i += paso) idx.push(i);
  const pares = new Set();
  for (const i of idx) {
    const cerca = idx.filter((j) => j !== i).map((j) => {
      const dx = puntos[i][0] - puntos[j][0], dy = puntos[i][1] - puntos[j][1], dz = puntos[i][2] - puntos[j][2];
      return [dx * dx + dy * dy + dz * dz, j];
    }).sort((a, b) => a[0] - b[0]).slice(0, vecinos);
    for (const [, j] of cerca) pares.add(i < j ? `${i}-${j}` : `${j}-${i}`);
  }
  return [...pares].map((p) => p.split("-").map(Number));
}

function anillo3d(n, radio) {
  return Array.from({length: n}, (_, k) => {
    const a = k / n * Math.PI * 2;
    return [Math.cos(a) * radio, 0, Math.sin(a) * radio];
  });
}

function rotar(p, ax, ay, az) {
  let [x, y, z] = p;
  let c = Math.cos(ax), s = Math.sin(ax);
  [y, z] = [y * c - z * s, y * s + z * c];
  c = Math.cos(ay); s = Math.sin(ay);
  [x, z] = [x * c + z * s, -x * s + z * c];
  c = Math.cos(az); s = Math.sin(az);
  [x, y] = [x * c - y * s, x * s + y * c];
  return [x, y, z];
}

function color(nombre) {
  return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
}

function nodo(clase, etiqueta, valor, pie, vivo) {
  return h("div", {clase: ["nodo", clase, vivo ? "vivo" : null]},
    h("div", {clase: "fila-nodo"}, h("span", {clase: "etq"}, etiqueta), h("span", {clase: "v"}, valor)),
    pie ? h("div", {clase: "pie"}, pie) : null);
}

// Color de la onda según lo que ha pasado.
const ONDA = {entrada: "vivo", decision_aprobada: "vivo", orden_completada: "vivo", cierre: "vivo", fuente_recuperada: "vivo",
  senal_detectada: "sal", decision_rechazada: "p", ballena_fill: "cian", ballena_cambio_inferido: "cian",
  error: "rojo", alerta: "rojo", fuente_perdida: "rojo", liquidacion_inferida: "ambar", stop_movido: "ambar", proteccion: "ambar"};

export function crearNucleo() {
  const canvas = h("canvas", {"aria-hidden": "true"});
  const entradas = h("div", {clase: "columna entradas"});
  const salidas = h("div", {clase: "columna salidas"});
  const centro = h("div", {clase: "centro-nucleo"});
  const cabeza = h("div", {clase: "cabeza"});
  const leyenda = h("div", {clase: "leyenda"});
  const el = h("section", {clase: "nucleo", "aria-label": "Núcleo del bot: fuentes de datos y resultados"},
    canvas, cabeza, h("div", {clase: "cuerpo-nucleo"}, entradas, centro, salidas), leyenda);

  let puntos = [], interior = [], pares = [], aros = [], polvo = [];
  let ang = 0, vel = 0.0042, tilt = 0.38, giro = 0;                       // giro: velocidad extra por arrastre (inercia)
  const mira = {x: 0, y: 0, ox: 0, oy: 0};                                  // cursor normalizado -1..1 y su versión suavizada
  let vivo = true, salud = "ok", visible = true, anclas = null, colores = {}, raf = null, ultimo = 0, marcos = 0;
  const t0 = performance.now();
  const ondas = [];                                                         // {t, color, fuerza}
  const chispas = [];                                                       // pulsos extra por los hilos
  let latido = 0;                                                           // 0..1, brillo del núcleo interior
  let actividad = 0;                                                        // sube con cada evento y decae

  function medir() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = el.getBoundingClientRect();
    if (!r.width) return;
    canvas.width = Math.round(r.width * dpr);
    canvas.height = Math.round(r.height * dpr);
    const estrecho = r.width < 640;
    const n = estrecho ? 420 : 900;
    if (puntos.length !== n) {
      puntos = puntosEsfera(n);
      pares = constelacion(puntos, estrecho ? 70 : 130);
      interior = puntosEsfera(estrecho ? 70 : 130, 0.42);
      aros = [{pts: anillo3d(72, 1.28), ax: 1.2, az: 0.2, v: 0.9}, {pts: anillo3d(84, 1.44), ax: 0.4, az: 1.1, v: -0.6},
        {pts: anillo3d(96, 1.6), ax: 2.1, az: -0.5, v: 0.4}];
      polvo = Array.from({length: estrecho ? 26 : 60}, () => ({x: Math.random(), y: Math.random(), z: 0.3 + Math.random() * 0.7, v: 0.02 + Math.random() * 0.05}));
    }
    const rel = (x) => { const q = x.getBoundingClientRect(); return {x: (q.left - r.left) * dpr, y: (q.top - r.top) * dpr, w: q.width * dpr, h: q.height * dpr}; };
    const c = rel(centro);
    const radio = Math.max(40 * dpr, Math.min(c.w * 0.30, c.h * 0.36));
    anclas = {
      dpr, w: canvas.width, h: canvas.height, cx: c.x + c.w / 2, cy: c.y + c.h / 2 - 14 * dpr, radio,
      ent: estrecho ? [] : [...entradas.children].map((n2) => { const q = rel(n2); return {x: q.x + q.w, y: q.y + q.h / 2}; }),
      sal: estrecho ? [] : [...salidas.children].map((n2) => { const q = rel(n2); return {x: q.x, y: q.y + q.h / 2}; }),
    };
    colores = {p: color("--particula") || "190, 225, 235", vivo: color("--vivo") || "#3ddc97", sal: color("--enlace") || "#6fd6ff",
      ambar: color("--ambar") || "#f2b84b", rojo: color("--rojo") || "#ff6b5e", cian: "#5ee6e0"};
  }

  function tinte() {                                   // color «de marca» del núcleo según la salud del bot
    return salud === "mal" ? colores.rojo : salud === "aviso" ? colores.ambar : colores.vivo;
  }

  function curva(ctx, a, b) {
    const mx = (a.x + b.x) / 2;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.bezierCurveTo(mx, a.y, mx, b.y, b.x, b.y);
    ctx.stroke();
    return (t) => {                                    // punto de la curva en t ∈ [0, 1] (Bézier cúbica)
      const u = 1 - t;
      return [u * u * u * a.x + 3 * u * u * t * mx + 3 * u * t * t * mx + t * t * t * b.x,
        u * u * u * a.y + 3 * u * u * t * a.y + 3 * u * t * t * b.y + t * t * t * b.y];
    };
  }

  function proyectar(p, ca, sa, ci, si, radio, cx, cy, resp = 1) {
    const x1 = p[0] * ca + p[2] * sa, z1 = -p[0] * sa + p[2] * ca;
    const y2 = p[1] * ci - z1 * si, z2 = p[1] * si + z1 * ci;
    return [cx + x1 * radio * resp, cy + y2 * radio * resp, (z2 + 1) / 2, z2];
  }

  function dibujar(t) {
    const ctx = canvas.getContext("2d");
    if (!anclas || !ctx) return;
    const {dpr, w, h: alto, cx, cy} = anclas;
    const nace = suave(Math.min(1, (t - t0) / 1500));                      // entrada animada
    const radio = anclas.radio * (0.55 + 0.45 * nace);
    ctx.clearRect(0, 0, w, alto);
    ctx.globalAlpha = nace;
    const marca = tinte();

    // Polvo de fondo con paralaje (se mueve con el cursor y deriva hacia arriba).
    for (const m of polvo) {
      m.y -= m.v * 0.0016 * 16;
      if (m.y < -0.02) { m.y = 1.02; m.x = Math.random(); }
      const px = (m.x + mira.ox * 0.03 * m.z) * w, py = (m.y + mira.oy * 0.02 * m.z) * alto;
      ctx.fillStyle = `rgba(${colores.p}, ${(0.08 + 0.3 * m.z * (0.5 + 0.5 * Math.sin(t / 900 + m.x * 9))).toFixed(3)})`;
      ctx.fillRect(px, py, 1.4 * dpr * m.z, 1.4 * dpr * m.z);
    }

    // Hilos de datos: entradas -> esfera -> salidas, con pulsos que viajan (más rápidos con actividad).
    ctx.lineWidth = 1 * dpr;
    ctx.strokeStyle = `rgba(${colores.p}, ${(0.13 + actividad * 0.12).toFixed(3)})`;
    const borde = (p) => {
      const a2 = Math.atan2(p.y - cy, p.x - cx);
      return {x: cx + Math.cos(a2) * radio * 1.02, y: cy + Math.sin(a2) * radio * 1.02};
    };
    const hilos = [...anclas.ent.map((p) => ({f: curva(ctx, p, borde(p)), dentro: true})),
      ...anclas.sal.map((p) => ({f: curva(ctx, borde(p), p), dentro: false}))];
    const ritmo = vivo ? 2600 / (1 + actividad * 1.4) : 9000;
    hilos.forEach((hi, k) => {
      for (const desfase of [0, 0.5]) {
        const fase = ((t / ritmo) + k * 0.17 + desfase) % 1;
        const [x, y] = hi.f(fase);
        ctx.fillStyle = vivo ? (hi.dentro ? marca : colores.sal) : colores.ambar;
        ctx.globalAlpha = nace * Math.sin(fase * Math.PI) * 0.9;
        ctx.beginPath();
        ctx.arc(x, y, 1.8 * dpr, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    // Pulsos extra lanzados por eventos reales: viajan por un hilo hacia la esfera (señales) o hacia fuera (resultados).
    for (let i = chispas.length - 1; i >= 0; i--) {
      const c = chispas[i];
      const k = (t - c.t) / 1100;
      if (k >= 1 || !hilos[c.hilo]) { chispas.splice(i, 1); continue; }
      const kk = hilos[c.hilo].dentro ? k : k;
      for (let tr = 0; tr < 5; tr++) {                                   // estela
        const [x, y] = hilos[c.hilo].f(Math.max(0, kk - tr * 0.03));
        ctx.fillStyle = colores[c.color] || marca;
        ctx.globalAlpha = nace * (1 - tr / 5) * Math.sin(Math.min(1, kk * 1.2) * Math.PI) ;
        ctx.beginPath();
        ctx.arc(x, y, (3.2 - tr * 0.4) * dpr, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = nace;

    // Halo suave detrás de la esfera, que respira con el latido.
    const halo = ctx.createRadialGradient(cx, cy, radio * 0.15, cx, cy, radio * (1.7 + latido * 0.15));
    halo.addColorStop(0, `rgba(${colores.p}, ${(vivo ? 0.16 + latido * 0.1 : 0.05).toFixed(3)})`);
    halo.addColorStop(1, `rgba(${colores.p}, 0)`);
    ctx.fillStyle = halo;
    ctx.fillRect(cx - radio * 1.9, cy - radio * 1.9, radio * 3.8, radio * 3.8);

    // Rotaciones: giro propio + inclinación que sigue al cursor.
    const inc = tilt + mira.oy * 0.35;
    const a = ang + mira.ox * 0.5;
    const ci = Math.cos(inc), si = Math.sin(inc), ca = Math.cos(a), sa = Math.sin(a);

    // Anillos giroscópicos: tres circunferencias en 3D, cada una girando a su ritmo, con un satélite.
    aros.forEach((ar, k) => {
      const rot = (t / 4000) * ar.v;
      let prev = null;
      ctx.lineWidth = 1 * dpr;
      for (let i = 0; i <= ar.pts.length; i++) {
        const q = rotar(ar.pts[i % ar.pts.length], ar.ax + rot * 0.3, rot, ar.az);
        const [px, py, prof] = proyectar(q, ca, sa, ci, si, radio, cx, cy);
        if (prev) {
          ctx.strokeStyle = `rgba(${colores.p}, ${(0.05 + prof * 0.2).toFixed(3)})`;
          ctx.beginPath();
          ctx.moveTo(prev[0], prev[1]);
          ctx.lineTo(px, py);
          ctx.stroke();
        }
        prev = [px, py];
      }
      const idx = Math.floor((t / (vivo ? 90 : 340) * (k % 2 ? -1 : 1)) % ar.pts.length + ar.pts.length) % ar.pts.length;
      const sat = rotar(ar.pts[idx], ar.ax + rot * 0.3, rot, ar.az);
      const [sx, sy, sp] = proyectar(sat, ca, sa, ci, si, radio, cx, cy);
      ctx.fillStyle = k === 1 ? colores.sal : k === 2 ? colores.cian : marca;
      ctx.globalAlpha = nace * (0.35 + sp * 0.65);
      ctx.beginPath();
      ctx.arc(sx, sy, (1.6 + sp * 1.6) * dpr, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = nace;
    });

    // Constelación: líneas entre vecinos, más visibles al frente y con destellos viajando.
    const proy = new Array(puntos.length);
    for (let i = 0; i < puntos.length; i++) {
      const p = puntos[i];
      const resp = 1 + 0.018 * Math.sin(t / 900 + p[3]) + latido * 0.012;
      proy[i] = proyectar(p, ca, sa, ci, si, radio, cx, cy, resp);
    }
    ctx.lineWidth = 0.8 * dpr;
    for (const [i, j] of pares) {
      const A = proy[i], B = proy[j];
      const prof = (A[2] + B[2]) / 2;
      if (prof < 0.42) continue;                                          // solo la cara visible
      const onda = (Math.sin(t / 700 + i * 0.7) + 1) / 2;
      ctx.strokeStyle = `rgba(${colores.p}, ${(0.06 + prof * 0.2 + onda * actividad * 0.15).toFixed(3)})`;
      ctx.beginPath();
      ctx.moveTo(A[0], A[1]);
      ctx.lineTo(B[0], B[1]);
      ctx.stroke();
    }

    // Esfera exterior (con realce donde pasa una onda).
    const bandas = ondas.map((o) => ({r: suave(Math.min(1, (t - o.t) / 1600)) * radio * 2.2, a: 1 - Math.min(1, (t - o.t) / 1600), c: o.color, f: o.fuerza}));
    for (let i = 0; i < puntos.length; i++) {
      const [px, py, prof] = proy[i];
      const d = Math.hypot(px - cx, py - cy);
      let realce = 0, col = null;
      for (const b of bandas) {
        const dd = Math.abs(d - b.r);
        if (dd < radio * 0.18) { const e = (1 - dd / (radio * 0.18)) * b.a * b.f; if (e > realce) { realce = e; col = b.c; } }
      }
      const chispa = vivo && (i % 97 === Math.floor(t / 140) % 97);
      const tam = (0.55 + prof * 1.25 + realce * 1.8) * dpr;
      ctx.fillStyle = realce > 0.05 ? (colores[col] || marca) : chispa ? marca : `rgba(${colores.p}, ${(0.14 + prof * 0.86).toFixed(3)})`;
      ctx.globalAlpha = nace * (realce > 0.05 ? Math.min(1, 0.5 + realce) : 1);
      const lado = tam * (chispa ? 2 : 1);
      ctx.fillRect(px - lado / 2, py - lado / 2, lado, lado);
    }
    ctx.globalAlpha = nace;
    // Ondas: anillos que se expanden por la pantalla desde el centro.
    for (const b of bandas) {
      ctx.strokeStyle = colores[b.c] || marca;
      ctx.globalAlpha = nace * b.a * 0.5 * b.f;
      ctx.lineWidth = (1.5 + (1 - b.a) * 1.5) * dpr;
      ctx.beginPath();
      ctx.ellipse(cx, cy, b.r, b.r * 0.82, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.globalAlpha = nace;

    // Núcleo interior: contra-rotación, brillo que late y chispas.
    const nucleoR = radio * (0.46 + latido * 0.05);
    const brillo = ctx.createRadialGradient(cx, cy, 0, cx, cy, nucleoR * 1.4);
    brillo.addColorStop(0, `rgba(${colores.p}, ${(0.18 + latido * 0.32).toFixed(3)})`);
    brillo.addColorStop(1, `rgba(${colores.p}, 0)`);
    ctx.fillStyle = brillo;
    ctx.fillRect(cx - nucleoR * 1.5, cy - nucleoR * 1.5, nucleoR * 3, nucleoR * 3);
    const cai = Math.cos(-a * 1.7), sai = Math.sin(-a * 1.7);
    for (let i = 0; i < interior.length; i++) {
      const [px, py, prof] = proyectar(interior[i], cai, sai, ci, si, radio, cx, cy, 1 + latido * 0.05);
      const tam = (0.7 + prof * 1.3) * dpr;
      ctx.fillStyle = i % 11 === Math.floor(t / 120) % 11 ? marca : `rgba(${colores.p}, ${(0.25 + prof * 0.7).toFixed(3)})`;
      ctx.fillRect(px - tam / 2, py - tam / 2, tam, tam);
    }
    ctx.globalAlpha = 1;
  }

  function bucle(t) {
    raf = null;
    if (!el.isConnected) { quitarEscucha(); return; }                        // la vista se fue: se para solo
    if (visible && !document.hidden && t - ultimo >= 33) {
      const dt = Math.min(3, (t - ultimo) / 16.7 || 1);
      ultimo = t;
      giro *= 0.94;                                                          // la inercia del arrastre se apaga sola
      ang += ((vivo ? vel : vel * 0.28) * (1 + actividad * 1.5) + giro) * dt;
      mira.ox += (mira.x - mira.ox) * 0.08;
      mira.oy += (mira.y - mira.oy) * 0.08;
      actividad = Math.max(0, actividad - 0.004 * dt);
      const ciclo = vivo ? 1500 / (1 + actividad * 1.2) : 3200;              // latido del núcleo interior
      latido = Math.pow((Math.sin(t / ciclo * Math.PI * 2) + 1) / 2, 3);
      for (let i = ondas.length - 1; i >= 0; i--) if (t - ondas[i].t > 1700) ondas.splice(i, 1);
      if (++marcos % 90 === 0) medir();                                      // el diseño puede cambiar (fuentes, datos)
      dibujar(t);
    }
    if (!reducido()) raf = requestAnimationFrame(bucle);
  }

  function arrancar() {
    medir();
    if (reducido()) { dibujar(performance.now() + 2000); return; }
    if (!raf) raf = requestAnimationFrame(bucle);
  }

  // ---------------------------------------------------------------- interacción
  function normal(e) {
    const r = el.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * 2 - 1, ((e.clientY - r.top) / r.height) * 2 - 1];
  }
  let arrastre = null;
  el.addEventListener("pointermove", (e) => {
    const [nx, ny] = normal(e);
    mira.x = nx; mira.y = ny;
    if (arrastre) { giro = (e.clientX - arrastre.x) * 0.0016; arrastre.x = e.clientX; arrastre.mov = true; }
  });
  el.addEventListener("pointerleave", () => { mira.x = 0; mira.y = 0; arrastre = null; });
  el.addEventListener("pointerdown", (e) => { arrastre = {x: e.clientX, mov: false}; });
  el.addEventListener("pointerup", () => {
    if (arrastre && !arrastre.mov) lanzarOnda("sal", 1);                    // un toque sin arrastrar = una onda
    arrastre = null;
  });
  el.addEventListener("pointercancel", () => { arrastre = null; });

  function lanzarOnda(col, fuerza = 0.8) {
    if (reducido()) return;
    ondas.push({t: performance.now(), color: col, fuerza});
    if (ondas.length > 4) ondas.shift();
  }

  // ---------------------------------------------------------------- novedades del bot (bus de eventos)
  const quitarEscucha = alEvento((ev) => {
    if (!el.isConnected) return;
    actividad = Math.min(1, actividad + 0.45);
    const col = ONDA[ev.tipo] || "p";
    lanzarOnda(col, col === "rojo" ? 1 : 0.8);
    const hilos = anclas ? anclas.ent.length + anclas.sal.length : 0;
    if (hilos && !reducido()) {
      const entrante = ["senal_detectada", "ballena_fill", "ballena_cambio_inferido", "operacion_grande"].includes(ev.tipo);
      const n = entrante ? anclas.ent.length : anclas.sal.length;
      const base = entrante ? 0 : anclas.ent.length;
      chispas.push({t: performance.now(), hilo: base + Math.floor(Math.random() * n), color: col === "p" ? "vivo" : col});
    }
  });

  if (window.IntersectionObserver) {
    new IntersectionObserver((es) => { visible = es.some((e) => e.isIntersecting); if (visible) arrancar(); }).observe(el);
  }
  if (window.ResizeObserver) new ResizeObserver(() => { medir(); if (reducido()) dibujar(performance.now() + 2000); }).observe(el);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) arrancar(); });

  /** Rellena las cifras con los datos del bot (cada sondeo). */
  function actualizar(d) {
    const b = d?.bot || {};
    vivo = !!d?.bot_vivo;
    salud = Object.keys(b.sin_stop || {}).length || b.conciliacion_ok === false ? "mal" : !vivo || (b.bloqueos || []).length ? "aviso" : "ok";
    const ext = Object.values(b.contexto_externo?.fuentes || {});
    const extOk = ext.filter((f) => f.estado === "correcto").length;
    const cob = b.cobertura_ballenas || {};
    const est = b.estrategias || [];
    const activas = est.filter((e) => e.activa).length;
    const sombra = Object.values(b.probador?.estrategias || {}).reduce((s, x) => s + (x.sombra?.n || 0), 0);
    const pos = b.posiciones || [];
    const ra = b.limites?.riesgo_abierto?.valor_pct;
    const cer = b.cerebro || {};
    reemplazar(cabeza,
      h("span", {clase: "etq"}, "▸ Núcleo · cerebro del bot"),
      h("span", {clase: "etq"}, vivo ? "decide al cierre de cada vela de 4 h" : "bot sin señales: núcleo en espera"));
    reemplazar(entradas,
      nodo("", "Velas 4 h", num((b.motor?.monedas || []).length, 0), "monedas vigiladas", vivo),
      nodo("", "Funding · OI", num((b.mercado?.monedas || []).length, 0), "Hyperliquid, cada ciclo", vivo),
      nodo("", "Binance · Bybit", ext.length ? `${extOk}/${ext.length}` : "—", "datos públicos de lectura", ext.length && extOk === ext.length),
      nodo("", "Ballenas", num(cob.elegidas, 0), hay(cob.frescas) ? `${cob.frescas} con datos frescos` : null, vivo));
    reemplazar(salidas,
      nodo("salida", "Posiciones", String(pos.length), hay(ra) ? `riesgo abierto ${pct(ra, 1)}` : null, pos.length > 0),
      nodo("salida", "Estrategias", String(activas), "activas en simulado", activas > 0),
      nodo("salida", "En sombra", num(sombra, 0), "señales medidas sin dinero", false),
      nodo("salida", "Superan el lab", num(b.motor?.validadas, 0), "evidencia para real", (b.motor?.validadas || 0) > 0));
    reemplazar(centro, h("div", {},
      h("div", {clase: "etq"}, cer.decide ? "Cerebro activo" : "Cerebro desactivado"),
      h("div", {clase: "muy-tenue mono"}, cer.version ? String(cer.version).replace("cerebro-lab-", "modelo ") : "sin modelo")));
    reemplazar(leyenda,
      h("span", {}, h("b", {}, "● "), "entrada de datos"), h("span", {}, h("b", {}, "● "), "decisión y resultado"),
      h("span", {}, "arrastra para girarla · toca para lanzar una onda"),
      h("span", {}, "la esfera es decorativa; las cifras son reales"));
    medir();
    if (reducido()) dibujar(performance.now() + 2000); else arrancar();
  }

  return {el, actualizar};
}
