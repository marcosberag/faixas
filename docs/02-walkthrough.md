# Walkthrough: estado real del código

Qué hay escrito, qué funciona, qué está roto y cómo reproducirlo.
Última verificación: **14 de septiembre de 2026**. Las secciones 1 a 13 cuentan el
piloto hasta la fase 3 con todo detalle; la 14 recoge lo que el código de las fases 4
a 7 obliga a saber, y la 15 la pasada de limpieza del 14-09.

---

## Estado en una tabla

| Paso | Estado | Dónde |
|---|---|---|
| Descargar atributos de las franjas | ✅ funciona | `scripts/descarga_faixas.py` |
| Descargar **geometrías** de las franjas | ✅ **resuelto** | `scripts/carga_faixas.py` |
| Reparar geometrías inválidas | ✅ funciona | `scripts/repara_faixas.py` |
| Verificar contra el servicio oficial | ✅ IoU 0,9996 | `scripts/verifica_faixas.py` |
| Renderizar franjas sobre ortofoto | ✅ funciona | `scripts/mapa_faixas.py`, `mapa_zoom_post.py` |
| Malla de bloques LiDAR y elección | ✅ funciona | `scripts/malla_lidar.py` |
| Descargar LiDAR del CNIG | ✅ **resuelto** | `scripts/descarga_lidar.py` |
| SMRF / MDT / MDS / CHM | ✅ funciona | `scripts/pipeline_chm.py` |
| Comprobar que el CHM no está roto | ✅ funciona | `scripts/verifica_chm.py` |
| Recorte y métricas por franja | ✅ funciona | `scripts/metricas_faixas.py` |
| Muestra de validación estratificada | ✅ funciona | `scripts/muestra_validacion.py` |
| Ortofoto y recortes para anotar | ✅ funciona | `scripts/chips_validacion.py` |
| Anotador de fotointerpretación | ✅ funciona, **probado** | `scripts/anotador.py`, `test_anotador.js` |
| Anotar los 400 puntos | ✅ hecho, 24 min | `validacion/anotacion.csv` |
| Calibrar el umbral y tasa de FP | ✅ **5,5 m, FP 24,2 %** | `scripts/calibra_umbral.py` |
| Revisar discrepancias | ✅ hecho | `scripts/revisa_discrepancias.py` |
| Fiabilidad intra-anotador | ✅ kappa 0,53–0,88 | `scripts/retest_validacion.py` |
| Fase 4: la comarca entera | ✅ **263 bloques, 0 fallos** | `scripts/procesa_comarca.py` |
| Validar el clasificador S2 | ❌ **no valida** (AUC 0,746, ver §13) | `scripts/fenologia_especie.py` |
| Validar el producto fuera de muestra | ✅ FP 33,5 % [25–42], sens. 89,8 % | `scripts/valida_producto.py` |
| Ranking final con cotas | ✅ **353–574 ha prohibidas** (reemplazos confirmados + clasificador de copas) | `scripts/ranking_final.py` |
| Serie anual S2 + detector de eventos | ✅ montado, **97,4 % persistente** | `scripts/serie_s2_anual.py`, `detecta_eventos.py` |
| Validar el detector contra PNOA histórico | ✅ persistencia confirmada (FN 3,8 %); eventos **39 % de precisión** — sequía 2026 domina, la vigilancia no se publica | `scripts/hojas_persistencia.py`, `valida_persistencia.py` |
| Fase 6: especie por copa (segmentación + textura a 25 cm) | ✅ **AUC eucalipto 0,86 OOS**, integrada solo en zonas validadas (45 % del disperso): titular **[353–574] ha** (−24 % de anchura) | `scripts/copas_chm.py`, `entrena_copas.py`, `aplica_copas.py` |
| Filtro de edificios del Catastro | ✅ 13.452 huellas; **589 «copas» eran tejados** | `scripts/descarga_catastro.py` |
| Fase 7A: escalar a Pontevedra | ✅ **3.197/3.197 bloques, 0 corruptos** (~5 días de máquina); cadena completa corrida | `scripts/prepara_provincia.py`, `procesa_comarca.py --malla` |
| Validación provincial fuera de muestra | ✅ **FP 20,1 % [12,8–28,0]**, sens. 90,1 %, ≥35 m 9/9 árbol (150 puntos, 16 delegados al prefiltro de Claude) | `scripts/valida_producto.py --dir validacion_pontevedra`, `anotador_prefiltrado.py` |
| Ranking provincial al 30-08 (sin fase 6, cota del disperso del piloto) | ✅ [4.493–8.288] ha prohibidas en 38.601 ha de franja; Ponteareas 1º | `scripts/ranking_final.py --zona pontevedra` |
| Fase 5 en la provincia: persistencia por tiles | ✅ **98,2 % persistente**; 4 tiles MGRS compuestos por separado; 2018 = incendios de 2017, 2026 = sequía | `scripts/serie_s2_anual.py --zona pontevedra`, `detecta_eventos.py --zona pontevedra` |
| Fase 6 en la provincia: clasificador de copas | ✅ **AUC eucalipto 0,866 OOS**, 407 zonas de entrenamiento; aplicado en 45 zonas validadas (24 % del disperso), fracción prohibida 47,8 % obs. (36 % corregida) | `copas_chm.py`, `muestra_copas.py --zona`, `parches_copas.py --zona`, `entrena_copas.py --zona --cnn`, `aplica_copas.py --zona` |
| **Ranking provincial FINAL** | ✅ **[4.770–8.141] ha prohibidas** (−16 % de anchura frente a [4.493–8.515] sin fase 6); podio estable, Lalín de 4º a 6º. Cota alta del disperso con la muestra provincial (§15). Sin filtro de Catastro (WFS limita por IP; efecto medido: 1 ha) | `scripts/ranking_final.py --zona pontevedra` |
| Fase 7B: producto usable | ✅ 464 puntos de inspección, visor web y dossier PDF por concello (piloto; pendiente `--zona`) | `scripts/puntos_inspeccion.py`, `visor.py`, `dossier_concello.py` |

---

## Requisitos

```bash
pip install requests pillow numpy scipy matplotlib geopandas pyogrio rasterio laspy[lazrs]
```

Y **PDAL aparte**, que en Windows tiene su propia historia: ver la sección 5.

---

## 1. Descarga de las franjas

```bash
python scripts/descarga_faixas.py
```

Consulta el servicio ArcGIS REST de la Xunta, pagina con `resultOffset`, guarda un JSON
por capa en `datos/crudo/` y avisa por consola de cuántas geometrías vienen vacías.

**Servicio:**
```
https://ideg.xunta.gal/servizos/rest/services/PBA/Afeccions_Agropecuaria_Faixas/MapServer
```
- Capa 0 — "Faixa de protección 50m" (núcleos de población)
- Capa 1 — "Faixa de protección 50m (Illadas)" (edificaciones aisladas)
- CRS EPSG:25829, `MaxRecordCount` 1000, `hasZ` y `hasM` a `true`

### Recuento verificado de la zona piloto

| Concello | Capa 0 | Capa 1 |
|---|---|---|
| Arbo | 8 | 8 |
| Cañiza, A | 12 | 13 |
| Covelo | 18 | 18 |
| Crecente | 11 | 13 |
| **Total** | **49** | **52** |

40 parroquias distintas. Extensión: `548731, 4661398, 567278, 4685317` (EPSG:25829),
es decir 18,5 × 23,9 km.

> **Corrige a `CLAUDE.md`**, que daba 37 y 39. Esos números salían de una consulta a la
> que le faltaba A Cañiza, por el motivo del apartado siguiente.

### Trampa nº 1: el nombre de los concellos lleva artículo pospuesto

El campo `CONCELLO` guarda **`'Cañiza, A'`**, no `'A Cañiza'`. Igual con `'Neves, As'`,
`'Arnoia, A'`, `'Pastoriza, A'`… Un `WHERE ... IN (...)` con la forma natural del nombre
no falla: **devuelve menos registros en silencio**, que es peor.

Para comprobar los valores reales:
```
/0/query?where=CONCELLO+LIKE+'%iza%'&outFields=CONCELLO&returnDistinctValues=true&f=json
```

---

## 2. El bloqueo: el servicio no exporta geometrías

**Este es el problema que impide continuar con el pipeline.**

`CLAUDE.md` avisaba de que `f=geojson` devolvía `geometry: null` por culpa de `hasZ`/
`hasM`, y proponía usar `f=json` o forzar `returnZ=false&returnM=false`. **Ese
diagnóstico es incorrecto.** El servicio no devuelve geometría por ninguna vía.

Comprobado, todo con el mismo resultado:

| Intento | Resultado |
|---|---|
| `f=json` + `returnGeometry=true` | sin geometría |
| `f=json` + `returnZ=false&returnM=false` | sin geometría |
| `f=geojson` | sin geometría |
| POST en vez de GET | sin geometría |
| `objectIds=186` (un solo registro) | sin geometría |
| con `outSR=25829` | sin geometría |
| con `geometryPrecision=2` | sin geometría |

La respuesta cruda no trae la clave `geometry` **en absoluto**, y `geometryType` viene a
`null`:

```json
{"displayFieldName":"PARROQUIA","fieldAliases":{"OBJECTID":"OBJECTID"},
 "fields":[...],"features":[{"attributes":{"OBJECTID":186}}]}
```

No es un fallo de serialización: el servidor ignora `returnGeometry` por completo.

**Y sin embargo las geometrías están ahí.** Dos pruebas:

1. El filtro espacial funciona. Una consulta con `geometryType=esriGeometryEnvelope`
   devuelve recuentos correctos y distintos según el recuadro.
2. `/export` las dibuja. Las imágenes de `salidas/` están renderizadas por el propio
   servidor de la Xunta.

Conclusión: la capa tiene la exportación de geometría capada a propósito, pero la
consulta espacial y el renderizado siguen abiertos.

