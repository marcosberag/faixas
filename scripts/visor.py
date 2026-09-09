"""Genera el visor web estatico: salidas/visor/index.html (autocontenido).

Un solo fichero HTML que se abre en el navegador (o se sube tal cual a
cualquier hosting estatico): Leaflet desde CDN, ortofoto PNOA del IGN como
fondo (WMTS publico), parroquias coloreadas por el punto medio de las cotas
del ranking, y los puntos de inspeccion de puntos_inspeccion.py con su ficha.

Los datos van INCRUSTADOS como GeoJSON en el propio HTML (parroquias
disueltas y simplificadas a 10 m, reproyectadas a WGS84): sin servidor, sin
ficheros aparte, sin CORS.

Uso:
    python scripts/visor.py
"""
import json
import pathlib
import warnings

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PROC = RAIZ / "datos" / "procesado"
MET = PROC / "metricas"
SALIDA = RAIZ / "salidas" / "visor"


def parroquias_geojson():
    fx = gpd.GeoDataFrame(pd.concat(
        [gpd.read_file(PROC / f"faixas_{n}_paradanta_ok.gpkg")
         for n in ("nucleos", "illadas")], ignore_index=True), crs="EPSG:25829")
    dis = fx.dissolve(by=["NOMECONCEL", "PARROQUIA"]).reset_index()
    dis["geometry"] = dis.geometry.simplify(10)

    r = pd.read_csv(MET / "ranking_final.csv", encoding="utf-8-sig")
    dis = dis.merge(r, left_on=["NOMECONCEL", "PARROQUIA"],
                    right_on=["concello", "parroquia"], how="left")
    cols = ["NOMECONCEL", "PARROQUIA", "puesto", "ha_medida", "ha_arbolado",
            "ha_sobre_35m", "ha_prohibida_min", "ha_prohibida_max",
            "ha_prohibida_punto_medio", "geometry"]
    dis = dis[cols].to_crs("EPSG:4326")
    return json.loads(dis.to_json(drop_id=True))


def puntos_geojson():
    g = gpd.read_file(MET / "puntos_inspeccion.gpkg").to_crs("EPSG:4326")
    g = g.round({"ha": 2})
    return json.loads(g.to_json(drop_id=True))


def areas_geojson():
    """Las MANCHAS, aligeradas para caber en el HTML.

    Son el arbolado real, o sea recortes de raster: 7.300 poligonos y medio
    millon de vertices en escalera de 1 m. Tal cual pesan 6,5 MB de GeoJSON.
    Un cierre morfologico (buffer +3 / -3) funde los trozos vecinos que el ojo
    ve como una mancha sola, y despues se simplifica. Se hace EN METROS y
    antes de reproyectar: en grados, una tolerancia de 3 aplana el pais.
    """
    ruta = MET / "areas_inspeccion.gpkg"
    if not ruta.exists():
        return {"type": "FeatureCollection", "features": []}
    g = gpd.read_file(ruta)
    g["geometry"] = g.geometry.buffer(3).buffer(-3).simplify(2.5)
    g = g[~g.geometry.is_empty]
    g = g[["tipo", "ha", "PARROQUIA", "NOMECONCEL", "geometry"]].to_crs("EPSG:4326")
    return json.loads(g.round({"ha": 2}).to_json(drop_id=True))


PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Faixas — A Paradanta</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { height: 100%; margin: 0; font-family: system-ui, sans-serif; }
  #mapa { height: 100%; }
  .cabecera {
    position: absolute; top: 10px; left: 54px; right: 10px; z-index: 1000;
    background: rgba(255,255,255,.94); border-radius: 8px; padding: 10px 16px;
    box-shadow: 0 1px 6px rgba(0,0,0,.25); max-width: 520px;
  }
  .cabecera h1 { margin: 0; font-size: 17px; }
  .cabecera p { margin: 4px 0 0; font-size: 12.5px; color: #444; }
  .leyenda {
    background: rgba(255,255,255,.94); border-radius: 6px; padding: 10px 12px;
    font-size: 12px; line-height: 1.5; box-shadow: 0 1px 4px rgba(0,0,0,.3);
  }
  .leyenda i { width: 14px; height: 14px; display: inline-block;
               vertical-align: -2px; margin-right: 6px; border-radius: 3px; }
  .leyenda .pto { border-radius: 50%; border: 2.5px solid; background: none;
                  width: 10px; height: 10px; }
  .popup-tit { font-weight: 600; margin-bottom: 4px; }
  .popup-fila { display: flex; justify-content: space-between; gap: 14px; }
  .popup-fila span:last-child { font-variant-numeric: tabular-nums; font-weight: 600; }
  .aviso-pie {
    position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
    z-index: 1000; background: rgba(30,30,30,.85); color: #eee; font-size: 11px;
    padding: 4px 12px; border-radius: 12px; white-space: nowrap;
  }
</style>
</head>
<body>
<div id="mapa"></div>
<div class="cabecera">
  <h1>Franjas de biomasa con arbolado prohibido — A Paradanta</h1>
  <p>Indicador de riesgo para priorizar inspeccion (Ley 3/2007). Parroquias por
     hectareas estimadas (punto medio de cotas) y puntos concretos de inspeccion.
     <b>No acredita infraccion</b>: la ley admite excepciones que ningun sensor evalua.</p>
</div>
<div class="aviso-pie">LiDAR y ortofoto PNOA © IGN · faixas © Xunta de Galicia · IFN4 · elaboracion propia</div>
<script>
const PARROQUIAS = __PARROQUIAS__;
const PUNTOS = __PUNTOS__;
const AREAS = __AREAS__;

const mapa = L.map("mapa");
L.tileLayer("https://tms-pnoa-ma.idee.es/1.0.0/pnoa-ma/{z}/{x}/{-y}.jpeg", {
  maxZoom: 19, attribution: "PNOA © IGN"
}).addTo(mapa);

function color(v) {
  return v == null ? "#999" :
         v > 40 ? "#7f1d1d" : v > 25 ? "#c2410c" : v > 15 ? "#ea8c33" :
         v > 8  ? "#eab308" : "#65a30d";
}
const capaParr = L.geoJSON(PARROQUIAS, {
  style: f => ({ color: "#fff", weight: 1, fillOpacity: 0.55,
                 fillColor: color(f.properties.ha_prohibida_punto_medio) }),
  onEachFeature: (f, l) => {
    const p = f.properties;
    l.bindPopup(`<div class="popup-tit">${p.PARROQUIA}</div>
      <div style="color:#666;font-size:12px;margin-bottom:6px">${p.NOMECONCEL}
        ${p.puesto ? "· puesto " + p.puesto + " de 40" : ""}</div>
      <div class="popup-fila"><span>franja medida</span><span>${(p.ha_medida ?? 0).toFixed(0)} ha</span></div>
      <div class="popup-fila"><span>con arbolado</span><span>${(p.ha_arbolado ?? 0).toFixed(0)} ha</span></div>
      <div class="popup-fila"><span>prohibido (cotas)</span><span>${(p.ha_prohibida_min ?? 0).toFixed(0)}–${(p.ha_prohibida_max ?? 0).toFixed(0)} ha</span></div>
      <div class="popup-fila"><span>eucaliptal &gt;35 m</span><span>${(p.ha_sobre_35m ?? 0).toFixed(1)} ha</span></div>`);
  }
}).addTo(mapa);
mapa.fitBounds(capaParr.getBounds());

const estiloPto = {
  eucaliptal_35m: { c: "#e11d48", r: 8 },
  rodal_ifn:      { c: "#f97316", r: 7 },
  disperso_copas: { c: "#8b5cf6", r: 5 }
};
const nombreTipo = {
  eucaliptal_35m: "Eucaliptal seguro (dosel &gt;35 m)",
  rodal_ifn: "Rodal IFN de especie prohibida",
  disperso_copas: "Arbolado disperso clasificado"
};
// las manchas: lo que justifica cada punto, no solo la chincheta
const capaAreas = L.geoJSON(AREAS, {
  style: f => ({ color: estiloPto[f.properties.tipo].c, weight: 1.6,
                 fillOpacity: 0.22, fillColor: estiloPto[f.properties.tipo].c }),
  onEachFeature: (f, l) => l.bindPopup(
    `<div class="popup-tit">${f.properties.ha} ha</div>
     <div style="font-size:12px;color:#666">${f.properties.PARROQUIA}
     (${f.properties.NOMECONCEL})</div>`)
}).addTo(mapa);

const capas = {};
for (const t of Object.keys(estiloPto)) {
  capas[t] = L.geoJSON(PUNTOS, {
    filter: f => f.properties.tipo === t,
    pointToLayer: (f, ll) => L.circleMarker(ll, {
      radius: estiloPto[t].r, color: estiloPto[t].c, weight: 2.5,
      fillOpacity: 0.15, fillColor: estiloPto[t].c
    }),
    onEachFeature: (f, l) => {
      const p = f.properties;
      l.bindPopup(`<div class="popup-tit">${nombreTipo[t]}</div>
        <div style="color:#666;font-size:12px;margin-bottom:6px">${p.PARROQUIA} (${p.NOMECONCEL})</div>
        <div class="popup-fila"><span>estimacion</span><span>${p.ha} ha</span></div>
        <div class="popup-fila"><span>certeza</span><span>${p.certeza}</span></div>
        <div style="font-size:12px;margin-top:6px">${p.nota}</div>
        <div style="font-size:11px;color:#888;margin-top:4px">ETRS89 UTM29:
          ${Math.round(p.x)}, ${Math.round(p.y)}</div>`);
    }
  }).addTo(mapa);
}
L.control.layers(null, {
  "Parroquias (ranking)": capaParr,
  "Manchas de arbolado": capaAreas,
  "Eucaliptal seguro &gt;35 m": capas.eucaliptal_35m,
  "Rodales IFN prohibidos": capas.rodal_ifn,
  "Disperso clasificado": capas.disperso_copas
}, { collapsed: false }).addTo(mapa);

const leyenda = L.control({ position: "bottomright" });
leyenda.onAdd = () => {
  const d = L.DomUtil.create("div", "leyenda");
  d.innerHTML = `<b>ha prohibidas (punto medio)</b><br>
    <i style="background:#7f1d1d"></i>&gt; 40<br>
    <i style="background:#c2410c"></i>25–40<br>
    <i style="background:#ea8c33"></i>15–25<br>
    <i style="background:#eab308"></i>8–15<br>
    <i style="background:#65a30d"></i>&lt; 8<br>
    <div style="margin-top:6px"><b>puntos de inspeccion</b></div>
    <i class="pto" style="border-color:#e11d48"></i>eucaliptal &gt;35 m (certeza alta)<br>
    <i class="pto" style="border-color:#f97316"></i>rodal IFN prohibido<br>
    <i class="pto" style="border-color:#8b5cf6"></i>disperso clasificado`;
  return d;
};
leyenda.addTo(mapa);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    SALIDA.mkdir(parents=True, exist_ok=True)
    html = (PLANTILLA
            .replace("__PARROQUIAS__", json.dumps(parroquias_geojson(),
                                                  separators=(",", ":")))
            .replace("__PUNTOS__", json.dumps(puntos_geojson(),
                                              separators=(",", ":")))
            .replace("__AREAS__", json.dumps(areas_geojson(),
                                             separators=(",", ":"))))
    ruta = SALIDA / "index.html"
    ruta.write_text(html, encoding="utf-8")
    print(f"-> {ruta.relative_to(RAIZ)}  ({ruta.stat().st_size/1e6:.1f} MB)")
