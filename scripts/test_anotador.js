// Ejecuta el JS del anotador contra un DOM falso y comprueba el flujo.
const fs = require("fs");
const vm = require("vm");

const HTML = "C:\\Users\\PC\\¿\\mis\\personal\\faixas\\datos\\procesado\\validacion\\anotador.html";
const src = fs.readFileSync(HTML, "utf8");
const js = src.match(/<script>([\s\S]*)<\/script>/)[1];

// ---- DOM minimo -----------------------------------------------------------
function nodo(id) {
  const clases = new Set();
  return {
    id, textContent: "", innerHTML: "", src: "", onclick: null,
    dataset: {}, style: {},
    classList: {
      add: c => clases.add(c), remove: c => clases.delete(c),
      contains: c => clases.has(c),
      toggle: (c, on) => (on === undefined ? (clases.has(c) ? clases.delete(c)
                                                            : clases.add(c))
                                           : (on ? clases.add(c) : clases.delete(c))),
    },
    _clases: clases,
  };
}
const nodos = {};
const opciones1 = ["arbol", "no", "edificacion", "dudoso"].map(v => {
  const n = nodo("op-" + v); n.dataset.v = v; return n;
});
const opciones2 = ["pino", "eucalipto", "acacia", "frondosa", "nd"].map(t => {
  const n = nodo("op-" + t); n.dataset.t = t; return n;
});
let descargas = [];

const TIPOS = ["pino", "eucalipto", "acacia", "frondosa", "nd"];
const document = {
  querySelector: s => nodos[s] || (nodos[s] = nodo(s)),
  querySelectorAll: s => s.startsWith("#pregunta1") ? opciones1 : opciones2,
  createElement: () => ({ href: "", download: "", click() { descargas.push(this); } }),
  onkeydown: null,
};
const almacen = {};
const localStorage = {
  setItem: (k, v) => { almacen[k] = String(v); },
  getItem: k => (k in almacen ? almacen[k] : null),
  removeItem: k => { delete almacen[k]; },
};
let ultimoBlob = null;
const ctx = {
  document, localStorage, console,
  Image: function () { return { set src(v) {} }; },
  Blob: function (partes) { ultimoBlob = partes.join(""); return { partes }; },
  URL: { createObjectURL: () => "blob:x" },
  confirm: () => true,
  JSON, Date, Object, Math, Array, String, Number, parseInt,
};
// una "recarga" es un contexto nuevo con el mismo localStorage: si se reejecuta
// el script en el mismo contexto, el `const PUNTOS` choca consigo mismo
function carga() {
  const c = Object.assign({}, ctx);
  vm.createContext(c);
  vm.runInContext(js, c);
  return c;
}
let vivo = carga();

// ---- utilidades de prueba -------------------------------------------------
const tecla = k => document.onkeydown({ key: k, preventDefault() {} });
const resp = () => JSON.parse(almacen[Object.keys(almacen).find(k => k.startsWith("faixas-"))] || "{}");
const estado = () => nodos["#estado"].textContent;
const PUNTOS = vm.runInContext("PUNTOS", vivo);
// el test se adapta al modo con el que se genero el HTML: si no,
// correrlo sobre un anotador hecho con --sin-tipo daria una pared
// de fallos enganosos que no son fallos
const PIDE_TIPO = vm.runInContext("PIDE_TIPO", vivo);

let fallos = 0;
function ok(cond, msg) {
  console.log((cond ? "  ok   " : "  FALLO") + "  " + msg);
  if (!cond) fallos++;
}

console.log(`\n${PUNTOS.length} puntos cargados`);
console.log(PIDE_TIPO ? "modo normal (pregunta el tipo de copa)"
                      : "modo --sin-tipo (solo arbol / no arbol)");
ok(PUNTOS.length === 400, "el HTML lleva los 400 puntos");
ok(!("h" in PUNTOS[0]) && !("chm_m" in PUNTOS[0]),
   "los puntos NO llevan la altura del CHM (anotacion ciega)");
ok(!/CHM|chips_chm|revela/i.test(js), "no queda rastro del revelado en el JS");

console.log("\nflujo basico");
ok(estado().includes("posición 1"), "arranca en el primero");
tecla("2");                                     // no arbol
ok(resp()[PUNTOS[0].id].clase === "no", "1) '2' guarda 'no' y avanza");
ok(estado().includes("posición 2"), "   avanzo al segundo");

tecla("1");                                     // arbol
if (PIDE_TIPO) {
  ok(estado().includes("posición 2"), "2) '1' NO avanza: espera el tipo");
  ok(nodos["#pregunta2"]._clases.has("oculto") === false, "   muestra la subpregunta");
  tecla("4");                                   // frondosa
  const r2 = resp()[PUNTOS[1].id];
  ok(r2.clase === "arbol" && r2.tipo === "frondosa", "   guarda clase y tipo");
  ok(estado().includes("posición 3"), "   y ahora si avanza");

  // la acacia es una frondosa PROHIBIDA: si no tuviera tecla propia acabaria
  // marcada como frondosa, o sea como exenta, que es justo lo contrario
  ok(TIPOS.includes("acacia"), "la acacia tiene categoria propia");
  ok(/acacia/i.test(js) && /eucalipto/i.test(js) && /pino/i.test(js),
     "las tres categorias prohibidas estan en el JS");
  ok(!/conifera/i.test(js), "ya no queda 'conifera o eucalipto', que mezclaba");
} else {
  // con --sin-tipo la subpregunta no existe y 'arbol' avanza directo
  ok(resp()[PUNTOS[1].id].clase === "arbol", "2) '1' guarda 'arbol'");
  ok(estado().includes("posición 3"), "   y avanza directo: no pide tipo");
  ok(resp()[PUNTOS[1].id].tipo === undefined, "   y no inventa un tipo");
}