El bloqueo es **específico de estas capas**, no del servidor: otras capas del mismo
ArcGIS (`PBA/Malla`, `PBA/EntidadesPoboacion_PBA`, `PBA/ConcellosDescargas`) devuelven
geometría con normalidad. Es una decisión deliberada, coherente con que la capa
identifica parcelas de particulares.

Vías descartadas por el camino:

- **No hay WFS.** El servicio declara `supportedExtensions: "WMSServer"` y nada más.
- **No hay FeatureServer** equivalente (error 500).
- **`dynamicLayers` está deshabilitado** en el MapService.
- **`GetFeatureInfo` del WMS tampoco sirve geometría** en ninguno de sus siete
  `INFO_FORMAT`, ni siquiera en `application/geo+json`, que devuelve `"geometry": null`.
  Ojo: el WMS cuelga de `/servizos/services/...`, no de `/servizos/rest/services/...`.

## 2 bis. La solución: descarga directa del PBA

**Resuelto.** Las geometrías se descargan como shapefile desde el visor del Plan Básico
Autonómico:

```
https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa/FaixaProteccion50m.zip
https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa/FaixaProteccion50m_Illadas.zip
```

104,6 MB y 39,75 MB. Shapefile completo con `.prj`, **EPSG:25829**, sin reproyección.
4.006 registros de núcleos y 2.178 de illadas para toda Galicia.

Se encontraron inspeccionando el visor `mapas.xunta.gal/visores/pba/`: cada capa lleva un
icono "descargar cartografía da capa" con la URL en el `onclick`. De las 111 capas del
PBA, la de faixas es la única que usa `descargaZipsArray` (dos ficheros) en vez de
`descargaZips` (uno) — un filtro que solo busque `descargaZips(...)` la da por vacía.

### Trampa nº 3: TLS incompleto en `visorgis.cmati.xunta.es`

Ese servidor sirve una cadena de certificados sin el intermedio, y `requests` falla con
`CERTIFICATE_VERIFY_FAILED`. **No desactivar la verificación.** El almacén de
certificados de Windows sí resuelve la cadena:

```powershell
Invoke-WebRequest -Uri $url -OutFile $destino -UseBasicParsing
```

### Trampa nº 4: los campos NO son los de la API

| API REST | Shapefile |
|---|---|
| `CONCELLO` = `'Cañiza, A'` | `NOMECONCEL` = `'A Cañiza'` |
| `PARROQUIA` | `PARROQUIA`, y además `CODPARRO` (código, mejor para agregar) |
| — | `CONCELLOOR`, `PROVINCIA` |

El artículo va pospuesto en la API y **antepuesto en el shapefile**. Es exactamente la
trampa contraria. Cualquier código que cruce ambas fuentes tiene que normalizar.

### Trampa nº 5: geometrías inválidas

El shapefile trae auto-intersecciones de anillo: **4 de 49** en núcleos y **15 de 52** en
illadas. Sin reparar, un recorte de ráster contra ellas falla en silencio. `make_valid`
las arregla y **la superficie no cambia** (+0,000 %), así que son defectos topológicos
sin efecto sobre el área. Lo hace `scripts/repara_faixas.py`.

### Verificación

| Comprobación | Resultado |
|---|---|
| Registros zona piloto vs API | 49 y 52 — **cuadra exactamente** |
| CRS del `.prj` | ETRS89 UTM 29N = EPSG:25829 |
| Geometrías válidas tras reparar | 101/101 |
| **IoU contra el `/export` oficial** | **0,9996** (0 px solo en servicio, 64 px solo en shapefile) |

El IoU se calcula rasterizando el shapefile en la misma rejilla que la imagen del
servicio. Es la prueba de que el fichero descargado es el mismo dato que la Xunta pinta.

### Trampa nº 2: qué parámetros respeta `/export`

Comprobado sobre este servicio concreto:

| Parámetro | ¿Lo respeta? |
|---|---|
| `layerDefs` | ✅ sí — filtra bien por `CONCELLO` |
| `dynamicLayers` | ❌ `"'dynamicLayers' is not enabled on this MapService"` |
| `layerDrawingOptions` | ❌ ignorado en silencio, pinta con su simbología |

Como no se puede cambiar la simbología desde el servicio, `mapa_zoom_post.py` pide el PNG
transparente, se queda con **el canal alfa como máscara** y recolorea en local. Es la
forma limpia de controlar el estilo aquí.

Cuidado al validar `layerDefs`: si el recuadro solo contiene registros que ya pasan el
filtro, con y sin filtro salen imágenes idénticas y parece que no funciona. Hay que
probarlo en una extensión amplia.

---

## 3. Generación de las imágenes

```bash
python scripts/mapa_faixas.py       # comarca + zoom, con barra de rótulo
python scripts/mapa_zoom_post.py    # zoom limpio y zoom con atribución
```

Compone dos fuentes sobre el mismo `bbox` y el mismo CRS, sin reproyectar:

- **Fondo:** WMS PNOA del IGN, capa `OI.OrthoimageCoverage`, `EPSG:25829`.
- **Encima:** `/export` del MapServer de la Xunta, `png32` transparente.

### Procedencia de la ortofoto

Consultable vía `GetFeatureInfo` sobre la capa **`OI.MosaicElement`** (la de imagen
`OI.OrthoimageCoverage` no es consultable y da `LayerNotDefined`).

Sobre la zona piloto: **vuelo de septiembre de 2023, resolución 0,15 m.**

Dato relevante: la ortofoto y el LiDAR serán de fechas distintas. Cualquier discrepancia
entre lo que se ve en la foto y lo que mide el CHM puede ser corta o plantación
intermedia, no error del método. Hay que registrar ambas fechas en la validación.

### Licencia

PNOA se distribuye bajo CC-BY: **la atribución es obligatoria**, no decorativa. Toda
imagen publicada debe llevar el crédito al IGN y a la Xunta. `post_zoom_atribucion.jpg`
lo lleva; `post_zoom_limpia.jpg` no, y por eso no debería publicarse tal cual.

---

## 4. Cómo comprobar la alineación

No hay reproyección en ningún punto: ambas peticiones se hacen en `EPSG:25829` con el
mismo `bbox`. La verificación empírica es que **los polígonos envuelven exactamente los
núcleos de casas visibles** en la ortofoto; con un desfase de CRS o de orden de ejes eso
no encajaría.

Comprobación pendiente: **nadie ha medido que la banda mida 50 m**. Se intentó aislando
componentes conexos circulares de la capa 1 (edificaciones aisladas, que deberían dar
círculos de radio ≈ 50 m + huella del edificio), pero en la zona de prueba los polígonos
están fusionados y no hay ninguno aislado. Repetir en una zona de baja densidad cuando
haya geometrías de verdad.

### Qué es exactamente el polígono

Medido ya sobre las geometrías reales:

| | Núcleos | Illadas |
|---|---|---|
| Registros | 49 | 52 |
| Polígonos sueltos (tras `explode`) | 2.475 | 1.320 |
| Área por polígono (mediana) | 6.400 m² | 2.991 m² |
| Ancho medio `2A/P` (mediana) | 30,9 m | 22,4 m |
| **Radio inscrito máximo** | **47 m** | 37 m |

Que el radio inscrito **nunca supere los 50 m** es la confirmación indirecta del ancho de
banda: es el buffer de 50 m de cada edificación, no un polígono que englobe superficie
arbitraria. Si incluyera el interior de núcleos grandes, habría radios de cientos de
metros.

Corrige una lectura anterior de este documento. Al rellenar huecos sobre la máscara
rasterizada quedaban solo 531 px de 260.883, y se concluyó que el polígono "incluye el
núcleo". Lo correcto es más preciso: **en aldeas compactas los buffers de 50 m de casas
vecinas se solapan y cubren el interior de facto**, sin que el polígono sea otra cosa que
la unión de buffers.

El efecto práctico sobre las métricas es el mismo: al recortar el CHM entran casas,
jardines y arbolado ornamental. Habrá que decidir si se descuenta el casco urbano
—cruzando con Catastro o con la clase "edificio" del LiDAR— o si se asume y se documenta.

Un registro = una parroquia (multipolígono). Para agregar, `CODPARRO` es más fiable que
el nombre.

---

## 5. El LiDAR: descarga desde el CNIG

```bash
python scripts/malla_lidar.py       # qué bloques hacen falta
python scripts/descarga_lidar.py    # los baja y cronometra
```

### La malla: el nombre del fichero es la esquina NOROESTE

El PNOA sirve bloques de 1×1 km alineados a múltiplos de 1000 m en EPSG:25829:

```
PNOA-2024-GAL-559-4674-H29-NPC01.LAZ
              |   |    |   +-- nivel de clasificación
              |   |    +------ huso 29 = EPSG:25829
              |   +----------- Y de la esquina NW / 1000
              +--------------- X de la esquina NW / 1000
```

Cubre X `[559000, 560000]`, Y **`[4673000, 4674000]`**. Es decir, el bloque cae *debajo*
de la Y del nombre, no encima.

Comprobado contra el buscador: el punto `(558500, 4673500)` devuelve la hoja `558-4674` y
el punto `(558500, 4672500)` la `558-4673`. Suponer la esquina SW desplaza todo un
kilómetro al norte, y como los bloques vecinos también existen y también tienen datos, el
error **no da ningún fallo**: sale un CHM perfectamente válido de un sitio equivocado.

### Trampa nº 6: el CNIG no tiene URLs directas

No hay patrón de URL que se pueda construir. Hay que pasar por el buscador, que es un
formulario con estado de sesión. La secuencia, sacada del javascript de la página:

| Paso | Petición | Qué devuelve |
|---|---|---|
| 1 | `GET /CentroDescargas/lidar-tercera-cobertura` | abre sesión (`JSESSIONID`) |
| 2 | `POST /archivosSerie` | HTML con la hoja y su `sec` |
| 3 | `POST /initDescargaDir` `secuencial=<sec>` | `{"muestraLic":"NO", ...}` |
| 4 | `POST /descargaDir` `secDescDirLA=<sec>` | el LAZ |

