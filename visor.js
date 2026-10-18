"use strict";

(() => {
  const $ = id => document.getElementById(id);
  const fmt = (v, digits = 0) => Number(v).toLocaleString("es-ES", {
    minimumFractionDigits: digits, maximumFractionDigits: digits
  });
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[c]);
  const normaliza = s => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const color = v => v == null ? "#84929a" : v > 40 ? "#75283d" :
    v > 25 ? "#b24f32" : v > 15 ? "#ca8b37" : v > 8 ? "#b4ae4c" : "#6c997a";
  const tipos = {
    eucaliptal_35m: { color: "#c13754", nombre: "Dosel de más de 35 m" },
    rodal_ifn: { color: "#db7620", nombre: "Especie según inventario forestal" },
    disperso_copas: { color: "#4160bf", nombre: "Arbolado disperso clasificado" }
  };
  let manifest, mapa, parroquias, lista = [], eleccion = "", destacado = "";
  let puntos, areas, revision = 0, temporizador;
  const cache = new Map();
  const capasParroquia = new Map();
  const clave = p => `${p.NOMECONCEL}\u0000${p.PARROQUIA}`;
  const cotas = p => `${fmt(p.ha_prohibida_min)}–${fmt(p.ha_prohibida_max)}`;

  async function json(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`No se pudo cargar ${url} (${res.status})`);
    return res.json();
  }
  function estado(texto, error = false) {
    $("estado").textContent = texto;
    $("estado").classList.toggle("error", error);
  }
  function fichaParroquia(p) {
    const datos = p.puesto != null;
    return `<div class="ficha"><h3>${esc(p.PARROQUIA)}</h3><p>${esc(p.NOMECONCEL)}${datos ? ` · puesto ${p.puesto} de ${manifest.n_parroquias}` : ""}</p>
      ${datos ? `<dl><div><dt>Estimación (cotas)</dt><dd>${cotas(p)} ha</dd></div>
      <div><dt>Franja medida</dt><dd>${fmt(p.ha_medida, 1)} ha</dd></div>
      <div><dt>Arbolado detectado</dt><dd>${fmt(p.ha_arbolado, 1)} ha</dd></div>
      <div><dt>Dosel &gt;35 m</dt><dd>${fmt(p.ha_sobre_35m, 1)} ha</dd></div></dl>` : "<p>Franja oficial sin resultado medido. No equivale a riesgo cero.</p>"}
      <p class="nota">Estimación para priorizar inspección. No acredita infracción ni identifica propietarios.</p></div>`;
  }
  function fichaPunto(f) {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    let nota;
    if (p.tipo === "eucaliptal_35m") {
      nota = "El modelo atribuye este dosel a eucalipto por su altura. La especie requiere comprobación.";
    } else if (p.tipo === "rodal_ifn") {
      const especie = String(p.nota).split(" (IFN")[0].replaceAll("_", " ");
      const fraccion = String(p.nota).match(/f_prohibida (\d+%)/)?.[1];
      nota = `Especie principal según el inventario de 2010: ${especie}. Sin evento detectado en 2017–2026.${fraccion ? ` Proporción de especies incluidas en la norma según el inventario: ${fraccion}.` : ""}`;
    } else {
      const numero = String(p.nota).match(/^(\d+) copas/)?.[1];
      nota = `${numero ? `Grupo de ${numero} copas` : "Copas"} clasificadas como especies incluidas en la norma, en una zona con validación espacial.`;
    }
    return `<div class="ficha"><h3>${esc(tipos[p.tipo]?.nombre ?? p.tipo)}</h3>
      <p>${esc(p.PARROQUIA)} (${esc(p.NOMECONCEL)})</p>
      <dl><div><dt>Estimación del grupo</dt><dd>${fmt(p.ha, 2)} ha</dd></div></dl>
      <p>${esc(nota)}</p><p>Coordenadas: ${fmt(lat, 5)}, ${fmt(lon, 5)}</p>
      <a href="https://www.google.com/maps/search/?api=1&query=${lat},${lon}" target="_blank" rel="noopener">Abrir ubicación en mapas</a>
      <p class="nota">Punto sobre arbolado medido en 2024. Requiere comprobación de especie y estado actual. Las superficies pueden solaparse.</p></div>`;
  }
  function resumen() {
    const c = manifest.concellos.find(c => c.concello === eleccion);
    const p = c ?? manifest.totales;
    $("resumen").innerHTML = `<h2>${esc(c?.concello ?? "Toda Pontevedra")}</h2>
      <p class="cotas">${cotas(p)} <span class="unidad">ha estimadas</span></p>
      <p>de arbolado de especies incluidas en la norma.<br><strong>No acredita infracción.</strong></p>
      <p class="medida">${fmt(p.ha_medida)} ha de franja medida · ${c?.parroquias ?? manifest.n_parroquias} parroquias${c ? "" : ` · ${manifest.n_concellos} concellos`}</p>`;
  }
  function renderLista() {
    const busqueda = normaliza($("buscar").value.trim());
    const visibles = lista.filter(p => (!eleccion || p.NOMECONCEL === eleccion) &&
      (!busqueda || normaliza(`${p.PARROQUIA} ${p.NOMECONCEL}`).includes(busqueda)));
    $("cuenta").textContent = `${visibles.length} ${visibles.length === 1 ? "resultado" : "resultados"}`;
    const fragmento = document.createDocumentFragment();
    for (const p of visibles) {
      const li = document.createElement("li"), boton = document.createElement("button");
      boton.type = "button";
      boton.setAttribute("aria-pressed", String(destacado === clave(p)));
      boton.innerHTML = `<span class="rango">${p.puesto}</span><span class="nombre">${esc(p.PARROQUIA)}<small>${esc(p.NOMECONCEL)}</small></span><span class="hectareas">${cotas(p)} ha</span>`;
      boton.addEventListener("click", () => {
        destacado = clave(p);
        const capa = capasParroquia.get(destacado);
        mapa.fitBounds(capa.getBounds(), { padding: [24, 24], maxZoom: 16 });
        capa.openPopup();
        renderLista();
      });
      li.append(boton); fragmento.append(li);
    }
    if (!visibles.length) {
      const li = document.createElement("li");
      li.className = "vacio"; li.textContent = "No hay parroquias con ese nombre en esta selección.";
      fragmento.append(li);
    }
    $("ranking").replaceChildren(fragmento);
  }
  function bounds(bbox) { return L.latLngBounds([bbox[1], bbox[0]], [bbox[3], bbox[2]]); }
  function elige(nombre, acercar = true) {
    eleccion = nombre; $("concello").value = nombre; destacado = "";
    mapa.closePopup();
    resumen(); renderLista();
    parroquias.eachLayer(capa => {
      const p = capa.feature.properties, activo = !eleccion || p.NOMECONCEL === eleccion;
      capa.setStyle({ fillOpacity: activo ? .6 : .12, weight: activo ? .7 : .3 });
    });
    if (acercar) {
      const c = manifest.concellos.find(c => c.concello === nombre);
      mapa.fitBounds(c ? bounds(c.bbox) : parroquias.getBounds(), { padding: [20, 20], maxZoom: 14 });
    }
    const url = new URL(location.href);
    if (nombre) url.searchParams.set("concello", nombre); else url.searchParams.delete("concello");
    history.replaceState(null, "", url);
    actualizaDetalle();
  }
  function cargaConcello(c) {
    if (!cache.has(c.archivo)) {
      cache.set(c.archivo, json(c.archivo).catch(error => { cache.delete(c.archivo); throw error; }));
    }
    return cache.get(c.archivo);
  }
  async function actualizaDetalle() {
    const turno = ++revision;
    if (!mapa || !manifest) return;
    if (mapa.getZoom() < 13) {
      puntos.clearLayers(); areas.clearLayers();
      estado("Acércate para ver puntos y manchas de arbolado."); return;
    }
    if (!mapa.hasLayer(puntos) && !mapa.hasLayer(areas)) {
      estado("Activa puntos o manchas en el selector de capas."); return;
    }
    const vista = mapa.getBounds().pad(.12);
    const municipios = manifest.concellos.filter(c => (!eleccion || c.concello === eleccion) && vista.intersects(bounds(c.bbox)));
    estado("Cargando detalle de la zona…");
    const resultados = await Promise.allSettled(municipios.map(cargaConcello));
    if (turno !== revision) return;
    puntos.clearLayers(); areas.clearLayers();
    let n = 0;
    for (const resultado of resultados) {
      if (resultado.status !== "fulfilled") continue;
      const d = resultado.value;
      for (const f of d.puntos.features) {
        const [x, y] = f.geometry.coordinates;
        if (vista.contains([y, x])) { puntos.addData(f); n++; }
      }
      // Canvas evita miles de nodos SVG en el movil. Leaflet recorta al viewport.
      if (mapa.hasLayer(areas)) areas.addData(d.areas);
    }
    puntos.bringToFront();
    if (resultados.some(r => r.status === "rejected")) {
      estado("No se cargó parte del detalle. ");
      $("estado").classList.add("error");
      const reintento = document.createElement("button");
      reintento.type = "button"; reintento.textContent = "Reintentar";
      reintento.addEventListener("click", actualizaDetalle); $("estado").append(reintento);
    } else estado(`${n} puntos en esta vista. Pulsa un punto o una franja para consultar su ficha.`);
  }
  function inicializaMapa(datos) {
    mapa = L.map("mapa", { preferCanvas: true, zoomControl: false, minZoom: 7, maxZoom: 19 });
    L.control.zoom({ position: "topright" }).addTo(mapa);
    L.control.scale({ imperial: false, position: "bottomright", maxWidth: 120 }).addTo(mapa);
    const callejero = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(mapa);
    const orto = L.tileLayer("https://tms-pnoa-ma.idee.es/1.0.0/pnoa-ma/{z}/{x}/{-y}.jpeg", {
      maxZoom: 19, attribution: 'Ortofoto PNOA &copy; <a href="https://www.ign.es/">IGN</a>'
    });
    parroquias = L.geoJSON(datos, {
      style: f => ({ color: color(f.properties.ha_prohibida_punto_medio),
                     weight: .7, opacity: .95, fillOpacity: .6,
                     fillColor: color(f.properties.ha_prohibida_punto_medio) }),
      onEachFeature: (f, capa) => {
        capasParroquia.set(clave(f.properties), capa);
        capa.bindPopup(() => fichaParroquia(f.properties), { maxWidth: 300 });
      }
    }).addTo(mapa);
    puntos = L.geoJSON(null, {
      pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 6, weight: 2,
        color: tipos[f.properties.tipo]?.color ?? "#444", fillColor: "#fff", fillOpacity: .8 }),
      onEachFeature: (f, capa) => capa.bindPopup(() => fichaPunto(f), { maxWidth: 300 })
    }).addTo(mapa);
    areas = L.geoJSON(null, {
      style: f => ({ color: tipos[f.properties.tipo]?.color ?? "#444", weight: 1.2, fillOpacity: .22 }),
      onEachFeature: (f, capa) => capa.bindPopup(() => `<div class="ficha"><h3>Mancha de arbolado</h3><p>${esc(f.properties.PARROQUIA)} (${esc(f.properties.NOMECONCEL)})</p><p>${esc(tipos[f.properties.tipo]?.nombre)} · ${fmt(f.properties.ha, 2)} ha del grupo</p><p class="nota">Contorno simplificado para visualización. No es una delimitación catastral ni acredita infracción.</p></div>`)
    }).addTo(mapa);
    L.control.layers({ "Mapa": callejero, "Ortofoto PNOA (IGN)": orto }, {
      "Franjas por parroquia": parroquias, "Puntos de inspección": puntos, "Manchas de arbolado": areas
    }, { collapsed: true, position: "topright" }).addTo(mapa);
    mapa.on("moveend", () => { clearTimeout(temporizador); temporizador = setTimeout(actualizaDetalle, 160); });
    mapa.on("overlayadd overlayremove", e => { if (e.layer !== parroquias) actualizaDetalle(); });
    let fallosTiles = 0;
    for (const capa of [callejero, orto]) capa.on("tileerror", () => {
      if (++fallosTiles === 3) estado("El fondo no responde. Prueba el otro mapa en el selector de capas.", true);
    });
    mapa.fitBounds(parroquias.getBounds(), { padding: [18, 18] });
    new ResizeObserver(() => mapa.invalidateSize()).observe($("mapa"));
  }
  async function inicio() {
    try {
      if (!window.L) throw new Error("No se ha podido cargar la biblioteca del mapa. Comprueba la conexión y recarga.");
      const [config, datos] = await Promise.all([json("manifest.json"), json("datos/parroquias.geojson")]);
      manifest = config;
      lista = datos.features.map(f => f.properties).filter(p => p.puesto != null).sort((a, b) => a.puesto - b.puesto);
      if (lista.length !== manifest.n_parroquias) throw new Error("Los datos del mapa no coinciden con el ranking publicado.");
      for (const c of [...manifest.concellos].sort((a, b) => a.concello.localeCompare(b.concello, "es"))) {
        const opcion = document.createElement("option"); opcion.value = c.concello; opcion.textContent = c.concello;
        $("concello").append(opcion);
      }
      $("concello").disabled = false; $("buscar").disabled = false;
      $("validacion").textContent = `Validación provincial: aproximadamente un ${fmt(manifest.tasa_fp * 100)} % de falsos positivos del producto (IC95: ${fmt(manifest.tasa_fp_lo * 100)}–${fmt(manifest.tasa_fp_hi * 100)} %), con 150 puntos. No es una garantía para cada punto del mapa.`;
      inicializaMapa(datos);
      const inicial = new URL(location.href).searchParams.get("concello") ?? "";
      elige(manifest.concellos.some(c => c.concello === inicial) ? inicial : "");
      $("concello").addEventListener("change", e => { $("buscar").value = ""; elige(e.target.value); });
      $("buscar").addEventListener("input", renderLista);
      $("provincia").addEventListener("click", () => { $("buscar").value = ""; elige(""); });
      window.addEventListener("popstate", () => {
        const valor = new URL(location.href).searchParams.get("concello") ?? "";
        elige(manifest.concellos.some(c => c.concello === valor) ? valor : "");
      });
    } catch (error) {
      console.error(error);
      $("resumen").innerHTML = `<p>No se han podido cargar los resultados. Recarga la página o <a href="ranking_final_pontevedra.csv">descarga el ranking por parroquia</a>.</p>`;
      estado(error.message, true);
    }
  }
  inicio();
})();
