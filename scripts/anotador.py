"""Genera el anotador HTML para fotointerpretar la muestra de validacion.

Produce `datos/procesado/validacion/anotador.html`, que se abre en el navegador
con doble clic. No necesita servidor: carga los chips como ficheros relativos y
guarda el progreso en localStorage del propio navegador.

DECISIONES QUE AFECTAN A LA VALIDEZ DEL RESULTADO
-------------------------------------------------

1. CIEGO, Y SIN EXCEPCIONES. La altura del CHM no aparece en ningun momento, ni
   siquiera despues de responder. El orden viene barajado de
   `muestra_validacion.py`, asi que tampoco se puede inferir por la secuencia.

   Hubo aqui un boton de "revelar el CHM" que se activaba solo tras responder.
   Esta quitado a proposito: aunque no sesga el chip que ya has contestado, te
   ensena la relacion entre lo que ves y lo que dice el LiDAR, y a partir de ahi
   contamina todos los siguientes. Las discrepancias se miran al final, con
   `revisa_discrepancias.py`, cuando la anotacion ya esta cerrada.

2. CRITERIO A LA VISTA. El recordatorio esta permanentemente en pantalla. En 400
   chips el criterio deriva sin que uno se de cuenta — sobre todo la frontera
   entre matorral alto y arbolito — y una deriva a mitad de muestra sesga la
   calibracion sin dejar rastro.

3. CUATRO CATEGORIAS, no dos. "Edificacion" va aparte de "no arbol" porque es un
   falso positivo de naturaleza distinta: el CHM ve el tejado y acierta en la
   altura, pero no es vegetacion. Separarlo permite dar las dos cifras.
   "Dudoso" existe para que nadie se vea obligado a inventar: se declaran y se
   excluyen del calculo principal, y su porcentaje se publica.

4. TIPO DE COPA como pregunta secundaria. La ley exime a las frondosas no
   listadas (disp. ad. 3a, punto 3), asi que un castanhar dentro de la faixa es
   legal. Quien ya esta mirando la ortofoto puede decir de que tipo es la copa
   casi sin coste, y eso le da a la fase 3 una verdad de referencia gratis.

   LAS CATEGORIAS VAN POR ESTATUS LEGAL, NO POR BOTANICA. La primera version
   ofrecia "conifera o eucalipto" frente a "frondosa caducifolia", y estaba mal:
   la ACACIA (mimosa) es una frondosa y esta en la lista prohibida, asi que quien
   supiera botanica la habria marcado como frondosa, o sea como exenta, que es
   exactamente lo contrario. Ahora la acacia tiene su propia tecla y las tres
   opciones prohibidas van marcadas en rojo. El eucalipto tampoco es una conifera
   y estaba metido en esa casilla; ahora va aparte.

5. TIEMPO POR CHIP. Se registra. Una racha de respuestas de menos de un segundo
   es senhal de fatiga y conviene poder detectarla al analizar.

   Y ES OPCIONAL. No entra ni en el umbral ni en la tasa de falsos positivos,
   que es lo unico que la fase 2 tiene que entregar. Con `--sin-tipo` no se
   pregunta siquiera. Etiquetar con dudas seria peor que no etiquetar: la
   fase 3 acabaria entrenando contra ruido, y eso no se detecta despues.
   El clasificador de especie de verdad sera el infrarrojo del propio LiDAR.

Uso:
    python scripts/anotador.py
    python scripts/anotador.py --sin-tipo   # solo arbol / no arbol
"""
import argparse
import json
import pathlib

import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VAL = RAIZ / "datos" / "procesado" / "validacion"