En el paso 2, `codAgr=MOMDT` y `codSerie=LIDA3` identifican la serie, y `coordenadas` es
un **GeoJSON `FeatureCollection` con un punto en WGS84** — no en 25829, aunque los datos
lo estén. Devuelve la hoja que contiene ese punto.

El paso 3 existe para la licencia. Con esta serie devuelve `muestraLic: NO` y no hay nada
que aceptar; el script aborta si algún día cambia, en vez de intentar aceptarla solo.

Aviso: el CNIG puede devolver una página de error con código HTTP 200. El script
comprueba que los cuatro primeros bytes sean `LASF` antes de dar por buena la descarga.

### Trampa nº 7: la ficha dice 5 pts/m² y el fichero trae 17,5

| | puntos | pts/m² |
|---|---|---|
| Fichero completo | 17.515.247 | 17,5 |
| Sin clase 12 (solape) | 6.232.228 | 6,2 |
| Sin solape y un solo retorno por pulso | 4.946.775 | **4,9** |

Los 5 pts/m² de la ficha son los **primeros retornos de la pasada principal**. El resto es
solape entre pasadas del avión (64 % de los puntos) y retornos secundarios.

El solape va marcado como **clase 12 al estilo antiguo**: el flag `Overlap` que LAS 1.4
tiene para esto está a cero en estos ficheros. Hay que filtrar por clase.

### Trampa nº 8: PDAL no lee el CRS del fichero

`pdal info` avisa:

```
Global encoding WKT flag not set for point format 6 - 10.
```

y deja el SRS vacío. El fichero **sí** declara EPSG:25829, en un GeoKey VLR (registro
34735, clave 3072 = 25829), pero al ser formato de punto 8 el estándar LAS 1.4 exige el
CRS en WKT y PDAL no cae al GeoKey. Sin `override_srs` el ráster de salida sale sin
proyección y no cruza con nada.

### Otros datos del fichero, que importan más adelante

- **Formato de punto 8: trae banda infrarroja** además de RGB. Es exactamente lo que la
  fase 3 necesita para separar perennifolias de caducifolias sin pedir nada más.
- Vuelo de **2024** según el nombre; el fichero se generó en 2025. La ortofoto de la zona
  es de septiembre de 2023, así que hay **un año largo de desfase**: una discrepancia en
  la validación visual puede ser una corta intermedia y no un error del método.
- Nivel **NPC01**, clasificación automática sin revisar. Se descarta entera y se rehace.

---

## 6. PDAL en Windows

**No hay wheel de `pip install pdal`**: solo `sdist`, que exige compilar `libpdal` con
CMake. La vía practicable es un entorno conda con **micromamba**, que es un único `.exe`
de 11 MB y no toca el Python del sistema:

```powershell
Invoke-WebRequest "https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64.exe" -OutFile "$HOME\.local\bin\micromamba.exe"
& "$HOME\.local\bin\micromamba.exe" create -y -p "$HOME\.local\micromamba\envs\pdal" -c conda-forge pdal gdal
```

Cuatro minutos y medio. Instala PDAL 2.10.2.

El resto del pipeline sigue en el Python del sistema, que ya tiene geopandas y rasterio;
el entorno conda solo aporta el binario. `pipeline_chm.py` lo invoca por subproceso.

### Trampa nº 9: llamar a `pdal.exe` directo, no a `micromamba run`

`micromamba run` **se come el stderr del proceso hijo**. Un pipeline que falla devuelve un
código de salida numérico y nada más: aquí un error trivial de ruta relativa se manifestó
como `3221226505` (`0xC0000409`, un crash de Windows) sin una sola línea de diagnóstico.

Llamando a `envs\pdal\Library\bin\pdal.exe` con `PATH` apuntando a ese directorio, los
mensajes de PDAL salen normales. Además ahorra el arranque de micromamba en cada llamada.

Relacionado: **PDAL resuelve las rutas relativas contra su propio directorio de trabajo**,
no contra el del script que escribe el JSON. Rutas absolutas siempre.

### Trampa nº 10: hay que filtrar antes de que la nube entre en memoria

`filters.elm`, `filters.outlier` y `filters.smrf` **no son *streamables***: cargan la nube
completa en RAM y construyen un KD-tree encima. Con 17,5 M de puntos eso son varios GB y
PDAL revienta en un portátil de 16 GB con otras cosas abiertas.

La solución es poner un `filters.expression` — que **sí** es *streamable* — como primera
etapa, para que solo entren en memoria los puntos que se van a usar:

```json
{"type":"filters.expression",
 "expression":"Classification != 12 && ReturnNumber == NumberOfReturns"}
```

De 17,5 M a 4,9 M. Y de paso es lo correcto: el eco del suelo es siempre el **último**
retorno del pulso, y el de la copa el **primero**.

Descartar la clase 12 no es fiarse de NPC01: el solape lo marca la geometría del vuelo,
no el clasificador morfológico.

### Trampa nº 11: `writers.gdal` con `bounds` da un píxel de más

Pasando `bounds` y `resolution`, un bloque de 1 km sale de **1001×1001** píxeles y llega
hasta la coordenada 560001. Al mosaicar bloques vecinos esa fila sobrante los solapa y los
desalinea, y en las métricas por bloque se cuenta dos veces la frontera.

Se arregla dando `origin_x`, `origin_y`, `width` y `height` en vez de `bounds`.

---

## 7. Fase 1: los números medidos

Tres bloques, elegidos con `malla_lidar.py` por superficie de franja y en tres concellos
distintos: **559-4674** (A Cañiza), **562-4668** (Crecente), **549-4679** (Covelo).

Portátil de referencia: **i5-8350U, 4 núcleos / 8 hilos a 1,7 GHz, 16 GB de RAM**. No es
una máquina rápida, y eso conviene tenerlo en cuenta al leer las extrapolaciones.

### Descarga

| Bloque | MB | s | MB/s |
|---|---|---|---|
| 559-4674 | 102,9 | 4,3 | 23,9 |
| 562-4668 | 80,4 | 4,0 | 20,0 |
| 549-4679 | 147,5 | 6,8 | 21,8 |
| **Total** | **331** | **15** | **21,9** |

La descarga **no es el cuello de botella**: 22 MB/s sostenidos y el CNIG no limita.

Cuidado con el tamaño: la ficha del CNIG anunciaba 50,81 MB para el bloque de muestra,
pero estos pesan **80–148 MB**. Son bloques con núcleo de población, que tienen más
puntos que la media. A 110 MB de media, los 263 bloques de la comarca son **~28 GB**;
tomando los 50,8 MB de la ficha serían 13 GB. La cifra real estará entre las dos y hay
que dejar sitio para 30 GB.

### Proceso

| Bloque | MB | MDT | MDS | CHM | total |
|---|---|---|---|---|---|
| 549-4679 | 147,5 | 141,8 s | 76,7 s | 0,8 s | **219 s** |
| 559-4674 | 102,9 | 93,0 s | 66,6 s | 0,5 s | **160 s** |
| 562-4668 | 80,4 | 75,7 s | 55,8 s | 0,4 s | **132 s** |

**170 s por bloque de media.** El MDT se lleva el 55 % (es donde está SMRF), el MDS el
44 %, y la resta del CHM es gratis.

Los rásteres pesan poco: **42 MB los nueve** (MDT, MDS y CHM de tres bloques),
GeoTIFF con DEFLATE y predictor 3.

### ¿Cabe la comarca en el plazo?

263 bloques × 170 s = **12,4 h en serie**, más ~25 min de descarga. Con 4 procesos en
paralelo, una noche. Sobre un mes de plazo, **no es un problema**, y por eso no hay que
optimizar nada todavía.

Con dos matices: la RAM no da para 8 procesos a la vez (cada uno pide ~2 GB en el pico de
SMRF), y hay que tener 30 GB libres.

---

## 8. Comprobar que el CHM no está roto

```bash
python scripts/verifica_chm.py
```

### Contraste numérico contra NPC01

Nuestro MDT (SMRF, IDW) contra un MDT hecho con el mínimo de Z de los puntos que **NPC01**
llama suelo. No es una verdad de referencia — NPC01 es clasificación automática sin
revisar, y rehacerla es el motivo de meter SMRF — pero son dos algoritmos independientes:

| Bloque | mediana | σ | \|dif\| < 0,25 m | > 2 m |
|---|---|---|---|---|
| 549-4679 | +0,083 m | 0,263 m | 81,8 % | 0,19 % |
| 559-4674 | +0,053 m | 0,269 m | 91,5 % | 0,13 % |
| 562-4668 | +0,053 m | 0,257 m | 88,5 % | 0,18 % |

Coinciden. El sesgo de +5 a +8 cm es el esperado y no es un error: nuestro MDT interpola
por IDW (una media ponderada) y el de contraste toma el **mínimo** de la celda, que por
construcción está por debajo.

Que la discrepancia grande sea del 0,2 % descarta el fallo que preocupaba: SMRF dejando
arbolado dentro del terreno en las laderas.

### Comprobación visual

`salidas/verifica_*.png`, cuatro paneles por bloque: ortofoto, sombreado del MDT, CHM y
CHM recortado a las franjas.

El sombreado es el panel que delata un MDT malo. En los tres bloques sale limpio: se ven
bancales, caminos, taludes y el encajamiento del río, y **no** hay bultos ni cráteres
donde el CHM tiene arbolado.

---

## 9. Métricas, y tres avisos sobre cómo leerlas

```bash
python scripts/metricas_faixas.py
```

Sobre **104,2 ha** de franja (el 3,7 % de la comarca):

| Umbral | ha | % de la franja |
|---|---|---|
| > 2 m | 59,8 | 57,4 % |
| > 3 m | 47,1 | 45,2 % |
| > 5 m | 38,9 | 37,4 % |
| > 8 m | 30,8 | 29,6 % |
| > 10 m | 26,2 | 25,1 % |

Control de rasterización: 104,2 ha medidas contra 104,3 ha de polígono, **−0,04 %**.

Y ahora los tres avisos, por orden de importancia.

