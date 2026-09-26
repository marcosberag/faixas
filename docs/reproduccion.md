# Reproducción independiente del pipeline (Linux, VPS)

Ejecución independiente del pipeline sobre un VPS Linux (Ubuntu 24.04), cuenta
elCanosail, como verificación externa del claim de reproducibilidad.

Fecha original: 2026-09-19 (hasta el CHM). Actualizado: 2026-09-22 (fase 0 y
métricas).

## Estado: qué está reproducido y qué no

| Tramo | Estado | Fecha | Detalle |
|---|---|---|---|
| **Fase 0** — shapefiles oficiales del PBA → recorte de la zona piloto → reparación → verificación contra el servicio | **Reproducido** | 22-09 | §1 |
| **LAZ → MDT → MDS → CHM** a 1 m, 3/3 bloques piloto | **Reproducido** | 19-09 | §2 |
| **Métricas** (`metricas_faixa_bloque.csv`) y comparación con el CSV del repo | **Reproducido** | 22-09 | §3 |
| Fases 2–7 (calibración, IFN, persistencia, copas, ranking, visor, dossiers) | **No reproducidas** | — | §4 |

La versión del 19-09 decía a la vez que se había alcanzado `metricas_faixa_bloque.csv`
y que su comparación seguía pendiente. Era contradictorio. Con precisión: lo
reproducido hasta el 19-09 era **LAZ → MDT → MDS → CHM en tres bloques**, y la
comparación de métricas quedaba pendiente. El 22-09 se han ejecutado la fase 0 y
las métricas, y se han comparado (§1 y §3).

## 1. Fase 0 — las geometrías oficiales (22-09-2026)

La vía prevista son los **dos shapefiles del visor del PBA** (README; walkthrough
§2 bis), no la vectorización del `/export`:

```
https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa/FaixaProteccion50m.zip
https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa/FaixaProteccion50m_Illadas.zip
```

Descargados y descomprimidos en `datos/crudo/FaixaProteccion50m{,_Illadas}/`, con
los nombres que espera `carga_faixas.py`. Los cuatro scripts de esta parte son
Python puro (`geopandas`, `shapely`, `rasterio`, `PIL`, `requests`): **no hacen
falta PDAL ni micromamba**, corren en el mismo venv de `requirements.txt` que el
resto del pipeline.

```
python scripts/carga_faixas.py
python scripts/repara_faixas.py
python scripts/verifica_faixas.py
python scripts/metricas_faixas.py    # §3
```

### 1.1 Carga y recorte — `carga_faixas.py`

| Comprobación | Medido aquí | Documentado |
|---|---|---|
| Registros en Galicia (núcleos / illadas) | 4.006 / 2.178 | 4.006 / 2.178 |
| Campos del shapefile | `CONCELLOOR, CODPARRO, PARROQUIA, NOMECONCEL, PROVINCIA` | los mismos |
| CRS | EPSG:25829 | EPSG:25829 |
| Zona piloto | **49 / 52 — OK** | 49 / 52 |
| Superficie de la zona piloto | 2.240 ha + 609 ha | 2.240 ha + 609 ha |

Los avisos de `pyogrio` al leer (`Geometry of polygon of fid N cannot be
translated to Simple Geometry`) son los 4 + 15 polígonos inválidos que arregla el
paso siguiente; no son un fallo.

### 1.2 Reparación — `repara_faixas.py`

| | Núcleos | Illadas |
|---|---|---|
| Inválidas antes | 4/49 | 15/52 |
| Inválidas después | 0 | 0 |
| Superficie | 2.240,2 ha → 2.240,2 ha (+0,000 %) | 609,4 ha → 609,4 ha (+0,000 %) |
| Vacías / área cero | 0 / 0 | 0 / 0 |

Cuadra con el walkthrough (§2 bis, trampa nº 5): 4 de 49 y 15 de 52, y la
superficie no se mueve.

### 1.3 Verificación contra el servicio oficial — `verifica_faixas.py`

| Comprobación | Medido aquí | Documentado |
|---|---|---|
| Polígonos sueltos (`explode`) | 2.475 / 1.320 | 2.475 / 1.320 |
| Área por polígono, mediana | 6.400 m² / 2.991 m² | 6.400 / 2.991 |
| Ancho medio `2A/P`, mediana | 30,9 m / 22,4 m | 30,9 / 22,4 |
| Radio inscrito máximo | 47 m / 37 m | 47 m / 37 m |
| **IoU contra el `/export`** | **0,9996** (0 px solo servicio, 64 px solo shapefile) | **0,9996** (0 / 64) |

Coincide al dígito con lo publicado, y el veredicto del propio script
(`COINCIDEN`) se cumple.

## 2. Fase 1 — LAZ → MDT → MDS → CHM (19-09-2026)

Tres bloques piloto (559-4674 A Cañiza, 562-4668 Crecente, 549-4679 Covelo):
descarga LAZ del CNIG → MDT (SMRF con los parámetros gallegos del repo) → MDS →
CHM a 1 m.

### Entorno (diferencias Linux)

- `requirements.txt` instala limpio en un venv de Python 3.12 (geopandas 1.1.4,
  rasterio, shapely, pyproj — todo con wheel).
