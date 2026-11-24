// CONFIGURACIÓN: SOLO los campos que expone el backend (lista blanca de config_panel.py), con vista previa del
// cambio, aviso si sube el riesgo, confirmación, historial y restauración. El navegador no es la frontera de
// seguridad: el backend vuelve a validar todo y rechaza modo, real, claves, red y permisos.

import {SOLO_LECTURA, enviar, esperarResultado, obtener} from "../api.js";
import {chip, errorCarga, h, reemplazar, seccion, tabla, vacio} from "../dom.js";
import {fecha, iso} from "../formato.js";
import {abrirDialogo, ayuda} from "../info.js";

let raiz = null;
const st = {esq: null, cambios: {}, seccion: null, puede: false, mensaje: ""};

function valorTexto(v) {
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" ? x.direccion : x)).join(", ") || "(vacío)";
  if (typeof v === "boolean") return v ? "sí" : "no";
  return v === null || v === undefined ? "—" : String(v);
}

function editor(c) {
  const id = `campo-${c.ruta.replaceAll(".", "-")}`;
  const marcar = (v) => { st.cambios[c.ruta] = v; pintarCambios(); };
  const desact = !st.puede || null;
  const actual = c.ruta in st.cambios ? st.cambios[c.ruta] : c.valor;
  if (c.tipo === "bool") return h("input", {id, type: "checkbox", marcado: !!actual, disabled: desact, onChange: (e) => marcar(e.target.checked)});
  if (c.tipo === "int" || c.tipo === "num") {
    return h("input", {id, type: "number", valor: actual ?? "", min: c.min ?? null, max: c.max ?? null, step: c.paso ?? (c.tipo === "int" ? 1 : "any"),
      disabled: desact, inputmode: "decimal", onChange: (e) => marcar(e.target.value)});
  }
  if (c.tipo === "opcion") return h("select", {id, disabled: desact, onChange: (e) => marcar(e.target.value)},
    (c.opciones || []).map((o) => h("option", {value: o, selected: o === actual || null}, o)));
  if (c.tipo === "multi") return h("fieldset", {id}, (c.opciones || []).map((o) => h("label", {clase: "acciones"},
    h("input", {type: "checkbox", value: o, marcado: (actual || []).includes(o), disabled: desact, onChange: (e) => {
      const sel = [...e.target.closest("fieldset").querySelectorAll("input:checked")].map((i) => i.value);
      marcar(sel);
    }}), o)));
  if (c.tipo === "monedas") return h("textarea", {id, disabled: desact, "aria-describedby": `${id}-ayuda`, onChange: (e) =>
    marcar(e.target.value.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean))}, (actual || []).join(", "));
  if (c.tipo === "direcciones") {
    const quitar = new Set((st.cambios[c.ruta] || {}).quitar || []);
    const nuevas = h("input", {type: "text", placeholder: "añadir 0x… (una o varias separadas por coma)", disabled: desact, autocomplete: "off",
      "aria-label": `Añadir direcciones a ${c.etiqueta}`});
    const enviarDir = () => marcar({quitar: [...quitar], anadir: nuevas.value.split(/[\s,;]+/).filter(Boolean)});
    nuevas.addEventListener("change", enviarDir);
    return h("div", {id}, (c.valor || []).map((d) => h("label", {clase: "acciones"},
      h("input", {type: "checkbox", disabled: desact, marcado: quitar.has(d.i), onChange: (e) => { if (e.target.checked) quitar.add(d.i); else quitar.delete(d.i); enviarDir(); }}),
      h("span", {clase: "mono"}, d.direccion), " quitar")), nuevas);
  }
  return h("span", {clase: "tenue"}, valorTexto(c.valor));
}

function pintarSeccion() {
  const zona = raiz.querySelector("#cfg-campos");
  const campos = (st.esq.campos || []).filter((c) => c.seccion === st.seccion);
  const sec = (st.esq.secciones || []).find((s) => s.id === st.seccion) || {};
  reemplazar(zona, h("h2", {}, sec.titulo || st.seccion, sec.texto ? [" ", ayuda(sec.titulo || st.seccion, sec.texto)] : null),
    campos.length ? campos.map((c) => h("div", {clase: ["campo", c.ruta in st.cambios ? "cambiado" : null]},
      h("label", {for: `campo-${c.ruta.replaceAll(".", "-")}`}, c.etiqueta, c.unidad ? h("span", {clase: "muy-tenue"}, ` (${c.unidad})`) : null,
        c.riesgo ? h("span", {clase: "muy-tenue"}, c.riesgo === "sube" ? " · subirlo aumenta el riesgo" : " · bajarlo aumenta el riesgo") : null),
      editor(c), c.ayuda ? h("details", {clase: "ayuda-campo", id: `campo-${c.ruta.replaceAll(".", "-")}-ayuda`},
        h("summary", {}, "¿Qué es?"), h("div", {clase: "ayuda"}, c.ayuda)) : null)) : vacio("Sin campos en esta sección."));
}

function pintarCambios() {
  const n = Object.keys(st.cambios).length;
  const zona = raiz.querySelector("#cfg-barra");
  reemplazar(zona, h("div", {clase: "acciones"},
    h("span", {clase: "tenue", "aria-live": "polite"}, n ? `${n} cambio(s) sin guardar` : "Sin cambios"),
    h("button", {type: "button", clase: "primario", disabled: !n || !st.puede || null, onClick: previsualizar}, "Revisar cambios…"),
    h("button", {type: "button", disabled: !n || null, onClick: () => { st.cambios = {}; pintarSeccion(); pintarCambios(); }}, "Descartar"),
    h("button", {type: "button", onClick: historial}, "Historial y restaurar")),
    st.mensaje ? h("p", {clase: "aviso info", role: "status"}, st.mensaje) : null);
}

