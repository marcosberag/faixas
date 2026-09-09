"""Genera el HTML de anotacion de las hojas de persistencia.

Protocolo, igual de ciego que en las fases anteriores:
  - Se ensenha la hoja de contacto (2010 -> hoy) y se pregunta si se ve un
    REEMPLAZO del dosel dentro del rodal: corta rasa, incendio, plantacion
    nueva. NO cuenta el aclareo leve ni el cambio de tono estacional.
  - Umbral de superficie: "si" cuando el reemplazo cubre a ojo UN TERCIO o
    mas del rodal. El detector va sobre la media de NDVI del rodal: una corta
    baja el NDVI local 0,4-0,5 desde ~0,78, asi que mover la media 0,18 exige
    ~40 % del area. Por debajo de eso es ciego por diseno, y anotarlo como
    "si" mediria al detector contra algo que no puede ver. Calva menor: "no";
    sin claridad sobre si llega al tercio: "dudoso".
  - El CRECIMIENTO no es reemplazo: un rodal joven que se cierra es "no" (la
    etiqueta de 2010 sigue valiendo y al detector el crecimiento le sube el
    NDVI). Una plantacion nueva sobre suelo antes raso SI es reemplazo (filas
    regulares = plantacion; cierre gradual e irregular = crecimiento).
  - Si la respuesta es "si", se marca EN QUE INTERVALO(S) se ve el cambio.
    Eso es lo que permite separar despues un fallo del detector (cambio en
    2017-2026 que no detecto) de un evento anterior a la serie S2 (cambio en
    2010-2017, que el detector no puede ver y esta declarado como hueco).
  - El HTML solo recibe los ids y el orden barajado: ni estado, ni especie,
    ni NDVI viajan al anotador.

El CSV descargado se guarda en datos/procesado/validacion_persistencia/
(SIEMPRE en la carpeta de SU muestra: ver la trampa del anotacion.csv en
CLAUDE.md).

Uso:
    python scripts/anotador_persistencia.py
"""
import json
import pathlib

import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VAL = RAIZ / "datos" / "procesado" / "validacion_persistencia"

INTERVALOS = ["2010-2014", "2014-2017", "2017-2020", "2020-2023", "2023-hoy"]

