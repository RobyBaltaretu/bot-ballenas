// CETO (19/11/2026): la ballena-robot que da el veredicto. Una ballena mecánica de SVG con sonar, ojo que sigue al cursor,
// branquias que se iluminan cuando habla, chorro de burbujas y un humor que cambia con el veredicto
// (adelante / cambiar de rumbo / no vale / pendiente / analiza). Habla con una burbuja que escribe letra a letra.
// IMPORTANTE: Ceto solo PRONUNCIA lo que ya calculó el código (criterios, alarmas, informe). No decide nada,
// y lo dice siempre en su última frase. Sin librerías ni estilos en línea (CSP): clases + CSSOM.

import {reducido} from "./anim.js";
import {h} from "./dom.js";
import {svg} from "./grafico.js";

let contador = 0;

/** Dibuja la ballena. Devuelve {el, pupila}; los colores salen del CSS (--ceto) según el humor. */
function dibujarBallena() {
  const n = ++contador;
  const s = svg("svg", {viewBox: "0 0 440 260", role: "img", "aria-label": "Ceto, la ballena robot del bot", class: "ceto-svg"});
  const defs = svg("defs", {});
  const grad = svg("linearGradient", {id: `cg${n}`, x1: "0", y1: "0", x2: "0", y2: "1"});
  grad.append(svg("stop", {offset: "0", class: "cg-a"}), svg("stop", {offset: "1", class: "cg-b"}));
  const vientre = svg("linearGradient", {id: `cv${n}`, x1: "0", y1: "0", x2: "0", y2: "1"});
  vientre.append(svg("stop", {offset: "0", class: "cv-a"}), svg("stop", {offset: "1", class: "cv-b"}));
  const recorte = svg("clipPath", {id: `cr${n}`});
  recorte.append(svg("circle", {cx: 352, cy: 126, r: 15}));
  defs.append(grad, vientre, recorte);

  const cola = svg("g", {class: "ceto-cola"});
  cola.append(
    svg("path", {d: "M92 138 C64 118 44 94 24 66 C56 62 84 78 98 100 Z", class: "ceto-placa"}),
    svg("path", {d: "M92 146 C66 162 50 186 32 216 C62 214 88 198 102 176 Z", class: "ceto-placa"}),
    svg("path", {d: "M92 142 L40 112", class: "ceto-linea"}), svg("path", {d: "M92 144 L48 190", class: "ceto-linea"}));

  const cuerpo = svg("g", {class: "ceto-cuerpo"});
  cuerpo.append(
    svg("path", {d: "M80 130 C105 80 195 54 275 68 C350 82 420 114 418 148 C416 188 350 214 270 214 C200 214 142 200 104 166 Z", fill: `url(#cg${n})`, class: "ceto-piel"}),
    svg("path", {d: "M104 166 C142 200 200 214 270 214 C350 214 416 188 418 148 C380 178 320 188 260 186 C190 184 140 178 104 166 Z", fill: `url(#cv${n})`, class: "ceto-vientre"}),
    // surcos del vientre (placas) y costuras del casco
    ...[150, 185, 220, 255, 290, 325, 360].map((x) => svg("path", {d: `M${x} ${190 + (x < 250 ? 6 : 2)} l-6 -14`, class: "ceto-surco"})),
    svg("path", {d: "M150 98 C200 80 250 78 300 90", class: "ceto-costura"}),
    svg("path", {d: "M196 76 L204 154", class: "ceto-costura"}),
    svg("path", {d: "M300 90 C318 110 322 140 310 176", class: "ceto-costura"}),
    ...[[160, 100], [210, 84], [262, 82], [306, 96]].map(([x, y]) => svg("circle", {cx: x, cy: y, r: 2.2, class: "ceto-remache"})));

  // aletas
  const dorsal = svg("path", {d: "M176 74 C170 54 178 40 194 30 C194 48 204 60 218 68 Z", class: "ceto-placa"});
  const aleta = svg("g", {class: "ceto-aleta"});
  aleta.append(svg("path", {d: "M258 176 C238 196 214 218 188 232 C230 238 270 218 292 188 Z", class: "ceto-placa"}),
    svg("path", {d: "M262 184 L206 224", class: "ceto-linea"}));

  // antena de sonar con su orbe y los anillos que se expanden
  const antena = svg("g", {class: "ceto-antena"});
  antena.append(svg("path", {d: "M232 72 C232 50 226 36 214 26", class: "ceto-hilo"}),
    ...[0, 1, 2].map((k) => svg("circle", {cx: 214, cy: 22, r: 7, class: `ceto-ping ceto-ping-${k}`})),
    svg("circle", {cx: 214, cy: 22, r: 6, class: "ceto-orbe"}));

  // pantalla del pecho
  const pantalla = svg("g", {class: "ceto-pantalla"});
  pantalla.append(svg("rect", {x: 150, y: 150, width: 78, height: 28, rx: 5, class: "ceto-marco"}),
    ...[0, 1, 2, 3, 4, 5, 6].map((k) => svg("rect", {x: 157 + k * 10, y: 155, width: 6, height: 18, rx: 1.5, class: `ceto-barra ceto-barra-${k}`})));

  // branquias que se iluminan al hablar
  const branquias = svg("g", {class: "ceto-branquias"});
  branquias.append(...[0, 1, 2].map((k) => svg("rect", {x: 296 + k * 11, y: 146 + k * 1.5, width: 5, height: 26, rx: 2.5, class: `ceto-branquia ceto-branquia-${k}`,
    transform: `rotate(14 ${298 + k * 11} ${159 + k * 1.5})`})));

  // ojo: aro, iris con el color del humor, pupila que sigue al cursor, destello y párpado
  const ojo = svg("g", {class: "ceto-ojo"});
  const pupila = svg("g", {class: "ceto-pupila"});
  pupila.append(svg("circle", {cx: 352, cy: 126, r: 9, class: "ceto-iris"}), svg("circle", {cx: 352, cy: 126, r: 4.2, class: "ceto-nucleo"}),
    svg("circle", {cx: 355.5, cy: 122.5, r: 1.8, class: "ceto-brillo"}));
  const parpado = svg("g", {"clip-path": `url(#cr${n})`});
  parpado.append(svg("rect", {x: 336, y: 110, width: 32, height: 32, class: "ceto-parpado"}));
  ojo.append(svg("circle", {cx: 352, cy: 126, r: 17, class: "ceto-aro"}), svg("circle", {cx: 352, cy: 126, r: 15, class: "ceto-fondo-ojo"}), pupila, parpado);

  // chorro de burbujas por el espiráculo
  const chorro = svg("g", {class: "ceto-chorro"});
  chorro.append(...[0, 1, 2, 3, 4, 5].map((k) => svg("circle", {cx: 262 + (k % 3) * 6 - 6, cy: 66, r: 2 + (k % 3), class: `ceto-gota ceto-gota-${k}`})));

  s.append(defs, cola, cuerpo, dorsal, branquias, pantalla, aleta, antena, chorro, ojo);
  return {el: s, pupila};
}