async function previsualizar() {
  const r = await enviar("/api/config", {cambios: st.cambios});
  if (!r.ok) {
    abrirDialogo("No se puede guardar", h("p", {clase: "aviso mal"}, "El bot rechaza estos cambios:"),
      h("ul", {}, (r.errores || [r.error]).map((x) => h("li", {}, x))));
    return;
  }
  const confirmar = h("button", {type: "button", clase: "primario", onClick: async (e) => {
    e.currentTarget.disabled = true;
    const g = await enviar("/api/config", {cambios: st.cambios, confirmar: true});
    if (!g.ok) { abrirDialogo("No se ha guardado", h("p", {clase: "aviso mal"}, g.error || "error")); return; }
    st.cambios = {};
    st.mensaje = `${g.mensaje} Esperando confirmación del bot…`;
    document.getElementById("dialogo").close();
    await cargar();
    const res = await esperarResultado(g.id);
    st.mensaje = res.pendiente ? res.mensaje : `Bot: ${res.mensaje || (res.ok ? "aplicado" : "no aplicado")}`;
    if (raiz) pintarCambios();
  }}, "Guardar y aplicar");
  abrirDialogo("Revisa los cambios",
    r.sube_riesgo ? h("p", {clase: "aviso mal"}, "⚠ Alguno de estos cambios AUMENTA el riesgo.") : null,
    tabla([{t: "Ajuste", v: (x) => x.etiqueta}, {t: "Antes", v: (x) => valorTexto(x.antes)}, {t: "Después", v: (x) => valorTexto(x.despues)},
      {t: "Riesgo", v: (x) => x.sube_riesgo ? chip("sube", "mal") : x.sube_riesgo === false ? chip("baja", "ok") : "—"}], r.cambios),
    h("p", {clase: "tenue"}, st.esq.aviso || ""), h("div", {clase: "acciones"}, confirmar,
      h("button", {type: "button", onClick: () => document.getElementById("dialogo").close()}, "Volver")));
}

async function historial() {
  let hst;
  try { hst = (await obtener("/api/config/historial")).cambios || []; } catch (e) { abrirDialogo("Historial", errorCarga(e.message)); return; }
  abrirDialogo("Historial de cambios", hst.length ? tabla([
    {t: "Fecha", v: (x) => fecha(iso(x.ts) ?? x.ts)}, {t: "Origen", v: (x) => x.origen || "—"},
    {t: "Cambios", v: (x) => (x.cambios || []).map((c) => `${c.etiqueta}: ${valorTexto(c.antes)} → ${valorTexto(c.despues)}`).join(" · ")},
    {t: "", v: (x) => x.copia_anterior && x.copia_disponible && st.puede ? h("button", {type: "button", onClick: () => {
      abrirDialogo("¿Restaurar la configuración anterior a este cambio?",
        h("p", {}, `Se vuelve a la copia ${x.copia_anterior}. El bot la valida y se reinicia de forma ordenada.`),
        h("div", {clase: "acciones"}, h("button", {type: "button", clase: "primario", onClick: async (e) => {
          e.currentTarget.disabled = true;
          const r = await enviar("/api/config/restaurar", {copia: x.copia_anterior});
          abrirDialogo("Restaurar", h("p", {clase: r.ok ? "aviso info" : "aviso mal"}, r.mensaje || r.error || ""));
        }}, "Sí, restaurar"), h("button", {type: "button", onClick: () => document.getElementById("dialogo").close()}, "Cancelar")));
    }}, "Restaurar la copia anterior") : (x.copia_anterior && !x.copia_disponible ? h("span", {clase: "muy-tenue"}, "copia ya no disponible") : "")},
  ], hst) : vacio("Aún no se ha cambiado nada desde el panel."));
}

async function cargar() {
  try {
    st.esq = await obtener("/api/config");
  } catch (e) {
    reemplazar(raiz, h("h1", {}, "Configuración"), errorCarga(`No se pudo leer la configuración: ${e.message}`));
    return;
  }
  st.puede = !!st.esq.puede_editar && !SOLO_LECTURA;
  st.seccion = st.seccion || st.esq.secciones?.[0]?.id;
  if (!raiz) return;
  const pestanas = h("div", {clase: "pestanas", role: "group", "aria-label": "Secciones de la configuración"},
    (st.esq.secciones || []).map((s) => h("button", {type: "button", "aria-pressed": String(s.id === st.seccion), onClick: (e) => {
      st.seccion = s.id;
      for (const b of pestanas.children) b.setAttribute("aria-pressed", String(b === e.currentTarget));
      pintarSeccion();
    }}, s.titulo)));
  reemplazar(raiz, h("div", {clase: "titulo-vista"}, h("div", {}, h("h1", {}, "Configuración"),
    h("p", {}, "Los ajustes que se pueden cambiar desde aquí ", ayuda("Qué se puede cambiar",
      "Solo los ajustes que el bot permite cambiar desde el panel, con vista previa antes de guardar.",
      "El modo, el dinero real, las claves, la red y los permisos NO se cambian aquí: eso se hace a mano, a propósito."),
    ))),
  st.puede ? null : h("p", {clase: "aviso"}, "Solo lectura: los cambios solo se hacen desde este equipo."),
  seccion(null, pestanas, h("div", {id: "cfg-campos"})), h("div", {id: "cfg-barra", clase: "seccion barra-fija"}));
  pintarSeccion();
  pintarCambios();
}

export const vista = {
  async entrar(el) { raiz = el; reemplazar(el, h("p", {clase: "cargando"}, "Cargando configuración…")); await cargar(); },
  salir() { raiz = null; },
};
