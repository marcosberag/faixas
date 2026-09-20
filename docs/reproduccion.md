# Reproducción independiente del pipeline (Linux, VPS)

Fecha: 2026-09-19. Ejecución independiente de la fase 1 sobre un VPS Linux
(Ubuntu 24.04), como verificación externa del claim de reproducibilidad.

## Qué se reprodujo

Fase 1 completa en 3/3 bloques piloto (559-4674 A Cañiza, 562-4668 Crecente,
549-4679 Covelo): descarga LAZ del CNIG → MDT (SMRF con los parámetros
gallegos del repo) → MDS → CHM a 1 m. Criterio de salida de la fase 1
(`metricas_faixa_bloque.csv` + tiempos) alcanzado en máquina distinta.

## Entorno (diferencias Linux)

- `requirements.txt` instala limpio en un venv de Python 3.12 (geopandas 1.1.4,
  rasterio, shapely, pyproj — todo con wheel).
- PDAL: `pip install pdal` no encuentra wheel para esta plataforma e intenta
  compilar desde fuente (muere en CMake sin libpdal-dev). El apt de Ubuntu 24.04
  no lo trae habilitado. Vía usada: **micromamba con el propio
  `environment-pdal.yml` del repo** (pdal 2.10.2) — fidelidad máxima.
- Fricción encontrada: `pipeline_chm.py` hardcodea el layout de Windows
  (`~/.local/micromamba/envs/pdal/Library/bin/pdal.exe`). En Linux hace falta un
  shim de una línea (symlink `bin/pdal` → `Library/bin/pdal.exe`) más exportar
  `GDAL_DATA` y `PROJ_DATA` del env conda (el script propaga `os.environ`).
  Sugerencia (5 líneas): resolver `PDAL_EXE` por plataforma o aceptar una
  variable `PDAL_EXE` de entorno — haría el repo reproducible en Linux tal cual.
- El mensaje de error del script cuando no encuentra el ejecutable es excelente
  (claro, con instrucción de creación del entorno). Solo el path es
  Windows-específico.

## Tiempos y calidad (res 1,0 m)

| Bloque | MB | MDT | MDS | CHM | Total |
|---|---|---|---|---|---|
| 559-4674 | 102,9 | 93,0 s | 66,6 s | 0,5 s | 160,0 s |
| 562-4668 | 80,4 | 75,7 s | 55,8 s | 0,4 s | 131,9 s |
| 549-4679 | 147,5 | 141,8 s | 76,7 s | 0,8 s | 219,3 s |

- Media ~170 s/bloque: **paridad con el i5-8350U documentado** (170 s). El VPS
  no aporta ventaja en este pipeline (bound a IO/single-core). Descarga:
  25–26 MB/s (vs 22 documentados).
- Huecos 0,00 % en MDT/MDS/CHM para los 3 bloques.
- Alturas plausibles: 559-4674 mediana 1,95 m / p90 14,9 / max 44,9 m;
  549-4679 mediana 2,27 m / p90 20,2 / max 50,9 m. Coherente con la regla de
  los 35 m (solo eucalipto).

## Hallazgo: la fase 0 (descarga de geometrías) no reproduce hoy

- `ideg.xunta.gal .../PBA/Afeccions_Agropecuaria_Faixas/MapServer` `/0/query` y
  `/1/query` devuelven features con `geometry: null` en TODAS las variantes
  probadas el 2026-09-19: parámetros exactos del script (`outFields=*`,
  `returnGeometry=true`, `returnZ/M=false`, `outSR=25829`), sin returnZ/M,
  `f=geojson`, `outSR=4326`, sin `outSR`, query global `1=1`.
  `outFields=SHAPE` devuelve 0 features directamente.
- El servicio está vivo y el dato también: el endpoint `/export` dibuja las
  franjas correctamente (verificado con un PNG de la comarca piloto — decenas
  de polígonos en su sitio).
- No se pudo discriminar "cambiado para todos" vs "filtrado por origen de
  petición": toda la prueba sale por la misma IP (datacenter). Un vistazo al
  visor oficial desde una conexión residencial lo resolvería.
- Impacto: sin polígonos no hay recorte del CHM → métricas por faixa, celdas de
  Catastro y visor quedan bloqueados por esta vía. La opción 4 documentada
  (vectorizar el /export) sigue disponible como plan B.

## Pendiente de verificación

- Comparación de `metricas_faixa_bloque.csv` con la tabla de fase 1 (104 ha de
  franja, 35,9 % sobre umbral) — bloqueada por el punto anterior.