/** Burbuja que escribe. Devuelve {el, decir(lineas), parar()}. */
function burbuja(raiz, alHablar) {
  const el = h("div", {clase: "ceto-burbuja", role: "status", "aria-live": "polite"});
  let ronda = 0;
  const parar = () => { ronda++; };
  async function decir(lineas) {
    const mia = ++ronda;
    el.replaceChildren();
    const textos = (Array.isArray(lineas) ? lineas : [lineas]).filter(Boolean);
    if (reducido()) {
      textos.forEach((t, i) => el.append(h("p", {clase: i === textos.length - 1 ? "ceto-nota" : null}, t)));
      return;
    }
    alHablar(true);
    for (let i = 0; i < textos.length; i++) {
      const p = h("p", {clase: ["ceto-escribe", i === textos.length - 1 && textos.length > 1 ? "ceto-nota" : null]});
      el.append(p);
      const t = textos[i];
      for (let k = 1; k <= t.length; k++) {
        if (mia !== ronda || !raiz.isConnected) return;
        p.textContent = t.slice(0, k);
        await new Promise((r) => setTimeout(r, 14 + (/[.,;:]/.test(t[k - 1]) ? 90 : 0)));
      }
      p.classList.remove("ceto-escribe");
      await new Promise((r) => setTimeout(r, 260));
    }
    if (mia === ronda) alHablar(false);
  }
  return {el, decir, parar};
}