PLANTILLA = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Anotación — persistencia</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#14161a; color:#e8e6e1;
         font:15px/1.45 system-ui, sans-serif; }
  header { padding:10px 18px; background:#1d2026; display:flex; gap:18px;
           align-items:center; flex-wrap:wrap; }
  header b { font-size:17px; }
  #prog { flex:1; height:8px; background:#2a2e36; border-radius:4px;
          min-width:160px; }
  #prog i { display:block; height:100%; background:#22A465; border-radius:4px;
            width:0; }
  main { display:flex; flex-direction:column; align-items:center;
         padding:12px 16px 40px; }
  #hoja { max-width:98vw; max-height:74vh; border:1px solid #333;
          border-radius:6px; }
  #panel { margin-top:12px; text-align:center; }
  .tecla { display:inline-block; background:#2a2e36; border:1px solid #444;
           border-radius:5px; padding:2px 9px; margin:0 3px; font-weight:600; }
  #badge { display:inline-block; min-width:110px; padding:3px 12px;
           border-radius:12px; background:#2a2e36; margin-left:10px; }
  .no  { background:#20415a !important; }
  .si  { background:#5a2820 !important; }
  .dudoso { background:#55491e !important; }
  #ivs { display:none; margin-top:10px; }
  #ivs.abierto { display:block; }
  .iv { display:inline-block; padding:6px 14px; margin:4px; border-radius:6px;
        background:#23262d; border:2px solid #3a3f49; cursor:pointer; }
  .iv.sel { border-color:#22A465; background:#1c3a2b; }
  #fin { display:none; margin-top:18px; padding:16px 22px; background:#1c3a2b;
         border-radius:8px; text-align:center; }
  button { font:inherit; padding:8px 18px; border-radius:6px; border:0;
           background:#22A465; color:#08130d; font-weight:700; cursor:pointer; }
  .aviso { color:#c9a53d; }
  small { color:#9aa0aa; }
</style></head><body>
<header>
  <b>Persistencia — ¿reemplazo del dosel?</b>
  <span id="pos"></span>
  <div id="prog"><i></i></div>
  <span><span class="tecla">n</span>no <span class="tecla">s</span>sí
        <span class="tecla">d</span>dudoso <span class="tecla">←</span><span class="tecla">→</span>navegar</span>
  <button onclick="descarga()">Descargar CSV</button>
</header>
<main>
  <img id="hoja" alt="hoja de contacto">
  <div id="panel">
    ¿Se ve un <b>reemplazo del dosel</b> dentro del rodal (corta rasa, incendio,
    plantación) en algún punto de la serie?
    <span id="badge">sin responder</span>
    <div><small>El aclareo leve y el cambio de tono estacional NO cuentan.
    Juzga solo lo de dentro del contorno amarillo. Cuenta como <b>sí</b> a
    partir de ~1/3 del rodal reemplazado; una calva menor es <b>no</b>, y si
    no está claro si llega al tercio, <b>dudoso</b>. El crecimiento (dosel que
    se cierra) es <b>no</b>; una plantación nueva sobre suelo antes raso es
    <b>sí</b> (filas regulares delatan plantación).</small></div>
    <div id="ivs">
      ¿En qué intervalo(s) se ve el cambio? (teclas 1–5, <span class="tecla">Enter</span> confirma)<br>
      <span id="cajas"></span>
      <div><small id="pista"></small></div>
    </div>
  </div>
  <div id="fin">
    <b>Anotación completa.</b><br>Descarga el CSV y guárdalo como<br>
    <code>datos/procesado/validacion_persistencia/anotacion.csv</code><br>
    <span class="aviso">— en ESA carpeta, no en validacion/ ni en
    validacion_producto/ —</span><br><br>
    <button onclick="descarga()">Descargar CSV</button>
  </div>
</main>
<script>
const IDS = __IDS__;
const IVS = __INTERVALOS__;
const KEY = "persistencia_v1";
// localStorage puede estar bloqueado en file:// segun el navegador: si lo
// esta, se anota igual en memoria (sin reanudar entre sesiones) en vez de
// morir al cargar. El CSV descargado es el registro que vale.
let alm;
try { alm = window.localStorage; alm.setItem("__t", "1"); alm.removeItem("__t"); }
catch (e) {
  alm = { _m: {}, getItem(k) { return this._m[k] || null; },
          setItem(k, v) { this._m[k] = v; } };
}
let resp = JSON.parse(alm.getItem(KEY) || "{}");
let i = 0, t0 = Date.now(), sel = new Set();
while (i < IDS.length && resp[IDS[i]]) i++;
if (i >= IDS.length) i = 0;

const $ = id => document.getElementById(id);
const cajas = $("cajas");
IVS.forEach((v, k) => {
  const s = document.createElement("span");
  s.className = "iv"; s.id = "iv" + k;
  s.textContent = (k + 1) + " · " + v;
  s.onclick = () => alterna(k);
  cajas.appendChild(s);
});

function pinta() {
  $("hoja").src = "hojas/" + IDS[i] + ".png";
  $("pos").textContent = IDS[i] + "  (" + (i + 1) + "/" + IDS.length + ")";
  const n = Object.keys(resp).length;
  $("prog").firstElementChild.style.width = (100 * n / IDS.length) + "%";
  const r = resp[IDS[i]];
  const b = $("badge");
  b.className = r ? r.respuesta : "";
  b.textContent = r ? (r.respuesta + (r.intervalos.length ? ": " + r.intervalos.join(", ") : ""))
                    : "sin responder";
  $("ivs").className = "";
  document.querySelectorAll(".iv").forEach(e => e.className = "iv");
  $("fin").style.display = n >= IDS.length ? "block" : "none";
  t0 = Date.now();
}

function alterna(k) {
  sel.has(k) ? sel.delete(k) : sel.add(k);
  $("iv" + k).className = sel.has(k) ? "iv sel" : "iv";
  $("pista").textContent = "";
}

function guarda(r, ints) {
  resp[IDS[i]] = { respuesta: r, intervalos: ints,
                   t_ms: Date.now() - t0 };
  alm.setItem(KEY, JSON.stringify(resp));
  if (i < IDS.length - 1) i++;
  pinta();
}

document.addEventListener("keydown", ev => {
  const abierto = $("ivs").className === "abierto";
  if (ev.key === "ArrowLeft" && i > 0) { i--; pinta(); return; }
  if (ev.key === "ArrowRight" && i < IDS.length - 1) { i++; pinta(); return; }
  if (abierto) {
    const k = "12345".indexOf(ev.key);
    if (k >= 0 && k < IVS.length) { alterna(k); return; }
    if (ev.key === "Enter") {
      if (!sel.size) { $("pista").textContent =
        "marca al menos un intervalo (1–5), o responde d si no está claro"; return; }
      guarda("si", [...sel].sort().map(k => IVS[k]));
    }
    if (ev.key === "Escape") pinta();
    return;
  }
  if (ev.key === "n") guarda("no", []);
  if (ev.key === "d") guarda("dudoso", []);
  if (ev.key === "s") {
    sel = new Set();
    $("ivs").className = "abierto";
    $("pista").textContent = "";
  }
});

function descarga() {
  let filas = ["id,respuesta,intervalos,t_ms"];
  for (const id of IDS) {
    const r = resp[id];
    if (!r) continue;
    filas.push([id, r.respuesta, r.intervalos.join("|"), r.t_ms].join(","));
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([filas.join("\\n")], { type: "text/csv" }));
  a.download = "anotacion.csv";
  a.click();
}
pinta();
</script></body></html>
"""

if __name__ == "__main__":
    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig")
    # al HTML solo viajan los ids, ya barajados en la muestra: nada de estado,
    # especie ni NDVI (protocolo ciego)
    html = (PLANTILLA
            .replace("__IDS__", json.dumps(list(m.id)))
            .replace("__INTERVALOS__", json.dumps(INTERVALOS)))
    ruta = VAL / "anotacion.html"
    ruta.write_text(html, encoding="utf-8")
    print(f"{len(m)} hojas en el anotador")
    print(f"-> {ruta.relative_to(RAIZ)}  (abrir en el navegador)")