tecla("3"); tecla("4");
ok(resp()[PUNTOS[2].id].clase === "edificacion", "3) '3' -> edificacion");
ok(resp()[PUNTOS[3].id].clase === "dudoso", "4) '4' -> dudoso");
ok(Object.keys(resp()).length === 4, "   cuatro respuestas guardadas");

console.log("\nnavegacion y revision");
tecla("ArrowLeft"); tecla("ArrowLeft");
ok(estado().includes("posición 3"), "flecha izquierda retrocede");
ok(estado().includes("respondido: edificacion"), "   y ensena lo ya respondido");
tecla("2");
ok(resp()[PUNTOS[2].id].clase === "no", "re-responder sobrescribe");
ok(estado().includes("posición 4"),
   "   al revisar avanza de uno en uno, no salta a la primera sin responder");

const antes = Object.keys(resp()).length;
tecla("ArrowRight");
ok(Object.keys(resp()).length === antes, "flecha derecha salta sin guardar nada");

console.log("\nteclas que no deben hacer nada");
const n0 = Object.keys(resp()).length;
["5", "0", "r", "d", "a", "Enter", "Escape"].forEach(tecla);
ok(Object.keys(resp()).length === n0, "teclas sueltas no crean respuestas fantasma");
document.onkeydown({ key: "1", ctrlKey: true, preventDefault() {} });
ok(Object.keys(resp()).length === n0, "ctrl+1 tampoco (es un atajo del navegador)");

console.log("\nencuadre de contexto");
const cerca = () => !nodos["#chip"]._clases.has("oculto");
ok(cerca(), "arranca en el encuadre de 40 m");
ok(nodos["#chipctx"].src.includes("chips_ctx/"), "el contexto sale de chips_ctx/");
tecla("z");
ok(!cerca(), "'z' aleja a 120 m");
ok(nodos["#encuadre"].innerHTML.includes("120"), "   y lo dice en pantalla");
tecla("z");
ok(cerca(), "'z' otra vez vuelve a 40 m");
tecla(" ");
ok(!cerca(), "la barra espaciadora hace lo mismo");
ok(Object.keys(resp()).length === n0, "alejar no crea ni cambia respuestas");
nodos["#chipctx"].onclick();
ok(cerca(), "hacer clic en el contexto vuelve al encuadre corto");
tecla("z");
const posAntes = estado();
tecla("2");
ok(estado() !== posAntes && cerca(),
   "al pasar de punto vuelve solo a 40 m: el zoom no se queda pegado");

console.log("\npersistencia");
const guardado = resp();
// se calcula en vez de codificarlo: si arriba se anade o quita un caso de prueba,
// la posicion esperada cambia y una constante daria un fallo enganoso
const esperada = PUNTOS.findIndex(p => !guardado[p.id]) + 1;
vivo = carga();   // simula cerrar y volver a abrir la pagina
ok(Object.keys(resp()).length === Object.keys(guardado).length,
   "al recargar recupera el progreso de localStorage");
ok(estado().includes("posición " + esperada),
   `   y reanuda en la primera sin responder (${esperada}), no en la 1`);

console.log("\nexportacion");
vm.runInContext("exporta()", vivo);
const lineas = ultimoBlob.trim().split("\n");
ok(lineas[0] === "id,clase,tipo,ms", "cabecera del CSV");
ok(lineas.length === 1 + Object.keys(resp()).length, "una fila por respuesta");
ok(lineas.slice(1).every(l => l.split(",").length === 4), "cuatro columnas en todas");
if (PIDE_TIPO) ok(lineas.some(l => l.includes("arbol,frondosa")),
                  "el tipo viaja en el CSV");
ok(lineas.slice(1).every(l => { const t = l.split(",")[2];
                                return t === "" || TIPOS.includes(t); }),
   "todos los tipos exportados son de la lista de categorias");
console.log("   muestra: " + lineas.slice(0, 3).join(" | "));

console.log("\ncompletar la muestra");
let guardia = 0;
while (Object.keys(resp()).length < PUNTOS.length && guardia++ < 3000) tecla("2");
ok(Object.keys(resp()).length === 400, "se pueden anotar los 400 sin bloquearse");
ok(nodos["#fin"]._clases.has("oculto") === false, "al acabar sale la pantalla final");
ok(nodos["#resumen"].textContent.includes("400 puntos anotados"), "y el resumen");
console.log("   " + nodos["#resumen"].textContent);

console.log(fallos === 0 ? "\nTODO OK\n" : `\n${fallos} FALLOS\n`);
process.exit(fallos ? 1 : 0);