/**
 * ceto({humor, frases, cabecera, contactos, compacto})
 *  humor: adelante | rumbo | no_vale | pendiente | analiza   (cambia color y gestos)
 *  frases: lo que dice al abrir la vista (la última se muestra como nota)
 *  cabecera: nodos que van a la derecha, encima de la burbuja (etiqueta, veredicto…)
 *  contactos: [{etq, estado: ok|aviso|mal|null, dice: [frases]}] — «ecos de sonar»; al pasar el cursor, Ceto los explica
 */
export function ceto({humor = "pendiente", frases = [], cabecera = null, contactos = [], compacto = false} = {}) {
  const raiz = h("section", {clase: ["ceto", compacto ? "ceto-compacto" : null], "data-humor": humor, "aria-label": "Ceto, el analista del bot"});
  const {el: ballena, pupila} = dibujarBallena();
  const habla = (si) => raiz.classList.toggle("hablando", si);
  const voz = burbuja(raiz, habla);

  const escena = h("button", {clase: "ceto-escena", type: "button", "aria-label": "Ceto: pulsa para que repita lo que ve",
    onClick: () => { raiz.classList.remove("ceto-salto"); void raiz.offsetWidth; raiz.classList.add("ceto-salto"); voz.decir(frases); }},
  h("div", {clase: "ceto-sonar", "aria-hidden": "true"}, h("span", {clase: "ceto-barrido"})),
  h("div", {clase: "ceto-burbujas", "aria-hidden": "true"}, Array.from({length: 9}, (_, k) => h("i", {estilo: {"--k": String(k)}}))),
  h("div", {clase: "ceto-nada"}, ballena));

  const ecos = contactos.length ? h("div", {clase: "ceto-ecos", role: "list", "aria-label": "Lecturas del sonar"},
    contactos.map((c, k) => h("button", {clase: ["ceto-eco", c.estado ? `eco-${c.estado}` : null], type: "button", role: "listitem",
      title: c.etq, "aria-label": c.etq, estilo: {"--k": String(k)},
      onMouseenter: () => voz.decir(c.dice), onFocus: () => voz.decir(c.dice), onClick: () => voz.decir(c.dice)},
    h("span", {clase: "eco-punto"}), h("span", {clase: "eco-etq"}, c.etq)))) : null;

  raiz.append(escena, h("div", {clase: "ceto-lado"}, cabecera, voz.el, ecos,
    h("p", {clase: "ceto-pie"}, "Pulsa a Ceto para que repita. Pasa el cursor por los ecos para oír cada lectura.")));

  // La pupila sigue al cursor (con límite) mientras Ceto esté en pantalla.
  let bloqueo = 0;
  const seguir = (e) => {
    if (!raiz.isConnected) { document.removeEventListener("pointermove", seguir); return; }
    const t = performance.now();
    if (t - bloqueo < 40 || reducido()) return;
    bloqueo = t;
    const r = ballena.getBoundingClientRect();
    if (!r.width) return;
    const ox = r.left + r.width * (352 / 440), oy = r.top + r.height * (126 / 260);
    const dx = e.clientX - ox, dy = e.clientY - oy, d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 220) * 5.5;
    pupila.style.transform = `translate(${(dx / d * k).toFixed(2)}px, ${(dy / d * k).toFixed(2)}px)`;
  };
  document.addEventListener("pointermove", seguir, {passive: true});

  // Primera intervención: tras un instante, para que se vea entrar a la ballena.
  setTimeout(() => { if (raiz.isConnected) voz.decir(frases); }, reducido() ? 0 : 700);
  return raiz;
}