### Aviso 1: esto no es incumplimiento, y el sesgo no es pequeño

La ley solo prohíbe 7 especies arbóreas y **exime a las frondosas no listadas**. Un
castañar dentro de la franja es legal y da exactamente la misma señal en el CHM que un
pinar. Ver [marco legal](03-marco-legal.md).

Mirando la ortofoto de Barcia de Mera (Covelo), que da el 58,2 % sobre 5 m —el valor más
alto de los tres bloques—, buena parte de la masa que rodea el núcleo tiene aspecto de
frondosa de ribera y de soto. **Ese 58 % no es un 58 % de incumplimiento.** La fase 3 no
es un adorno.

### Aviso 2: la resolución del píxel mueve el resultado un 17 %

Mismo bloque, mismas franjas, mismo pipeline, solo cambiando el tamaño de píxel:

| Umbral | 1,0 m | 0,5 m | dif |
|---|---|---|---|
| > 2 m | 17,03 ha | 14,13 ha | −17,0 % |
| > 3 m | 14,97 ha | 12,42 ha | −17,0 % |
| > 5 m | 11,74 ha | 9,82 ha | −16,3 % |
| > 10 m | 6,21 ha | 5,07 ha | −18,3 % |

No es ruido: es sistemático y del mismo signo en todos los umbrales. La causa es que el
MDS toma el **máximo** de cada celda, y una celda de 1 m² pesca el punto más alto de un
área cuatro veces mayor que una de 0,25 m². El CHM a 1 m está sesgado hacia arriba.

Consecuencia práctica: **la resolución hay que fijarla antes de calibrar el umbral, y el
umbral calibrado solo vale para esa resolución.** Cambiarla después invalida la
calibración.

Se elige **1 m** para producción: a 0,5 m el MDT ya tiene un 0,29 % de huecos (a 1 m,
ninguno) porque con 4,9 pts/m² efectivos salen 1,2 puntos por celda, y no cuesta menos
tiempo — el coste está en SMRF, que trabaja sobre la nube y no sobre la rejilla (155 s
frente a 160 s).

### Aviso 3: los edificios cuentan, pero poco

Se temía que los tejados inflasen la métrica. Medido con la clase 6 de NPC01, usada solo
para acotar la magnitud:

| Umbral | % de la superficie sobre umbral que es edificio |
|---|---|
| > 2 m | 2,1 – 3,8 % |
| > 5 m | 1,1 – 2,5 % |
| > 10 m | 0,0 – 1,1 % |

Es poco, y hay un motivo: **la capa de la Xunta ya recorta la huella de las edificaciones
del polígono**. Las illadas tienen 891 anillos interiores (2,0 % de su superficie) y los
núcleos 76 (0,26 %). Los tejados que quedan dentro son sobre todo naves y construcciones
posteriores al plan.

Con un 1–2 % a umbrales altos, descontar edificios **no es prioritario**. Queda anotado
como refinamiento, no como bloqueo.

---

## 10. Fase 2: calibrar el umbral contra ortofoto

```bash
python scripts/muestra_validacion.py    # sortea 400 puntos estratificados
python scripts/chips_validacion.py      # baja la ortofoto y recorta los chips
python scripts/anotador.py              # monta el HTML de anotación
#   -> abrir datos/procesado/validacion/anotador.html y anotar
python scripts/calibra_umbral.py        # umbral + tasa de FP + curva ROC
python scripts/revisa_discrepancias.py  # hojas de contacto de los desacuerdos
```

El estado a 17-08-2026: **todo montado y probado, falta anotar**. Son 400 decisiones
manuales, unos 25 minutos a 3–4 s por chip.

### El diseño, que es donde está el trabajo

**La unidad de validación es el punto, no el polígono.** Una franja de 20 ha no es
"arbolada" o "no arbolada", es un 37 % de algo; el punto es la única unidad sobre la que
un humano da una respuesta binaria fiable en tres segundos. De ahí sale una matriz de
confusión por cada umbral candidato.

**Muestreo estratificado por altura de CHM, no aleatorio simple.** Con muestreo simple
casi todos los puntos caerían en prado raso o bosque cerrado, y casi ninguno en los 1–6 m,
que es donde el umbral se juega. Las cuotas sobremuestrean esa banda:

| Estrato | Área de franja | Puntos | m²/punto |
|---|---|---|---|
| [0, 0,5) m | 29,1 ha | 40 | 7.264 |
| [0,5, 1,5) | 10,4 ha | 50 | 2.080 |
| [1,5, 2,5) | 14,1 ha | 60 | 2.354 |
| [2,5, 4) | 8,1 ha | 60 | 1.355 |
| [4, 6) | 6,6 ha | 60 | 1.104 |
| [6, 10) | 9,7 ha | 50 | 1.948 |
| [10, 20) | 17,9 ha | 50 | 3.579 |
| [20, ∞) | 8,3 ha | 30 | 2.768 |

**El precio de estratificar es que hay que reponderar.** Cada punto lleva un `peso_m2` =
área del estrato / puntos sorteados, que son los metros cuadrados de franja que
representa. Todo se calcula sumando pesos, nunca contando puntos. Control: los pesos
suman 104,3 ha, exactamente el universo.

**Separación mínima de 15 m.** Dos puntos a 3 m caen en la misma copa: no son dos
observaciones, es una contada dos veces, y estrecharía los intervalos de confianza de
mentira.

### La anotación es ciega, y eso obligó a rehacer el anotador

Primera versión: botón de "revelar el CHM" que solo se activaba **después** de responder.
Parecía inofensivo. No lo es: aunque no sesga el chip ya contestado, enseña la relación
entre lo que se ve y lo que mide el LiDAR, y a partir de ahí contamina todos los
siguientes. Está quitado. La altura del CHM **ni siquiera viaja al HTML** — no se puede
enseñar ni mirando el código fuente a media anotación.

Las discrepancias se miran al final, con `revisa_discrepancias.py`, cuando la anotación ya
está cerrada.

Cuatro categorías, no dos: *árbol*, *no árbol*, *edificación* y *dudoso*. Edificación va
aparte porque es un falso positivo de otra naturaleza — el CHM ve el tejado y acierta la
altura, pero no es vegetación. Los dudosos se declaran, se excluyen del cálculo y se
publica su porcentaje.

Y una pregunta secundaria cuando la respuesta es *árbol*: **conífera/eucalipto frente a
frondosa caducifolia**. Quien ya está mirando la ortofoto lo dice casi gratis, y eso le
da a la fase 3 una verdad de referencia y una primera cota del sesgo de especie.

Esa pregunta necesita saber cómo se ve cada tipo desde arriba, que no es evidente.
`scripts/chuleta_especie.py` genera una hoja de referencia con ejemplos reales de la zona
piloto, para tener al lado mientras se anota:

| | Pino | Eucalipto | Frondosa caducifolia |
|---|---|---|---|
| Copa | Estrellada, radial, pequeña | Rala, despeinada | Redondeada, textura de brócoli |
| Color | Verde oscuro grisáceo | Verde azulado o plateado | Verde claro y cálido |
| **Altura** | 20–25 m | **30–50 m** | 15–20 m |
| Patrón | Filas si es plantación | Filas muy densas | Irregular o copas grandes separadas |

**La altura es el rasgo más fiable porque no depende del ojo**: en Galicia solo el
eucalipto pasa de 35 m con regularidad. Y las pistas de contexto valen más que la textura
— fondo de valle en línea es ribera (exenta); copas grandes separadas sobre pasto junto a
la aldea es soto de castaño (exento); ladera con pies alineados es plantación.

Dos cautelas van impresas en la propia hoja: los ejemplos son **fotointerpretación
orientativa, no verdad de campo**, y **ninguno pertenece a la muestra** — están todos a
más de 60 m de cualquier punto sorteado, o serían respuestas dadas de antemano.

Aviso de uso: la pregunta de tipo es **secundaria y prescindible**. No entra en el
umbral ni en la tasa de falsos positivos. Si no se ve claro, *no distinguible* y a
seguir; y si estorba del todo, `--sin-tipo` la quita.

**Etiquetar con dudas sería peor que no etiquetar**: la fase 3 acabaría entrenando y
validando contra ruido, y eso no se detecta después — sale un modelo con métricas
buenas y sesgadas. El clasificador de especie de verdad será el infrarrojo del propio
LiDAR, no el ojo de quien anota.

### Las dos tasas de falsos positivos, que no son la misma

Se confunden todo el rato y aquí importa cuál se publica:

| | Fórmula | Qué dice |
|---|---|---|
| **FPR** | FP / (FP + VN) | De todo lo que no es árbol, qué fracción marcamos. Es el eje X de la ROC |
| **Tasa de FP del producto** | FP / (FP + VP) = 1 − precisión | De la superficie que declaramos arbolada, qué fracción no lo es |

**Se publica la segunda**, que es la que responde a "si mando un inspector a un sitio que
he marcado, qué probabilidad hay de que vaya en balde". La primera casi siempre es más
bonita y publicarla sola sería engañoso.

Intervalos por **bootstrap estratificado**: con pesos desiguales el intervalo binomial no
vale, así que se remuestrea con reemplazo dentro de cada estrato, 2.000 veces.

### Sin escala en la imagen no se puede fotointerpretar

Esto salió anotando, y era un fallo de diseño de verdad. En una foto aérea sin coches ni
edificios cerca **no hay forma de saber si una mancha mide dos metros o veinte**, y esa es
exactamente la diferencia entre un pino joven y una mata de tojo — justo la frontera que
el criterio pide vigilar. Una barra de escala en una esquina no basta: obliga a hacer la
conversión mentalmente en cada chip.

Tres cosas lo arreglan, y las tres van dibujadas sobre la imagen:

- **Rejilla métrica**, casillas de 10 m. El ojo se calibra solo en cuanto la ve.
- **El círculo de la mira mide 3 m de diámetro reales.** Segunda referencia, en el sitio
  donde estás mirando.