- PDAL: `pip install pdal` no encuentra wheel para esta plataforma e intenta
  compilar desde fuente (muere en CMake sin libpdal-dev). El apt de Ubuntu 24.04
  no lo trae habilitado. Vía usada: **micromamba con el propio
  `environment-pdal.yml` del repo** (pdal 2.10.2) — fidelidad máxima.
- Fricción encontrada: `pipeline_chm.py` resolvía la ruta de PDAL solo para
  Windows (`~/.local/micromamba/envs/pdal/Library/bin/pdal.exe`). En Linux hizo
  falta un shim de una línea (symlink `bin/pdal` → `Library/bin/pdal.exe`) más
  exportar `GDAL_DATA` y `PROJ_DATA` del env conda (el script propaga
  `os.environ`). La sugerencia (5 líneas: aceptar `PDAL_EXE` de entorno y elegir
  el layout por sistema operativo) está fusionada en `main` vía PR #2
  (`fix/pdal-exe-multiplataforma`, commit `6d55c94`).
- El mensaje de error del script cuando no encuentra el ejecutable es excelente
  (claro, con instrucción de creación del entorno). Solo el path era
  Windows-específico.

### Tiempos y calidad (res 1,0 m)

| Bloque | MB | MDT | MDS | CHM | Total |
|---|---|---|---|---|---|
| 559-4674 | 102,9 | 93,0 s | 66,6 s | 0,5 s | 160,0 s |
| 562-4668 | 80,4 | 75,7 s | 55,8 s | 0,4 s | 131,9 s |
| 549-4679 | 147,5 | 141,8 s | 76,7 s | 0,8 s | 219,3 s |

- Media ~170 s/bloque: **paridad con el i5-8350U documentado** (170 s): el VPS
  no muestra ventaja en este pipeline, aunque esta prueba no permite atribuir
  la causa al I/O o al uso de un solo núcleo. Descarga: 25–26 MB/s (vs 22
  documentados).
- Huecos 0,00 % en MDT/MDS/CHM para los 3 bloques.
- Alturas plausibles: 559-4674 mediana 1,95 m / p90 14,9 / max 44,9 m;
  549-4679 mediana 2,27 m / p90 20,2 / max 50,9 m. Coherente con la regla de
  los 35 m (solo eucalipto).

## 3. Métricas y comparación (22-09-2026)

`metricas_faixas.py` recorta los 3 CHM por las 101 faixas de la zona piloto, a
1 m de píxel y con el umbral calibrado de 5,5 m (lo lee de
`datos/procesado/validacion/calibracion_resumen.csv`).

| Umbral | Medido aquí | Walkthrough §9 |
|---|---|---|
| > 2 m | 59,8 ha (57,4 %) | 59,8 ha (57,4 %) |
| > 3 m | 47,1 ha (45,2 %) | 47,1 ha (45,2 %) |
| > 5 m | 38,9 ha (37,4 %) | 38,9 ha (37,4 %) |
| > 8 m | 30,8 ha (29,6 %) | 30,8 ha (29,6 %) |
| > 10 m | 26,2 ha (25,1 %) | 26,2 ha (25,1 %) |
| **> 5,5 m** (calibrado) | **37,4 ha — 35,9 %** | 35,9 % (fase 1 del README) |

- Superficie de franja medida: **104,2 ha**, el 3,7 % de la comarca.
- Control de rasterización: 104,2 ha medidas contra 104,3 ha de polígono,
  **−0,04 %**.
- Columna nueva de 35 m (suelo de eucalipto): 0,6 ha.

### Comparación con `metricas_faixa_bloque.csv` del repositorio

El CSV versionado cubre los 263 bloques de la corrida completa del piloto (651
filas `faixa × bloque`). Se toman las filas de los tres bloques reproducidos y se
cruzan por `(faixa_id, bloque)`:

| | |
|---|---|
| Filas comunes | 10 / 10 — mismo `faixa_id`, mismo bloque, ninguna suelta |
| Columnas numéricas comparadas | 20 (`ha_medida`, `ha_poligono_en_bloque`, `h_mediana`, `h_p90`, `h_max` y `ha_sobre_*` / `pct_sobre_*` de 2, 3, 5, 8, 10 y 35 m, más el 5,5 calibrado) |
| **Diferencia máxima** | **0** en todas |
| Totales | 104,2338 ha de franja y 37,3929 ha sobre 5,5 m — idénticos |

No es solo compatible: **los valores salen idénticos dígito a dígito**. Los CHM
se regeneraron en otra máquina a partir de los mismos LAZ y los mismos
parámetros, y el recorte por faixa da el mismo número. Con eso quedan cerradas de
extremo a extremo la fase 0, la fase 1 y la comparación de métricas.

## 4. Lo que sigue sin verificar

- Se cubre **fase 0 + fase 1 + métricas**. Las fases 2–7 (calibración del umbral,
  IFN, persistencia, copas, ranking, visor, dossiers) no se han ejecutado aquí.
- Se reproducen **3 bloques** de los 263 del piloto (10 faixas), no la comarca ni
  la provincia.
- El `query` del REST de la IDEG sigue devolviendo `geometry: null`, en VPS y en
  IP residencial (comentario del 21-09 en el issue #1). No es un bloqueo: la vía
  es el visor del PBA, como documenta el walkthrough en §2 y §2 bis. No se ha
  hecho ninguna vectorización del `/export`.
- El filtro provincial de Catastro y la reproducción completa desde un clon
  limpio siguen sin verificarse aquí.