PAGINA = """<!doctype html>
<meta charset="utf-8">
<title>Anotador de validacion — faixas</title>
<style>
  :root {
    --fondo: #14171a; --panel: #1e2328; --borde: #2f3740;
    --texto: #e6e9ec; --suave: #98a2ad; --acento: #5aa9e6;
    --si: #4caf7d; --no: #d98555; --edif: #b07cc6; --duda: #7d8894;
    --alerta: #e0574f;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fondo); color: var(--texto);
         font: 15px/1.5 system-ui, -apple-system, Segoe UI, sans-serif; }
  header { display: flex; align-items: center; gap: 18px; padding: 10px 18px;
           background: var(--panel); border-bottom: 1px solid var(--borde); }
  .barra { flex: 1; height: 7px; background: #2a3138; border-radius: 4px; overflow: hidden; }
  .barra > div { height: 100%; width: 0; background: var(--acento); transition: width .15s; }
  .cifra { font-variant-numeric: tabular-nums; color: var(--suave); font-size: 13px; }
  main { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 20px;
         padding: 20px; max-width: 1080px; margin: 0 auto; align-items: start; }
  .lienzo { position: relative; background: #000; border: 1px solid var(--borde);
            border-radius: 8px; overflow: hidden; aspect-ratio: 1; }
  .lienzo img { width: 100%; height: 100%; display: block; }
  .lienzo img.oculto { display: none; }
  .id { position: absolute; right: 12px; top: 10px; color: #fff; font-size: 12px;
        text-shadow: 0 0 4px #000; font-variant-numeric: tabular-nums; }
  .encuadre { position: absolute; left: 12px; top: 10px; color: #fff; font-size: 12px;
        text-shadow: 0 0 4px #000; font-variant-numeric: tabular-nums; }
  .encuadre b { color: #ffff3c; }
  aside { display: flex; flex-direction: column; gap: 8px; }
  button.op { display: flex; align-items: center; gap: 11px; width: 100%;
      padding: 11px 13px; border: 1px solid var(--borde); border-radius: 7px;
      background: var(--panel); color: var(--texto); font: inherit;
      cursor: pointer; text-align: left; }
  button.op:hover { border-color: var(--acento); }
  kbd { background: #2c343c; border: 1px solid #3d4650; border-radius: 4px;
        padding: 1px 7px; font: 12.5px ui-monospace, monospace; }
  button.op kbd { min-width: 26px; text-align: center; }
  button.op b { font-weight: 600; }
  button.op small { display: block; color: var(--suave); font-size: 12px;
      font-weight: 400; line-height: 1.35; }
  .p1 kbd { color: var(--si); } .p2 kbd { color: var(--no); }
  .p3 kbd { color: var(--edif); } .p4 kbd { color: var(--duda); }
  /* el color va por estatus legal, no por botanica: la acacia es una frondosa y
     esta prohibida, y esa es justamente la confusion que hay que evitar */
  .t-mal  { border-left: 4px solid var(--alerta) !important; }
  .t-bien { border-left: 4px solid var(--si) !important; }
  .grupo { margin-top: 6px; font-size: 12px; text-transform: uppercase;
      letter-spacing: .09em; color: var(--suave); }
  .criterio { background: var(--panel); border: 1px solid var(--borde);
      border-radius: 7px; padding: 11px 13px; font-size: 12.5px; color: var(--suave); }
  .criterio b { color: var(--texto); }
  .aviso { background: #3a1f1d; border: 1px solid var(--alerta); color: #f3cdc9;
      border-radius: 7px; padding: 11px 13px; font-size: 13px; }
  .pie { grid-column: 1 / -1; display: flex; gap: 10px; align-items: center;
      flex-wrap: wrap; border-top: 1px solid var(--borde); padding-top: 14px;
      font-size: 13px; color: var(--suave); }
  .pie button { padding: 8px 15px; border-radius: 6px; border: 1px solid var(--borde);
      background: var(--panel); color: var(--texto); font: inherit; cursor: pointer; }
  .pie button.primario { background: var(--acento); border-color: var(--acento);
      color: #08131c; font-weight: 600; }
  .oculto { display: none !important; }
  .fin { text-align: center; padding: 60px 20px; }
  .fin h2 { font-size: 22px; margin: 0 0 10px; }
  .fin p { color: var(--suave); }
</style>

<header>
  <strong>Validación de faixas</strong>
  <div class="barra"><div id="prog"></div></div>
  <span class="cifra" id="contador"></span>
  <span class="cifra" id="ritmo"></span>
</header>

<main id="pantalla">
  <div>
    <div class="lienzo">
      <img id="chip" alt="">
      <img id="chipctx" class="oculto" alt="">
      <span class="encuadre" id="encuadre"></span>
      <span class="id" id="etiqueta"></span>
    </div>
  </div>

  <aside>
    <div id="alerta" class="aviso oculto"></div>

    <div id="pregunta1">
      <div class="grupo">¿Qué hay justo en la mira?</div>
      <button class="op p1" data-v="arbol"><kbd>1</kbd><b>Árbol
        <small>copa de individuo leñoso con porte arbóreo</small></b></button>
      <button class="op p2" data-v="no"><kbd>2</kbd><b>No árbol
        <small>prado, cultivo, matorral, roca, camino, agua, suelo</small></b></button>
      <button class="op p3" data-v="edificacion"><kbd>3</kbd><b>Edificación
        <small>tejado, nave, muro, vehículo, estructura</small></b></button>
      <button class="op p4" data-v="dudoso"><kbd>4</kbd><b>Dudoso
        <small>sombra, nube, borde, no se puede decidir</small></b></button>
    </div>

    <div id="pregunta2" class="oculto">
      <div class="grupo">¿Qué tipo de copa?</div>
      <button class="op t-mal" data-t="pino"><kbd>1</kbd><b>Pino u otra conífera
        <small>copa estrellada, verde oscuro, 20–25 m</small></b></button>
      <button class="op t-mal" data-t="eucalipto"><kbd>2</kbd><b>Eucalipto
        <small>rala y despeinada, azulada, 30–50 m</small></b></button>
      <button class="op t-mal" data-t="acacia"><kbd>3</kbd><b>Acacia o mimosa
        <small>manta continua fina y plateada, sin copas sueltas</small></b></button>
      <button class="op t-bien" data-t="frondosa"><kbd>4</kbd><b>Frondosa caducifolia
        <small>castaño, roble, ribera. La única EXENTA</small></b></button>
      <button class="op" data-t="nd"><kbd>5</kbd><b>No distinguible</b></button>
    </div>

    <div class="criterio" id="recuerda-tipo">
      <b>El tipo de copa es opcional.</b> No entra en el umbral ni en la tasa de
      falsos positivos. Si no lo ves clarísimo, <kbd>5</kbd> y a seguir:
      etiquetar con dudas es peor que no etiquetar.
    </div>

    <div class="criterio">
      <b>La rejilla da la escala.</b> Cada casilla son 10 m, y el círculo de la
      mira mide 3 m de diámetro. Una copa de pino adulto llena media casilla.<br><br>
      <b>Matorral no es árbol.</b> Tojo, brezo y zarza forman manta continua sin
      copa individual ni sombra propia: van en <i>No árbol</i> aunque levanten
      dos metros.<br><br>
      <b>Sombra no es vegetación.</b> La sombra sobre suelo conserva el tono del
      suelo, solo más oscuro. Si es verde, hay planta.<br><br>
      <b>Decide solo el centro de la mira</b>, no lo que la rodea.<br><br>
      <b>No adivines.</b> Si dudas, <kbd>4</kbd>. Los dudosos se declaran y se
      excluyen; forzar la respuesta es lo que estropea la calibración.
    </div>

    <div class="criterio">
      <kbd>z</kbd> alejar a 120 m y volver · <kbd>←</kbd> volver ·
      <kbd>→</kbd> saltar sin responder.
      Puedes cerrar y seguir después: el progreso se guarda solo.
    </div>
  </aside>

  <div class="pie">
    <button id="atras">← Volver</button>
    <button id="saltar">Saltar →</button>
    <span id="estado"></span>
    <span style="flex:1"></span>
    <button id="exportar" class="primario">Descargar CSV</button>
    <button id="borrar">Borrar progreso</button>
  </div>
</main>

<div class="fin oculto" id="fin">
  <h2>Muestra completa</h2>
  <p id="resumen"></p>
  <p style="margin-top:24px">
    <button class="primario" id="exportar2"
      style="padding:11px 22px;border:0;border-radius:7px;font:inherit;font-weight:600;cursor:pointer">
      Descargar CSV</button>
    <button id="revisar"
      style="padding:11px 22px;border-radius:7px;font:inherit;cursor:pointer">
      Revisar desde el principio</button></p>
  <p style="font-size:13px">Guarda el CSV en <code>datos/procesado/validacion/</code>
     y corre <code>python scripts/calibra_umbral.py</code>.</p>
</div>

<script>
const PUNTOS = __DATOS__;
const CLAVE  = "faixas-validacion-__FIRMA__";
// la subpregunta de tipo de copa es opcional: no entra en el umbral ni en la
// tasa de falsos positivos, que es lo que la fase 2 tiene que entregar
const PIDE_TIPO = __PIDE_TIPO__;

let resp = {}, i = 0, t0 = Date.now(), esperandoTipo = false, persiste = true;
let lejos = false;   // si se esta mirando el encuadre de 120 m
// si el punto que se esta respondiendo era nuevo o se esta revisando: lo decide
// `responde` y lo necesita `respondeTipo`, que llega un clic despues
let pendiente = true;

const $ = s => document.querySelector(s);

// localStorage puede estar capado al abrir con file:// segun navegador y ajustes.
// Si lo esta hay que decirlo ANTES de que alguien anote 300 chips y los pierda.
try {
  localStorage.setItem(CLAVE + "-test", "1");
  localStorage.removeItem(CLAVE + "-test");
  resp = JSON.parse(localStorage.getItem(CLAVE) || "{}");
} catch (e) {
  persiste = false;
}

function guarda() {
  if (!persiste) return;
  try { localStorage.setItem(CLAVE, JSON.stringify(resp)); }
  catch (e) { persiste = false; alerta(); }
}

function alerta() {
  if (persiste) return;
  const a = $("#alerta");
  a.classList.remove("oculto");
  a.innerHTML = "<b>El navegador no deja guardar el progreso.</b> "
    + "Si cierras la pestaña lo pierdes todo. Descarga el CSV a menudo, "
    + "o sirve la carpeta con <code>python -m http.server</code> y ábrela "
    + "por <code>localhost</code>.";
}

function encuadra(ancho) {
  lejos = ancho;
  $("#chip").classList.toggle("oculto", lejos);
  $("#chipctx").classList.toggle("oculto", !lejos);
  $("#encuadre").innerHTML = lejos
    ? "120 × 120 m · rejilla <b>20 m</b>" : "40 × 40 m · rejilla <b>10 m</b>";
}

function pinta() {
  const p = PUNTOS[i], r = resp[p.id];
  $("#chip").src = "chips/" + p.id + ".jpg";
  $("#chipctx").src = "chips_ctx/" + p.id + ".jpg";
  // cada punto arranca en el encuadre corto: si el zoom se quedara pegado, se
  // acabarian juzgando unos puntos de cerca y otros de lejos sin darse cuenta
  encuadra(false);
  $("#etiqueta").textContent = p.id;
  esperandoTipo = false;
  $("#pregunta1").classList.remove("oculto");
  $("#pregunta2").classList.add("oculto");

  const hechas = Object.keys(resp).length;
  $("#prog").style.width = (100 * hechas / PUNTOS.length) + "%";
  $("#contador").textContent = hechas + " / " + PUNTOS.length;
  const ts = Object.values(resp).map(r => r.ms).filter(m => m > 0 && m < 60000);
  $("#ritmo").textContent = ts.length
    ? (ts.reduce((a, b) => a + b, 0) / ts.length / 1000).toFixed(1) + " s/chip" : "";

  $("#estado").textContent = "posición " + (i + 1) + (r
    ? " — respondido: " + r.clase + (r.tipo ? " / " + r.tipo : "") : "");
  t0 = Date.now();
  if (i + 1 < PUNTOS.length) new Image().src = "chips/" + PUNTOS[i + 1].id + ".jpg";
}

$("#chip").onclick = () => encuadra(true);
$("#chipctx").onclick = () => encuadra(false);

function ir(k) {
  $("#fin").classList.add("oculto");
  $("#pantalla").classList.remove("oculto");
  i = Math.max(0, Math.min(PUNTOS.length - 1, k));
  pinta();
}

function siguienteSinResponder(desde) {
  for (let k = desde; k < PUNTOS.length; k++) if (!resp[PUNTOS[k].id]) return k;
  return PUNTOS.findIndex(p => !resp[p.id]);   // -1 si no queda ninguno
}

function avanza(eraNuevo) {
  // al revisar (el punto ya estaba respondido) se avanza de uno en uno, que es lo
  // que uno espera; al anotar en serie se salta a la siguiente sin responder
  const k = eraNuevo ? siguienteSinResponder(i + 1) : i + 1;
  if (k < 0) return terminar();
  if (k >= PUNTOS.length) return terminar();
  ir(k);
}

function responde(clase) {
  const p = PUNTOS[i], eraNuevo = !resp[p.id];
  resp[p.id] = { clase, ms: Date.now() - t0 };
  guarda();
  if (clase === "arbol" && PIDE_TIPO) {
    // la subpregunta solo aplica si hay copa que clasificar
    esperandoTipo = true;
    $("#pregunta1").classList.add("oculto");
    $("#pregunta2").classList.remove("oculto");
    pendiente = eraNuevo;
  } else {
    avanza(eraNuevo);
  }
}

function respondeTipo(tipo) {
  resp[PUNTOS[i].id].tipo = tipo;
  guarda();
  avanza(pendiente);
}

function terminar() {
  $("#pantalla").classList.add("oculto");
  $("#fin").classList.remove("oculto");
  const c = {};
  Object.values(resp).forEach(r => c[r.clase] = (c[r.clase] || 0) + 1);
  const n = Object.keys(resp).length;
  $("#resumen").textContent = n + " puntos anotados · "
    + Object.entries(c).map(([k, v]) =>
        k + ": " + v + " (" + (100 * v / n).toFixed(0) + " %)").join(" · ");
}

function exporta() {
  const filas = PUNTOS.filter(p => resp[p.id]).map(p => {
    const r = resp[p.id];
    return [p.id, r.clase, r.tipo || "", r.ms].join(",");
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(
    new Blob(["id,clase,tipo,ms\\n" + filas.join("\\n") + "\\n"],
             {type: "text/csv;charset=utf-8"}));
  a.download = "anotacion.csv";
  a.click();
}

document.querySelectorAll("#pregunta1 .op").forEach(b =>
  b.onclick = () => responde(b.dataset.v));
document.querySelectorAll("#pregunta2 .op").forEach(b =>
  b.onclick = () => respondeTipo(b.dataset.t));
$("#atras").onclick = () => ir(i - 1);
$("#saltar").onclick = () => ir(i + 1);
$("#exportar").onclick = exporta;
$("#exportar2").onclick = exporta;
$("#revisar").onclick = () => ir(0);
$("#borrar").onclick = () => {
  if (confirm("¿Borrar las " + Object.keys(resp).length + " respuestas?")) {
    resp = {}; guarda(); ir(0);
  }
};

document.onkeydown = ev => {
  if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
  if (ev.key === "ArrowLeft")  { ev.preventDefault(); return ir(i - 1); }
  if (ev.key === "ArrowRight") { ev.preventDefault(); return ir(i + 1); }
  if (ev.key === "z" || ev.key === "Z" || ev.key === " ") {
    ev.preventDefault(); return encuadra(!lejos);
  }
  if (esperandoTipo) {
    const t = {"1": "pino", "2": "eucalipto", "3": "acacia",
               "4": "frondosa", "5": "nd"}[ev.key];
    if (t) respondeTipo(t);
    return;
  }
  const c = {"1": "arbol", "2": "no", "3": "edificacion", "4": "dudoso"}[ev.key];
  if (c) responde(c);
};

alerta();
if (!PIDE_TIPO) $("#recuerda-tipo").classList.add("oculto");
const inicio = siguienteSinResponder(0);
if (inicio < 0) { ir(0); terminar(); } else { ir(inicio); }
</script>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-tipo", action="store_true",
                    help="no preguntar el tipo de copa: solo arbol / no arbol")
    ap.add_argument("--dir", default="validacion",
                    help="subcarpeta de datos/procesado con muestra.csv y chips")
    args = ap.parse_args()
    VAL = RAIZ / "datos" / "procesado" / args.dir

    m = pd.read_csv(VAL / "muestra.csv", encoding="utf-8-sig").sort_values("orden")
    faltan = [f.id for f in m.itertuples() if not (VAL / "chips" / f"{f.id}.jpg").exists()]
    if faltan:
        raise SystemExit(f"faltan {len(faltan)} chips: corre antes chips_validacion.py")

    # solo los id, y en el orden barajado. La altura del CHM NO viaja al HTML:
    # si no esta ahi, no hay forma de ensenarla ni por accidente ni mirando el
    # codigo fuente a media anotacion
    datos = [{"id": f.id} for f in m.itertuples()]
    # la firma ata el localStorage a esta muestra: si se resortea con otra semilla,
    # las respuestas viejas no se mezclan con los chips nuevos
    firma = f"{len(m)}-{int(m.chm_m.sum() * 100) % 1000000}"

    html = (PAGINA
            .replace("__DATOS__", json.dumps(datos, separators=(",", ":")))
            .replace("__FIRMA__", firma)
            .replace("__PIDE_TIPO__", "false" if args.sin_tipo else "true"))
    salida = VAL / "anotador.html"
    salida.write_text(html, encoding="utf-8")

    print(f"{len(m)} puntos, firma {firma}")
    if args.sin_tipo:
        print("sin la subpregunta de tipo de copa: solo arbol / no arbol.")
        print("  El umbral y la tasa de falsos positivos salen igual; lo que")
        print("  no habra es cota del sesgo de especie desde esta muestra.")
    print(f"-> {salida.relative_to(RAIZ)}   ({salida.stat().st_size/1024:.0f} KB)")
    print(f"\nabrelo con doble clic:\n  {salida}")