- **Encuadre de contexto de 120 m** con la tecla `z`, con el recuadro de 40 m marcado
  dentro. Sirve para desempatar por el patrón de alrededor: una plantación en líneas no se
  parece a una mancha de matorral. No sesga — misma pregunta, más información — y al pasar
  de punto vuelve solo al encuadre corto, para que no se acaben juzgando unos puntos de
  cerca y otros de lejos sin darse cuenta.

### Trampa nº 12: la ortofoto hay que bajarla con margen

El WMS del IGN corta las peticiones en **4096 px**. A 0,125 m/px eso obliga a trocear.

Se pide 0,125 m/px y no los 0,15 m nativos para que entren **8 píxeles de ortofoto por
píxel de CHM**, exacto: con 0,15 m el kilómetro sale a 6.666,67 px y la rejilla no cierra.

Y el mosaico se pasa **64 m del bloque por cada lado**. Sin margen, todo punto cerca del
borde del kilómetro sale con media imagen en negro — un 8 % de la muestra — y no se pueden
tirar sin sesgar: el borde del bloque LiDAR es una línea arbitraria que no tiene nada que
ver con dónde hay arbolado. 64 m es lo que pide el encuadre de contexto (60 m desde el
centro, más holgura); con 32 m bastaba para los chips de 40 m, y hubo que rebajar los
mosaicos al añadir el zoom.

Con ese margen, 1.128 m se parten en **4×4 teselas de 2.256 px exactos**. La división
tiene que dar entero o las teselas no casan al coserlas. El script avisa si algún chip sale
con hueco negro.

Coste: 57 s por bloque de descarga, 20 MB de GeoTIFF con compresión JPEG, cacheado.

### Trampa nº 13: el AUC de una ROC truncada

El barrido de umbrales va de 0,25 a 20 m, así que la curva ROC no llega a las esquinas:
empieza en FPR 0,54 y acaba en 0,02. Integrarla tal cual daba **AUC 0,402 para una curva
casi perfecta**. Hay que anclarla en (0,0) — umbral infinito, no marcamos nada — y en
(1,1) — umbral cero, lo marcamos todo. Con las esquinas puestas, 0,967.

Es un fallo silencioso de los peores: el número sale, es plausible, y está mal.

### El anotador está probado

`scripts/test_anotador.js` extrae el `<script>` del HTML, lo ejecuta contra un DOM
simulado en Node y comprueba 34 cosas: que el flujo de teclado guarda lo que debe, que la
subpregunta de tipo aparece solo con *árbol*, que al revisar avanza de uno en uno pero al
anotar en serie salta a la siguiente sin responder, que las teclas sueltas no crean
respuestas fantasma, que el zoom de contexto no altera ninguna respuesta y no se queda
pegado al cambiar de punto, que el progreso sobrevive a recargar, que el CSV sale bien
formado, y que **la altura del CHM no aparece por ningún lado**.

```bash
node scripts/test_anotador.js
```

Merece la pena porque detrás de esa herramienta hay 400 decisiones manuales, y un bug que
se descubra a mitad obliga a repetirlas.

Aviso: en `file://` algunos navegadores capan `localStorage`. El anotador lo detecta al
arrancar y avisa en pantalla en vez de perder el trabajo en silencio. Si pasa, servir la
carpeta con `python -m http.server` y abrirla por `localhost`.

### Qué NO puede decir esta fase

Si la franja cumple la ley. Mide si hay árbol, no si ese árbol está prohibido. La pregunta
de tipo de copa da una primera cota del sesgo, pero es fotointerpretación a ojo, no
clasificación de especie: eso es la fase 3.

---

## 11. Fase 2: el resultado

Anotados los 400 puntos (24 min) y corrida la calibración:

| | |
|---|---|
| **Umbral calibrado** | **5,5 m** (máximo índice de Youden), a 1 m de píxel |
| Sensibilidad | 89,4 % — IC95 [81,4 – 96,6] |
| Precisión | 75,8 % — IC95 [68,8 – 83,0] |
| **Tasa de falsos positivos del producto** | **24,2 %** — IC95 [17,0 – 31,2] |
| FPR (el de la ROC) | 10,9 % |
| AUC | 0,916 |
| Dudosos declarados y excluidos | 12,4 % de la superficie |

F1 máximo cae en 8,75 m, bastante lejos del 5,5 de Youden. La curva de precisión
es muy plana entre 5 y 10 m, así que **el umbral no está fuertemente determinado**:
subirlo a 8 m cambia poco la precisión y cuesta sensibilidad. Se deja Youden por ser
el criterio declarado de antemano, y la tabla de puntos de operación va en el CSV
para quien quiera moverlo con otro criterio.

### Una medición que no depende del CHM

Como el muestreo es estratificado y ponderado, sumar los pesos por clase da un
estimador insesgado de la composición real de la franja, con el LiDAR fuera de la
ecuación:

| Clase | ha | % |
|---|---|---|
| Sin arbolado | 61,9 | 67,7 % |
| **Arbolado** | **25,3** | **27,7 %** |
| Edificación | 4,2 | 4,6 % |

El CHM a 5,5 m marca 35,9 % de la franja. La fotointerpretación dice 27,7 %. Esa
diferencia **es** la tasa de falsos positivos, medida por otro camino.

### Fiabilidad del anotador: la segunda pasada

`scripts/retest_validacion.py` reanota a ciegas una submuestra y compara. 126 puntos:
los 86 respondidos en menos de un segundo, más 40 de control tomados al azar del
resto, barajados y mezclados.

| Grupo | n | Acuerdo | Kappa de Cohen |
|---|---|---|---|
| Rápidos (< 1 s) | 86 | **97,7 %** | 0,88 |
| Control (≥ 1 s) | 40 | **72,5 %** | 0,53 |

**El resultado desmontó la hipótesis de partida.** Se sospechaba que las respuestas
de menos de un segundo eran una tecla por defecto — la clase «no árbol» tenía mediana
1,3 s y un 33 % bajo el segundo, frente a 3,4 s y 0 % de «dudoso». Resultó al revés:
los rápidos son los **más** reproducibles del conjunto. El tiempo de respuesta mide
dificultad, no descuido: se responde rápido cuando está claro.

**Aviso sobre este diseño.** El grupo de control se sorteó entre los que tardaron más
de un segundo, que por construcción están enriquecidos en casos difíciles. El
contraste 97,7 % contra 72,5 % **no** mide «prisa contra calma», mide «fácil contra
difícil». Lo que sí queda establecido es que la prisa no era descuido, y que en la
zona de decisión la consistencia intra-anotador es kappa 0,53 — moderada. Eso es una
limitación real del producto y se publica junto a la tasa de falsos positivos.

### Análisis de sensibilidad

Rehecha la calibración con la segunda pasada sustituyendo a la primera en esos 126
puntos (13 cambios netos de 400):

| | 1ª pasada | Consolidada |
|---|---|---|
| Umbral | 5,5 m | **5,5 m** |
| Sensibilidad | 88,7 % | 89,4 % |
| Tasa de FP | 26,1 % | 24,2 % |

**El umbral no se mueve y las métricas cambian dentro del intervalo de confianza.**
La calibración es robusta a la variabilidad del anotador. Se publica la consolidada;
la primera pasada queda en `validacion/anotacion_pase1.csv` para poder rehacerlo.

### ¿Cuánto contamina el resultado que el anotador dude?

`scripts/fiabilidad_anotador.py`. La pregunta se puede responder con números en vez
de con buenas intenciones, porque el retest da la tasa de error real del anotador y
esa tasa se puede volver a inyectar en la muestra.

**Dónde duda.** Cortando el retest por altura del CHM:

| Banda | n | Acuerdo | Esperado por azar | Kappa |
|---|---|---|---|---|
| 0–2 m — matorral y suelo | 47 | 93,6 % | 93,8 % | −0,02 |
| 2–8 m — **zona de decisión** | 54 | 90,7 % | 76,3 % | 0,61 |
| > 8 m — arbolado alto | 25 | 80,0 % | 44,2 % | 0,64 |

Ese **kappa de −0,02 con un 93,6 % de acuerdo no es un fallo**: es la paradoja de
kappa. Por debajo de 2 m casi todo es «no árbol», así que etiquetando al tuntún con
esas mismas frecuencias ya se acertaría un 93,8 %, y kappa mide justo lo que se gana
sobre eso. Publicar el kappa a secas ahí sería engañoso en la dirección contraria a
la habitual. Por eso la tabla lleva las tres columnas.

**Propagación.** Cada punto se vuelve a etiquetar al azar con la probabilidad de
volteo medida para su clase y su banda, y se recalibra. 1.000 réplicas:

| | Partida | Con una dosis más de ruido |
|---|---|---|
| Umbral Youden | 5,5 m | 5,5 m — IC95 [5,0 – 6,0] |
| Tasa de FP | 24,2 % | 32,0 % — IC95 [25,8 – 38,4] |

**El umbral se queda a ±1 m del calibrado en el 98 % de las réplicas.**

Y el desplazamiento de la tasa de FP se lee al revés de lo que parece: **el ruido del
anotador la sube, nunca la baja.** Un árbol mal marcado como «no» se contabiliza como
falso positivo aunque el CHM haya acertado — el desacuerdo se le apunta siempre al
CHM. Como la anotación real ya lleva su dosis de ese ruido, **el 24,2 % publicado es
un techo, no una cifra optimista**; extrapolando linealmente a un anotador infalible
saldría en torno al 16 %. Se publica el 24,2 % igualmente: pecar de declarar más
error del que hay es el lado correcto por el que pecar.

**Dos trampas que se evitaron por el camino**, ambas detectadas porque el número salía
plausible y estaba mal:

1. *Aplicar la tasa de volteo de la banda a todas las clases por igual.* «Árbol» son
   87 puntos y «no» son 231; con el mismo volteo se destruyen árboles mucho más
   deprisa de lo que se crean, y la tasa de FP saltaba a 36 % por puro sesgo. Hay que
   condicionar también a la clase de partida.
2. *Dejar mutar los dudosos.* Los 60 dudosos están **fuera** de la calibración por
   protocolo. Devolverlos a cara o cruz no dispersa el resultado, lo desplaza, porque
   pesan más en la parte alta del CHM. Va como escenario aparte: obligarse a decidir
   en vez de declarar la duda **empeora la tasa de FP en 3–4 puntos**. La tecla
   «dudoso» no es tibieza, es lo que impide que el ruido entre en el número.

**Qué limita el resultado.** Comparando la anchura del IC95 de la tasa de FP por cada
fuente de error: 14,2 puntos porcentuales por tener solo 400 puntos, 12,6 por la
variabilidad del criterio. **Mandan los dos por igual.** Si hubiera que estrechar el
intervalo, anotar más puntos y anotar mejor rinden casi lo mismo — y anotar más puntos
es mucho más barato que volverse mejor fotointérprete.

### El sesgo de especie: lo que la subpregunta de tipo de copa NO midió

Aquí hay que ser explícito, porque una versión anterior de este documento daba por
medido algo que no lo estaba.

| | |
|---|---|
| Árboles anotados | 87 |
| Con tipo de copa respondido | **25** |
| — «no distinguible» | 15 (51,9 % de la superficie tipificada) |
| — frondosa caducifolia | 10 (48,1 %) |
| — pino, eucalipto o acacia | **0** |

De ahí salió la frase «el 48 % del arbolado es frondosa exenta». **Se apoya en diez
puntos y no se sostiene.** Peor: que en A Paradanta no aparezca ni un pino ni un
eucalipto en 25 tipificaciones no es una descripción del terreno —es una comarca de
pinar y eucaliptal— sino la señal de que la pregunta no se pudo contestar. Los otros
62 árboles quedaron sin tipo al pasar el anotador a `--sin-tipo` a mitad de la
anotación, precisamente porque distinguir copas en esos chips era inviable.

**Lo que sí quedó establecido, y es un resultado útil aunque negativo: la especie no
se puede tipificar por fotointerpretación sobre ortofoto a 0,125 m/px.** El 60 % de
los intentos acabó en «no distinguible» o sin respuesta. La fase 3 no puede apoyarse
en esta vía para su verdad de referencia y necesita una fuente independiente.

Lo que sigue en pie sin cambios es el argumento legal, que no dependía de esta
medición: la disp. ad. 3ª.3 exime a las frondosas no listadas, en Galicia hay castaño
y roble dentro de las franjas, y el CHM no los distingue de un pino. **El sesgo existe
y su dirección es conocida —sobrestimar el incumplimiento—; lo que no está medido es
su tamaño.**

---

## 12. Fase 3: separar lo prohibido de lo exento

### La fuente, tras un rodeo

La canónica es el **MFE25 del MITECO**, y no hay forma limpia de usarla: su WMS
(`wms.mapama.gob.es/sig/Biodiversidad/MFE`) devuelve una `NullReferenceException` del
servidor a cualquier `GetCapabilities`, en las tres versiones del protocolo, y las
páginas de descarga por provincia pintan los enlaces con JavaScript, así que no hay
URL estable que citar.

La misma cartografía está publicada por la **Xunta** como servicio ArcGIS REST y ahí
sí funciona:

```
https://ideg.xunta.gal/servizos/rest/services/UsosSolo/IFN_2010_EspeciesArboreas
```

Y a diferencia del servicio de faixas —que ignora `returnGeometry` y no suelta
geometrías por ninguna vía— **este las devuelve sin pelea, y ya en EPSG:25829**. 658
polígonos en la zona piloto, 9 segundos. `scripts/descarga_ifn.py`.

Trae hasta tres especies por rodal con su ocupación en **décimas** (`O1+O2+O3` suma 8,
9 o 10, nunca 100) y la fracción de cabida cubierta.

### La clasificación es literal, especie a especie

**No se agrupa por género ni por «perennifolia contra caducifolia».** Esa
simplificación estuvo a punto de colarse en la fase 2 y es falsa en los dos sentidos:

| Trampa | Por qué |
|---|---|
| *Pinus pinea*, *P. nigra* | Son pinos y **no** están en la lista. Agrupar por género prohibiría de más. |
| *Quercus suber*, *Laurus nobilis* | Son perennifolias y **sí** están exentas. El corte legal es la lista, no la fenología. |
| *Robinia pseudoacacia* | Se llama «falsa acacia» y **no es una Acacia**. Está exenta. El nombre común engaña. |

Por eso el diccionario `LEGAL` de `especie_faixas.py` enumera las 29 especies de la
comarca una por una, y **el script aborta si el IFN trae alguna sin clasificar**. Un
`.get(sp, False)` habría dejado entrar cualquier especie nueva como exenta en
silencio, que es el error que más caro sale: rebaja el incumplimiento sin avisar.

La ocupación se usa como **factor continuo**, no como etiqueta: 412 de los 658
polígonos son mixtos, y un rodal con pino 6 y roble 3 no es «un pinar», es 2/3
prohibido.

### El resultado, y por qué el 48 % de la fase 2 era falso

| | Prohibida | Exenta |
|---|---|---|
| Monte de la comarca | **68,2 %** | 31,8 % |
| Dentro de la faixa | **66,9 %** | 33,1 % |
| Donde anotaste «árbol» (ponderado) | **72,2 %** | 27,8 % |

La fase 2 decía que el 48 % del arbolado era frondosa exenta. Con la cartografía
delante, en la faixa la exenta es un tercio, no la mitad, y la especie dominante es
*Pinus pinaster* (55,6 %) seguida de *Quercus robur* (22,6 %) y *Eucalyptus globulus*
(20,0 %).

### El arbolado que el IFN no ve, que es el matiz importante

El IFN cartografía **monte arbolado**, no árboles sueltos. Dentro de una banda de 50 m
pegada a las casas eso deja fuera bastante:

| | Superficie | Composición |
|---|---|---|
| Arbolado dentro de rodal | 15,5 ha (61,3 %) | 72,2 % prohibida, **medido** |
| Arbolado disperso | 9,8 ha (38,7 %) | **no medida** |

Y hay un indicio fuerte de que el disperso es otra población: **de los 10 puntos que
anotaste «frondosa caducifolia», 8 caen fuera de rodal**. Es el castaño de aldea y el
aliso de ribera. También son más bajos (mediana 11,8 m contra 17,2 m dentro de rodal).

Así que la cifra se da como rango, con las dos hipótesis extremas declaradas:

> **Entre el 44 % y el 72 % del arbolado detectado en faixa es especie prohibida.**
> Cota baja: todo el disperso exento. Cota alta: el disperso se comporta como el monte.

Sobre las 104 ha de faixa medidas: de 37,4 ha con arbolado por encima de 5,5 m,
**15,5 a 27,1 ha son de especie prohibida** (14,9 – 26,0 % de la faixa).

### Lo que justifica la fase entera: el orden cambia

| Parroquia | % arbolado | % prohibido | Puesto |
|---|---|---|---|
| Barcia de Mera (San Martiño) | 56,5 % | 23,4 % | 1 → 1 |
| A Cañiza (Santa Teresa) | 37,2 % | 10,0 % | 2 → **4** |
| Vilar (San Xorxe) | 28,2 % | 18,7 % | 3 → **2** |
| Albeos (San Xoán) | 22,1 % | 13,2 % | 4 → **3** |
| As Achas (San Sebastián) | 19,3 % | 2,7 % | 5 → 5 |

**Tres de cinco parroquias cambian de puesto** y la correlación de Spearman entre los
dos órdenes es 0,70. As Achas pasa de 19,3 % a 2,7 %: casi todo su arbolado en faixa
está exento.

Con esta n —pocas parroquias, solo los bloques ya procesados— la cifra es indicativa.
**La dirección no lo es:** mandar a un inspector guiándose por el indicador sin
corregir lo manda al sitio equivocado. Eso era exactamente el riesgo declarado, y
ahora está medido.

### Lo que esta corrección no arregla

- **Catorce años de desfase.** El IFN4 de Galicia es de 2010 y el LiDAR de 2024. El
  error no está repartido al azar: se concentra en el eucaliptal, que se corta a turno
  de 12–15 años y se replanta. O sea, justo en la especie que más importa acertar.
- **Es cartografía de rodal.** La mezcla fina dentro de la faixa queda por debajo de su
  unidad mínima.
- **El 38,7 % del arbolado no está cartografiado** y su composición se declara como
  rango, no se estima.

Ninguna de las tres se resuelve con más cómputo. Se resuelven con teledetección
multitemporal (Sentinel-2), que es la sección siguiente.

---

## 13. Sentinel-2 estacional: montado, y **NO VALIDA**

Conclusión primero, porque es un resultado parcial y sería fácil leerlo de más:
**la señal existe y es físicamente coherente, pero con tres bloques no se puede
validar y no sustituye al IFN.** El número que sale (56,7 % perennifolia) no debe
usarse.

### Primero se comprobó que el atajo era legítimo

El corte legal es una lista de 7 taxones, no «perennifolia contra caducifolia»:
*Quercus suber* y *Laurus nobilis* son perennifolias y están **exentas**. Antes de
gastar un byte en descargas, se midió la traducción contra el IFN:

| | Exenta | Prohibida |
|---|---|---|
| Caducifolia | 283,1 ha | 0,0 ha |
| Perennifolia | 7,6 ha | 925,5 ha |

**99,37 % de acuerdo.** El error del proxy es de 7,6 ha (alcornoque, madroño, laurel) y
no hay ni una caducifolia prohibida. **Eso vale en A Paradanta y no en general**: en un
alcornocal el mismo atajo sería un desastre. Si el método se lleva a otra comarca hay
que rehacer esta comprobación, no heredarla.

### La fuente: STAC público, sin registro

`scripts/descarga_s2.py`. Los COG de Sentinel-2 L2A en AWS, vía el STAC de Element84:

```
https://earth-search.aws.element84.com/v1
```

**No hace falta autenticarse**, al contrario que el Copernicus Data Space, y se lee por
rangos HTTP: solo baja la ventana que interesa. Toda la zona piloto cae en un único
tile MGRS (29TNG). Se componen medianas de tres fechas por estación —invierno 2023-24 y
verano 2024, este pegado a las fechas del vuelo LiDAR— porque con una sola escena una
nube fina o una sombra de relieve se cuela como «caducifolia sin hoja».

### Trampa nº 14: el metadato del STAC miente sobre el offset

Desde 2022 los productos L2A de Copernicus traen los valores desplazados: la
reflectancia es `DN × 0,0001 − 0,1`. El STAC declara `offset: -0.1` en `raster:bands`.
**Pero estos COG ya vienen armonizados**, así que aplicarlo los rompe:

| | NDVI mediana | fuera de [−1, 1] |
|---|---|---|
| Aplicando el offset declarado | 1,299 | **71 %** |
| Sin aplicarlo | 0,679 | 0 % |

La primera versión se fio del metadato y sacó una caída de NDVI con mediana **1,89**,
que es imposible: el NDVI está acotado en [−1, 1]. Se detectó porque 1,89 canta. **Si
el error hubiera dado 0,6 en vez de 1,89 habría pasado limpiamente** y toda la fase se
habría construido encima. Por eso el script lleva ahora una guardia que aborta si más
del 1 % de los píxeles se sale del rango.

Regla general: cuando el metadato y los datos no coinciden, mandan los datos.

### Trampa nº 15: calibrar en un dominio y aplicar en otro

La primera calibración se hizo sobre rodales de monte puros y densos (`O1 ≥ 8`,
`FCC ≥ 70`, erosionados 20 m). Salió **AUC 0,868, sensibilidad 85 %**. Parecía bien.

Contrastado contra el IFN **dentro de la faixa**, que es donde se usa de verdad, el
acuerdo se desplomó:

| | S2 dice caducifolia | S2 dice perennifolia |
|---|---|---|
| IFN caducifolia | 9.732 | 1.127 |
| IFN perennifolia | **9.377** | 8.889 |

**Acuerdo 63,9 %.** De lo que el IFN da por perennifolia, el clasificador acertaba el
**48,7 %** — peor que una moneda.

La causa está medida y es la **mezcla dentro del píxel de 10 m**. Exigiendo que los
100 m² sean todo arbolado según el CHM (que va a 1 m), la separación se recupera entera:

| Pureza mínima del píxel | n px | AUC |
|---|---|---|
| Sin filtro | 29.125 | 0,793 |
| 80 % | 22.660 | 0,853 |
| 100 % | 14.695 | **0,901** |

Tiene sentido físico: en una banda de 50 m un píxel de 10 m rara vez es copa llena —
mezcla arbolado con prado, huerta, camino o tejado, y el prado gallego sí verdea en
primavera, así que la mezcla empuja la caída de NDVI hacia el lado «caducifolia».

De ahí el diseño final: se calibra **dentro de la faixa**, con pureza ≥ 80 %, y lo que
no llega a esa pureza se declara **no clasificable** y se deja al IFN en vez de
inventarle una etiqueta. Solo el **67,9 %** del arbolado en faixa es clasificable.

### Por qué no está validado

La señal es inequívoca y coherente por especie:

| Especie | Caída mediana de NDVI | |
|---|---|---|
| *Quercus robur* | **0,257** | caducifolia |
| *Pinus radiata* | 0,091 | perennifolia |
| *Pinus sylvestris* | 0,019 | perennifolia |
| *Pinus pinaster* | 0,009 | perennifolia |
| *Eucalyptus globulus* | **−0,033** | perennifolia |

Pero la validación cruzada dejando un bloque fuera **no se puede hacer**: de los tres
bloques, solo dos tienen rodales puros dentro de faixa, y **uno de ellos no tiene ni un
píxel caducifolio**. Toda la señal de «caducifolia» sale de un único sitio.

Luego el AUC 0,853 es **in-sample**: mide que la señal existe, no cuánto generaliza. Y
el contraste final —IFN 72,8 % prohibida contra S2 56,7 % perennifolia, 16 puntos de
diferencia— mezcla dos causas que con estos datos **no se pueden separar**: corta real
de eucalipto entre 2010 y 2024, y error del clasificador.

El script imprime `*** ESTE NUMERO NO ESTA VALIDADO ***` en cuanto detecta que no hay
dos bloques con ambas clases, para que nadie lo tome del CSV sin verlo.

**Se valida solo con más bloques, o sea como subproducto de la fase 4.** No hay atajo:
no es cuestión de más cómputo sobre los mismos datos, es que faltan sitios con robledal
y pinar dentro de la misma faixa.

### El veredicto con la comarca entera (19-08-2026)

Con los 263 bloques la validación se pudo hacer, dejando fuera **zonas de 5×5 km**
(no bloques de 1 km: un rodal cruza bloques vecinos y sería fuga). Resultado:

| | con 3 bloques | con la comarca |
|---|---|---|
| AUC in-sample (pureza ≥ 80 %) | 0,853 | 0,761 |
| AUC in-sample (pureza 100 %) | 0,901 | 0,787 |
| AUC fuera de muestra | no se pudo | **0,746** |
| Acierto fuera de muestra, ponderado | — | **65,8 %** |
| Precisión al declarar «caducifolia exenta» | — | **45,8 %** |

Y lo decisivo no es la media, es la **varianza espacial**: el AUC por zonas va de
0,93 a **0,30** — en una zona el clasificador queda anti-correlacionado con la
referencia. Con esa heterogeneidad no existe una sensibilidad/especificidad estable
que permita siquiera una corrección de áreas a lo Rogan–Gladen.

Parte del desacuerdo puede ser culpa de la referencia (IFN de 2010: catorce años de
cortas y replantaciones), no del clasificador. **Da igual para la decisión**: si no
se puede validar contra la única referencia disponible, no entra en el producto. El
0,901 de los 3 bloques queda como lección de muestra pequeña.

**Decisión: el clasificador S2 por píxel NO entra en el producto.** Se publica como
resultado negativo medido. La especie se acota con lo que sí está contrastado: el
IFN aplicado como fracción continua, y la regla estructural de los 35 m (solo el
eucalipto los pasa en Galicia), que da un suelo de especie prohibida desde el
propio CHM.

---

## 14. Fases 4 a 7: lo que hay que saber del código

Los resultados y su discusión están en el README y en `CLAUDE.md`. Aquí va lo que
condiciona cómo se toca el código.

### Orquestación y reanudación

- `procesa_comarca.py` trabaja en **streaming** (descarga → CHM → borra el LAZ) porque
  el crudo no cabe en disco. Reanuda saltando lo que ya tiene CHM, renueva la sesión del
  CNIG cada 25 bloques, no se para por un bloque fallido y tiene guardias de disco
  (< 3 GB) y de batería (< 20 % sin enchufar). Con batería el bloque tarda 420 s en vez
  de 120.
- **Escritura atómica** del CHM (temporal + `os.replace`): sin ella, un corte a mitad de
  escritura dejaba un TIFF truncado que la reanudación daba por bueno para siempre.
- **Los procesos en segundo plano son hijos de la sesión de Claude Code**: si la sesión
  se cierra, mueren. Corridas de horas, desde una terminal propia.
  `vigila_pontevedra.ps1` relanza la corrida si Windows la mata.

### `--zona`: un mismo código para piloto y provincia

- Con `--zona paradanta` (defecto) los ficheros no llevan sufijo; con cualquier otra,
  `_{zona}`. Así el piloto no cambia de nombre y se puede comprobar por no-regresión.
- **Las carpetas `lidar/`, `copas/` y `catastro_celdas/` son compartidas** (A Paradanta
  está dentro de Pontevedra). Todo se filtra por `malla_lidar_{zona}.csv`; un `glob`
  sin filtrar mezcla zonas en silencio.
- **Cada zona valida en su carpeta**: `validacion_producto/` en el piloto (nombre
  histórico) y `validacion_{zona}/` en las demás. De ahí salen la tasa de FP
  (`ranking_final.py`) y, desde el 14-09, la cota alta del disperso
  (`especie_faixas.py`, ver §15).
- `puntos_inspeccion.py`, `visor.py` y `dossier_concello.py` **aún no aceptan `--zona`**.

### Trampas de escala (de 263 a 3.197 bloques)

| Trampa | Síntoma | Arreglo |
|---|---|---|
| `overlay`/`intersects` contra un multipolígono provincial disuelto | horas de CPU sin terminar: el índice espacial no filtra | trocear en piezas de una parte (`dissolve().explode()`) y recomponer; apareció en 6 scripts |
| Núcleos e illadas se solapan | áreas sumadas cuentan dos veces la zona común | unir las piezas que tocan cada rodal antes de intersecar |
| Ventana de rasterio de menos de 1 px | `WindowError` | se salta: el bloque vecino mide ese trozo |
| Bloque sin copas | CSV sin cabecera que rompe la lectura | declarar las columnas del DataFrame vacío |
| Concatenar 12,9 M de copas antes de filtrar | varios GB para tirar el 90 % | cruzar bloque a bloque (mismo orden, `sjoin` conserva el izquierdo) |
| Sentinel-2 en un único compuesto | NaN en tres cuartos de la provincia, sin error | componer por tile MGRS y acumular suma y cuenta por rodal |
| `rasgos()` con 88.624 parches | `MemoryError` | trocear en bloques de 8.000; idéntico bit a bit |
| Dissolve provincial | esquirlas línea/punto que `overlay` rechaza | filtrar a polígonos (área cero) |

Casi todas comparten forma: **el trabajo terminaba bien y el proceso moría en la
contabilidad o en un caso límite** que el piloto no tenía.

### Validación con prefiltro (provincia)

`anotador_prefiltrado.py` quita del anotador humano los «no» claros de
`claude_prefiltro.csv`; `fusiona_prefiltro.py` reconstruye `anotacion.csv` con los 150
puntos en el orden de `muestra.csv` (delegados con `ms=0`). **El orden de filas no es
cosmético**: los bordes del IC bootstrap dependen de él. Tres guardias abortan si el
humano anotó un delegado, si faltan puntos o si hay ids ajenos a la muestra.

### Catastro

El WFS limita por IP. `descarga_catastro.py` **no escribe el agregado si faltan
celdas** (`--parcial` para forzarlo): filtrar con un tercio de la provincia metería un
sesgo espacial imposible de declarar con una cifra. `aplica_copas.py` corre sin él
avisando de que la fracción del disperso sale ligeramente alta.

---

## 15. Limpieza del 14-09-2026

- **La cota alta del disperso venía del piloto también en la provincia.**
  `especie_faixas.py` leía siempre `validacion/` para calcular `p_mal_d` (fracción
  prohibida del IFN donde se anotó árbol), así que Pontevedra heredaba el 72,2 % de A
  Paradanta. Con su propia muestra sale **78,0 %** (46 puntos árbol dentro de rodal). Ahora cada zona usa
  `validacion_{zona}/` y, si no existe, la del piloto con aviso. Mismo patrón que la
  tasa de FP. Efecto en la provincia: la cota inferior no cambia y la superior pasa de 7.969 a
  **8.141 ha**; el orden apenas se mueve (Spearman 0,9996 por concello). No-regresión: la salida del piloto sale
  idéntica.
- **«60 concellos» era erróneo**: la capa de franjas de Pontevedra tiene 54, y son los
  54 del ranking.
- Docstring de `ranking_final.py`: decía que la cota alta añade «el disperso entero»;
  en realidad lo multiplica por `p_mal_d`.
- Imports sin uso eliminados en siete scripts.
- Estados obsoletos corregidos en README, `CLAUDE.md` y `docs/00` y `01` («fase 3 en
  marcha», «Sentinel-2 sin validar», «umbral sin fijar», y la frase falsa de que casi
  la mitad del arbolado del piloto era frondosa exenta, que seguía en el README).

---

## Scripts

| Archivo | Qué hace |
|---|---|
| `scripts/descarga_faixas.py` | Descarga atributos de las capas 0 y 1, pagina y avisa de geometrías vacías. |
| `scripts/carga_faixas.py` | Carga los shapefiles del PBA, filtra la zona piloto y contrasta con la API. |
| `scripts/repara_faixas.py` | `make_valid` sobre las geometrías rotas; comprueba el ancho de 50 m. |
| `scripts/verifica_faixas.py` | IoU contra el `/export` oficial de la Xunta. |
| `scripts/justifica_piloto.py` | Comprueba a posteriori, con la capa de toda Galicia, si A Paradanta es buena zona piloto. |
| `scripts/mapa_geometrias.py` | Mapa de las geometrías descargadas, dibujado en local sin el servicio. |
| `scripts/mapa_faixas.py` | Panorámica de la comarca y zoom, con barra de rótulo. |
| `scripts/mapa_zoom_post.py` | Zoom para divulgación: limpio y con atribución + escala. |
| `scripts/malla_lidar.py` | Malla de bloques de 1 km cruzada con las franjas, y ranking. |
| `scripts/descarga_lidar.py` | Descarga bloques del CNIG y cronometra. |
| `scripts/pipeline_chm.py` | SMRF → MDT / MDS / CHM, con tiempos por etapa. |
| `scripts/verifica_chm.py` | Contraste contra NPC01 y panel visual de comprobación. |
| `scripts/metricas_faixas.py` | Recorte por franja y superficie sobre umbral. Usa el umbral calibrado si existe. |
| `scripts/muestra_validacion.py` | Sorteo estratificado de 400 puntos con pesos y separación mínima. |
| `scripts/chips_validacion.py` | Mosaico de ortofoto por bloque y recorte de un chip por punto. |
| `scripts/anotador.py` | Genera el HTML de fotointerpretación, ciego y con teclado. |
| `scripts/chuleta_especie.py` | Hoja de referencia de tipo de copa, con ejemplos de la zona. |
| `scripts/test_anotador.js` | Prueba el anotador en Node contra un DOM simulado. |
| `scripts/calibra_umbral.py` | Umbral, tasa de falsos positivos con IC y curva ROC. |
| `scripts/revisa_discrepancias.py` | Hojas de contacto de los desacuerdos CHM/ortofoto. |
| `scripts/retest_validacion.py` | Segunda pasada ciega y concordancia intra-anotador. |
| `scripts/fiabilidad_anotador.py` | Propaga el error medido del anotador al umbral y a la tasa de FP. |
| `scripts/descarga_ifn.py` | Baja las especies arbóreas del IFN4 (2010) desde el IDE de la Xunta. |
| `scripts/especie_faixas.py` | Clasifica cada rodal contra la disp. ad. 3ª y corrige el ranking. |
| `scripts/descarga_s2.py` | Compone NDVI de invierno y verano desde los COG de Sentinel-2 en AWS. |
| `scripts/fenologia_especie.py` | Calibra la caída estacional de NDVI. **Validado con la comarca y rechazado** (AUC 0,746 fuera de zona): ver sección 13. |
| `scripts/procesa_comarca.py` | Fase 4: los 263 bloques en streaming (descarga → CHM → borra el LAZ), reanudable. |
| `scripts/ranking_final.py` | El entregable: ranking por franja con arbolado prohibido, con cotas. |
| `scripts/muestra_producto.py` | Muestra de validación del producto: 250 puntos de los 260 bloques nuevos. |
| `scripts/chips_producto.py` | Chips por punto contra el WMS (los puntos caen en ~130 bloques). |
| `scripts/valida_producto.py` | Tasa de FP fuera de muestra del producto, contra la publicada. |
| `scripts/serie_s2_anual.py` | Mediana de NDVI de cada verano 2017–2026, por rodal del IFN. |
| `scripts/detecta_eventos.py` | Eventos de dosel por rodal (caída ≥0,18 y NDVI <0,60), con efecto-año descontado. |
| `scripts/panel_eucalipto.py` | Panel de tres vistas (ortofoto / CHM / S2 actual) de cualquier punto. |
| `scripts/verifica_35m_fenologia.py` | Contraste fenológico del suelo de 35 m: ¿es todo perennifolio? |
| `scripts/muestra_persistencia.py` | Muestra de 65 rodales para validar el detector (eventos + persistentes). |
| `scripts/hojas_persistencia.py` | Hojas de contacto: PNOA 2010–2023 + S2 2024/2026 con el contorno del rodal. |
| `scripts/anotador_persistencia.py` | Anotador ciego de reemplazo de dosel, por intervalos de vuelo. |
| `scripts/valida_persistencia.py` | Compara la anotación con el detector: precisión, falsos negativos y hueco pre-S2. |
| `scripts/regla_dos_veranos.py` | Contraste retroactivo de exigir caída sostenida 2 veranos: rechazada (las cortas rebotan en un año; los incendios no). |
| `scripts/verdades_en_ranking.py` | Pasa los reemplazos confirmados por el ojo a la fracción de especie (no-eucalipto → desconocida); `ranking_final.py` lo prefiere si existe. |
| `scripts/material_hilo.py` | Genera el material de difusión de `salidas/hilo/` (con atribución PNOA/Copernicus horneada); el guion del hilo en `salidas/hilo/guion.md`. |
| `scripts/copas_chm.py` | Segmentación de copas individuales sobre el CHM (watershed): 1,18 M de copas. |
| `scripts/descarga_orto25.py` | Cache de ortofoto PNOA a 0,25 m por bloque (`--trozo i/n` paraleliza). |
| `scripts/muestra_copas.py` | 24k copas de entrenamiento etiquetadas con rodales puros persistentes del IFN. |
| `scripts/parches_copas.py` | Parche de 16×16 m por copa desde la cache de ortofoto. |
| `scripts/embeddings_copas.py` | Embedding MobileNetV3 (CPU) de los parches. |
| `scripts/entrena_copas.py` | Clasificador de especie por copa y validación dejando zonas de 5×5 km fuera. |
| `scripts/descarga_catastro.py` | Huellas de edificio (WFS INSPIRE de Catastro, celdas de 1 km): los tejados pasan el umbral del CHM. |
| `scripts/aplica_copas.py` | Aplica el clasificador al disperso en zonas validadas, excluye copas sobre edificio y corrige con fpr/fnr OOS. |
| `scripts/fotos_copas.py` | Figuras 11–13 del hilo: segmentación, parches y disperso clasificado. |
| `scripts/fotos_verificacion.py` | Figura 14 (2×2 satélite/LiDAR/clasificación) y panel de la casa con los tejados descartados. |
| `scripts/prepara_provincia.py` | Recorta las faixas oficiales a una provincia y repara sus geometrías (el shapefile cubre Galicia entera). |
| `scripts/puntos_inspeccion.py` | Del ranking por parroquia al sitio concreto: puntos anclados en arbolado medido + la mancha de cada uno. |
| `scripts/visor.py` | Visor web autocontenido (`salidas/visor/index.html`): ortofoto, ranking por parroquia y puntos clicables. |
| `scripts/dossier_concello.py` | Dossier PDF de inspección por concello: portada, ranking y una ficha con ortofoto por punto. |
| `scripts/anotador_prefiltrado.py` | Anotador reducido por el prefiltro de Claude: descarta sus «no» claros y deja el resto al humano. |
| `scripts/fusiona_prefiltro.py` | Reconstruye `anotacion.csv` con la anotación humana y los «no» delegados al prefiltro, en el orden de la muestra. |
| `scripts/vigila_pontevedra.ps1` | Vigilante de la corrida provincial: relanza `procesa_comarca.py` si Windows lo mata (Application Hang tras mover el portátil). |
| `scripts/material_hilo_pontevedra.py` | Figuras 16–20 del hilo provincial: mapa por parroquia, ranking de concellos con el piloto, curva de concentración, top 10 de parroquias y la tasa de FP medida tres veces. |
| `scripts/cuenta_tweets.py` | Cuenta los caracteres de cada tweet de un guion de `salidas/hilo/` al estilo de X (emoji 2, URL 23) y avisa si alguno pasa de 280. |
