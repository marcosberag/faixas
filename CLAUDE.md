# Contexto del proyecto — faixas

Pega esto al arrancar Claude Code, o guárdalo como `CLAUDE.md` en la raíz del repo.

---

## Qué estamos construyendo

Un pipeline en Python que estima, a partir de datos LiDAR públicos, qué franjas de
protección contra incendios en Galicia incumplen la obligación legal de no tener
arbolado.

La Ley 3/2007 de Galicia obliga a gestionar la biomasa en una franja de 50 m alrededor
de núcleos de población y viviendas: vegetación por debajo de cierta altura y
determinadas especies arbóreas eliminadas. Hoy el cumplimiento se verifica mandando
inspectores a pie, parcela por parcela. La Xunta ha duplicado la plantilla de inspección
en 2026.

Existe la capa de obligación (publicada). No existe la capa de cumplimiento. Eso es lo
que construimos.

**Proyecto financiado** por una mini-beca privada (X. Mihura). Plazo aproximado: 1 mes.
Entregable: ranking de parroquias y concellos por superficie de franja con arbolado no
permitido, más el código abierto y reproducible.

## Perfil del desarrollador

Estudiante de Ciencia de Datos e IA en la UPM, entrando a tercero. Trabaja en Python.
Experiencia previa con datos geoespaciales públicos españoles (sistema MRV agrícola
sobre SIGPAC y Copernicus/Sentinel-2). No es experto en teledetección forestal ni en
procesado de nubes de puntos — explica las decisiones de procesado LiDAR, no las des
por sabidas.

Prefiere respuestas directas y concisas, en español informal.

## Fuentes de datos

### 1. Franjas obligatorias — Xunta de Galicia

Servicio ArcGIS REST abierto, sin autenticación:

```
https://ideg.xunta.gal/servizos/rest/services/PBA/Afeccions_Agropecuaria_Faixas/MapServer
```

- **Capa 0**: "Faixa de protección 50m" (núcleos de población)
- **Capa 1**: "Faixa de protección 50m (Illadas)" (edificaciones aisladas)
- Geometría: polígono. CRS: **EPSG:25829** (ETRS89 / UTM 29N, metros)
- `MaxRecordCount`: 1000. Soporta paginación (`resultOffset` + `resultRecordCount`)
- Campos disponibles: `OBJECTID`, `PARROQUIA`, `CONCELLO`, `PROVINCIA`,
  `MODIF_FASE_ANT_ILLADAS`
- **No hay referencia catastral.** Un registro = una parroquia (multipolígono que
  envuelve todos los núcleos de esa parroquia), no una parcela.
- Solo están los concellos con plan municipal de prevención aprobado.

**Aviso (verificado 16-08-2026): este servicio NO devuelve geometrías por ninguna vía.**
No es el fallo `HasZ`/`HasM` que se suponía: el servidor ignora `returnGeometry` y la
respuesta ni siquiera trae la clave `geometry`. Tampoco hay WFS ni FeatureServer. Sirve
para atributos, recuentos y filtros espaciales, no para datos.

**Las geometrías se descargan del visor del PBA** (resuelto 16-08-2026):
```
https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa/FaixaProteccion50m.zip
https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa/FaixaProteccion50m_Illadas.zip
```
Shapefile, EPSG:25829, contrastado contra el servicio oficial con IoU 0,9996. Ese
servidor tiene la cadena TLS incompleta: descargar con `Invoke-WebRequest`, no con
`requests`. Detalle y trampas en `docs/02-walkthrough.md`.

**Segundo aviso: el campo `CONCELLO` lleva artículo pospuesto** — `'Cañiza, A'`, no
`'A Cañiza'`. Un `IN (...)` con la forma natural no da error: devuelve menos registros en
silencio.

Ejemplo de consulta:
```
.../MapServer/0/query?where=CONCELLO+IN+('Arbo','Ca%C3%B1iza%2C+A','Covelo','Crecente')&outFields=*&f=json
```

### 2. LiDAR — PNOA 3ª cobertura (IGN/CNIG)

- Centro de descargas: https://centrodedescargas.cnig.es/CentroDescargas/lidar-tercera-cobertura
- Galicia **ya publicada**, en nivel **NPC01** (clasificación automática provisional)
- Bloques LAZ de 1×1 km. Licencia CC-BY 4.0
- Al ser NPC01 y no NPC02, **la clasificación de suelo hay que rehacerla**, no se puede
  confiar en las clases del fichero

Verificado el 17-08-2026 sobre bloques reales de la zona piloto:

- **La descarga no tiene URL directa.** Hay que pasar por el buscador con sesión:
  `archivosSerie` (`codAgr=MOMDT`, `codSerie=LIDA3`, un punto GeoJSON **en WGS84**) →
  `initDescargaDir` → `descargaDir`. Lo hace `scripts/descarga_lidar.py`.
- **El nombre codifica la esquina NOROESTE**: `...-559-4674-...` cubre X [559000,560000]
  e Y **[4673000, 4674000]**. Suponer la esquina SW no da error, da un CHM del sitio
  equivocado.
- **Los 5 pts/m² son los primeros retornos de la pasada principal.** El fichero trae
  17,5 pts/m²: el 64 % es solape entre pasadas, marcado como **clase 12** (el flag
  `Overlap` de LAS 1.4 está a cero). Sin solape y con un retorno por pulso, 4,9 pts/m².
- **Formato de punto 8: hay `Infrared` por punto**, además de RGB, con datos reales
  (media 28.055, ~27 % de ceros, los mismos puntos que no tienen RGB). Pero **no sirve
  para el corte de la fase 3**: el `gps_time` sitúa el vuelo en **junio–julio de 2024**,
  y la separación caducifolia / perennifolia es fenológica. En verano un castaño y un
  pino dan los dos NDVI alto. Vale como complemento de alta resolución, no como vía
  principal.
- **PDAL no lee el CRS del fichero** (formato de punto 6-10 exige WKT y solo hay GeoKey
  VLR). Hace falta `override_srs=EPSG:25829`.
- Los bloques con núcleo pesan **80–148 MB**, no los 50,8 MB que anuncia la ficha.
- Vuelo de 2024. La ortofoto de la zona es de septiembre de 2023: **un año de desfase**.

### 3. Ortofoto PNOA (para validación manual)

WMS del IGN. Se usa solo para comprobar visualmente una muestra de resultados.

## Zona piloto

**A Paradanta (Pontevedra)**: Arbo, A Cañiza, Covelo, Crecente. ~340 km².

Verificado contra la API el 16-08-2026, con el nombre de concello corregido:

| Concello | Capa 0 | Capa 1 |
|---|---|---|
| Arbo | 8 | 8 |
| Cañiza, A | 12 | 13 |
| Covelo | 18 | 18 |
| Crecente | 11 | 13 |
| **Total** | **49** | **52** |

40 parroquias distintas. Extensión: `548731, 4661398, 567278, 4685317` (EPSG:25829),
18,5 × 23,9 km.

> Los 37 y 39 que figuraban antes aquí salían de una consulta a la que le faltaba
> A Cañiza por el problema del artículo pospuesto.

## Pipeline — montado y medido (fase 1, 17-08-2026)

Por bloque LiDAR de 1×1 km, en `scripts/pipeline_chm.py`:

1. Filtro **streamable** primero: fuera clase 12, y un retorno por pulso. De 17,5 M de
   puntos a 4,9 M. Sin esto, PDAL se queda sin memoria: `elm`, `outlier` y `smrf` cargan
   la nube entera en RAM.
2. `filters.assign` borra la clasificación NPC01
3. `filters.elm` + `filters.outlier` quitan ruido
4. `filters.smrf` clasifica suelo (`slope=0.20`, `window=16`, subido por el relieve)
5. **MDT** por IDW desde los puntos de suelo; **MDS** por máximo de primeros retornos
6. **CHM** = MDS − MDT, **a 1 m** (no cambiar sin recalibrar: a 0,5 m da un 17 % menos)
7. Recorte por franja con `all_touched=False` y métricas → `metricas_faixas.py`

**Medido**: 170 s/bloque en un i5-8350U. La comarca (263 bloques con franja) son 12,4 h
en serie y ~28 GB. No hay que optimizar nada.

**PDAL en Windows**: no hay wheel de pip. Entorno conda aparte con micromamba, y llamar
a `envs\pdal\Library\bin\pdal.exe` directo (`micromamba run` se come el stderr). El resto
del pipeline sigue en el Python del sistema.

**Stack**: PDAL, GDAL, rasterio, GeoPandas, NumPy, SciPy, laspy.

## Decisiones de diseño que NO se cambian

Estas ya están tomadas y forman parte del compromiso de la propuesta:

- **Solo arbolado, no matorral.** El vuelo LiDAR es una foto fija y el matorral
  estacional rebrota entre vuelos. A 5 pts/m² tampoco se discrimina bien una altura
  de 20 cm. El arbolado es estructural y ahí la norma es taxativa.
- **Salida como indicador de riesgo, nunca como acusación.** Hay explicaciones
  legítimas para muchos patrones. El framing es "herramienta de triaje para priorizar
  inspección", no "lista de infractores".
- **Unidad de análisis: parroquia y concello.** No parcela — la capa oficial no trae
  referencia catastral y bajar a parcela exigiría cruzar con Catastro por nuestra
  cuenta, con atribución discutible.
- **Validación manual obligatoria** contra ortofoto sobre muestra aleatoria, con tasa
  de falsos positivos publicada.

## Validación — COMPLETADA (fase 2, 18-08-2026)

**Umbral calibrado: 5,5 m** a 1 m de píxel. **Tasa de FP del producto: 24,2 %**,
IC95 [17,0 – 31,2]. Sensibilidad 89,4 %, AUC 0,916, 12,4 % de dudosos excluidos.
`metricas_faixas.py` ya lo consume solo desde `validacion/calibracion_resumen.csv`.

## Fase 3 — especie (18-08-2026, en marcha)

**Fuente: IFN4 2010 vía IDE de la Xunta**, `UsosSolo/IFN_2010_EspeciesArboreas`.
Devuelve geometrías (al revés que el servicio de faixas) y ya en EPSG:25829. 658
rodales en la zona piloto, 9 s de descarga.

**La clasificación legal es literal, especie a especie.** No agrupar por género ni por
perennifolia/caducifolia: `Pinus pinea` y `P. nigra` NO están en la lista; `Quercus
suber` y `Laurus nobilis` son perennifolias y SÍ están exentas; `Robinia pseudoacacia`
se llama «falsa acacia» pero no es Acacia y está exenta. `especie_faixas.py` **aborta**
si aparece una especie sin clasificar — un `.get(sp, False)` dejaría entrar cualquier
especie nueva como exenta en silencio.

**La ocupación (`O1,O2,O3`) son DÉCIMAS** y suman 8–10, no 100. 412 de 658 rodales son
mixtos, así que se usa como factor continuo, no como etiqueta.

Resultado: en faixa, **66,9 % prohibida / 33,1 % exenta**; donde se anotó árbol, 72,2 %
prohibida. Pero el IFN solo cartografía monte: **el 38,7 % del arbolado en faixa es
disperso y no está medido** (y 8 de los 10 puntos anotados «frondosa» caen ahí). De ahí
que la cifra se dé como rango: **44–72 % del arbolado detectado es prohibido**.

**Lo que justifica la fase: el ranking se REORDENA, no se escala.** 3 de 5 parroquias
cambian de puesto, Spearman 0,70. As Achas pasa de 19,3 % arbolado a 2,7 % prohibido.

**El sesgo de especie NO estaba medido, y la frase «el 48 % es frondosa exenta» que
figuraba aquí era falsa.** Se apoyaba en 10 puntos: de 87 árboles anotados solo 25
llevan tipo de copa, 15 de ellos «no distinguible» y **cero** de la lista prohibida —
en una comarca de pinar y eucaliptal, lo que delata que la pregunta no se pudo
contestar, no que no haya pinos. Los otros 62 se quedaron sin tipo al pasar a
`--sin-tipo` a mitad. Resultado negativo aprovechable: **la especie no se tipifica por
fotointerpretación sobre ortofoto a 0,125 m/px**, así que la fase 3 necesita verdad de
referencia de otra fuente (MFE del MITECO es la candidata). El sesgo existe y su
dirección se conoce —sobrestima el incumplimiento—; su tamaño no.

**Concordancia intra-anotador (retest ciego de 126 puntos):** kappa 0,88 en los
casos claros, **0,53 en la zona de decisión**. Se publica como limitación.
Ojo con la lectura del tiempo de respuesta: se sospechó que las respuestas de menos
de un segundo eran una tecla por defecto y resultó lo contrario — son las MÁS
reproducibles (97,7 %). El tiempo mide dificultad, no descuido.

**El error del anotador está propagado, no supuesto** (`fiabilidad_anotador.py`).
Acuerdo consigo mismo: 93,6 % por debajo de 2 m, 90,7 % en la zona de decisión de
2–8 m, 80 % por encima de 8 m. Reinyectando ese error en la muestra, **el umbral se
queda a ±1 m del calibrado en el 98 % de 1.000 réplicas**. Tres cosas que no hay que
volver a equivocar aquí:

- **El ruido del anotador SUBE la tasa de FP, nunca la baja**: el desacuerdo CHM /
  anotador se contabiliza como fallo del CHM aunque sea del anotador. Luego el 24,2 %
  es un **techo** (extrapolando a anotador infalible saldría ~16 %). Se publica el
  24,2 % de todas formas: pecar de pesimista es el lado correcto.
- **La tasa de volteo hay que condicionarla a la CLASE, no solo a la banda de
  altura.** «Árbol» son 87 puntos y «no» 231; con volteo uniforme se destruyen árboles
  más deprisa de lo que se crean y la tasa de FP saltaba a 36 % por puro sesgo.
- **Los dudosos no se dejan mutar**: están fuera por protocolo y devolverlos a cara o
  cruz desplaza el resultado en vez de dispersarlo. Como escenario aparte: obligarse a
  decidir empeora la tasa de FP 3–4 puntos.
- Kappa −0,02 con 93,6 % de acuerdo en la banda 0–2 m **no es un fallo**, es la
  paradoja de kappa (el azar ya acierta un 93,8 % con esas frecuencias). Imprimir
  siempre acuerdo, esperado por azar y kappa juntos.

Anchura del IC95 de la tasa de FP por fuente: 14,2 pp por el tamaño de muestra,
12,6 pp por el criterio del anotador. **Mandan por igual**, y anotar más puntos es más
barato que mejorar como fotointérprete.

Cómo se hizo:

- **400 puntos** en `datos/procesado/validacion/muestra.csv`, muestreo estratificado por
  altura de CHM con cuotas que sobremuestrean los 1–6 m. Cada punto lleva `peso_m2`
  (= área del estrato / puntos sorteados): **se suman pesos, nunca se cuentan puntos**.
  Separación mínima de 15 m. Semilla 20260817.
- **Anotación ciega sin excepciones.** La altura del CHM no viaja al HTML. Hubo un botón
  de "revelar tras responder" y está quitado: enseña la relación y contamina los chips
  siguientes. Las discrepancias se revisan al final con `revisa_discrepancias.py`.
- **Se publica la tasa de FP del producto** (1 − precisión), no el FPR de la ROC. IC por
  bootstrap estratificado.
- Ortofoto a **0,125 m/px** (8 px por píxel de CHM, exacto) y con **64 m de margen** sobre
  el bloque, o los puntos del borde salen con medio encuadre en negro.
- **Los chips llevan rejilla métrica de 10 m y la mira mide 3 m de diámetro.** Sin
  referencia de escala no se distingue un pino joven de una mata de tojo, que es
  justamente la frontera del criterio. Tecla `z`: encuadre de contexto de 120 m.
- El anotador tiene pruebas en Node: `node scripts/test_anotador.js` (34 casos).
- **La acacia (mimosa) es una frondosa y ESTÁ PROHIBIDA.** Las categorías de tipo van
  por estatus legal, no por botánica: pino / eucalipto / acacia (las tres de la lista)
  frente a frondosa caducifolia (la única exenta). La primera versión agrupaba mal.
- La pregunta de tipo de copa es **secundaria y prescindible** (`--sin-tipo` la quita): si no se
  ve claro, «no distinguible». Hay chuleta en `salidas/chuleta_tipo_copa.png`, con
  ejemplos de la zona que **no** salen de la muestra. La altura es el rasgo más fiable: en
  Galicia solo el eucalipto pasa de 35 m.

Trampa detectada: **el AUC de una ROC truncada**. El barrido no llega a las esquinas y
`np.trapezoid` daba 0,402 para una curva casi perfecta. Hay que anclar en (0,0) y (1,1).

## Sentinel-2 estacional — VALIDADO CON LA COMARCA Y RECHAZADO (19-08-2026)

**El clasificador por píxel NO entra en el producto.** Validación cruzada dejando
zonas de 5×5 km fuera (no bloques de 1 km: los rodales cruzan bloques y hay fuga):
AUC 0,746 y acierto 65,8 % ponderado fuera de muestra, precisión 45,8 % al declarar
«caducifolia exenta», y AUC por zonas entre 0,93 y **0,30** — sin estabilidad no hay
ni corrección de áreas posible. El 0,853/0,901 de los 3 bloques era muestra pequeña
(con la comarca, in-sample baja a 0,761/0,787). Parte del desacuerdo puede ser del
IFN 2010 como referencia, pero lo invalidable no se usa. Se publica como resultado
negativo medido. La especie se acota con IFN + regla de 35 m (`ha_sobre_35m`).

Lo de abajo queda como registro de cómo se montó:

**No usar el 56,7 % que imprime `fenologia_especie.py`.** El script avisa solo.

Lo que sí quedó establecido:

- **El proxy fenológico reproduce el corte legal con 99,37 % de acuerdo** aquí (7,6 ha
  de perennifolias exentas: alcornoque, madroño, laurel; cero caducifolias prohibidas).
  **Vale en A Paradanta, no en general** — en un alcornocal sería un desastre. Rehacer
  la comprobación si el método se lleva a otra comarca.
- **Fuente sin registro**: STAC de Element84 sobre los COG de AWS
  (`earth-search.aws.element84.com/v1`), leído por rangos HTTP. Toda la zona en un tile
  (29TNG). Medianas de 3 fechas por estación.
- **Señal inequívoca**: caída de NDVI verano→invierno de 0,257 en *Quercus robur*, 0,009
  en *Pinus pinaster*, −0,033 en *Eucalyptus globulus*.

Tres trampas que costaron, y que no hay que repetir:

- **El STAC declara `offset: -0.1` y estos COG ya están armonizados.** Aplicarlo mete el
  71 % de los píxeles fuera de [−1, 1] y da NDVI mediana 1,89. Se cazó porque 1,89 es
  imposible; **con 0,6 habría pasado**. Hay una guardia que aborta si >1 % sale de rango.
  Cuando el metadato y los datos discrepan, mandan los datos.
- **Calibrar en monte y aplicar en faixa no funciona.** AUC 0,868 en rodal denso, y al
  contrastar dentro de faixa el acuerdo cae al 63,9 % (48,7 % de acierto en lo
  perennifolio). La causa es la **mezcla en el píxel de 10 m**: con pureza ≥ 100 % el
  AUC sube a 0,901. Se calibra en faixa y lo impuro se declara no clasificable (queda
  fuera el 32,1 % del arbolado).
- **Con 3 bloques no hay validación cruzada posible**: solo 2 tienen rodales puros en
  faixa y uno no tiene ningún píxel caducifolio. El AUC 0,853 es **in-sample**. La
  diferencia con el IFN (72,8 % vs 56,7 %) mezcla corta real de eucalipto y error del
  clasificador, y no se pueden separar.

## Persistencia y vigilancia — VALIDADA (19-08-2026): la persistencia aguanta, los eventos no

**Idea**: los árboles no cambian de especie; si un rodal del IFN 2010 no sufrió un
evento de reemplazo, su etiqueta vale hoy. Detectar eventos es tratable con S2
(al revés que clasificar especie). El mismo detector, hacia adelante, es el
servicio de vigilancia (¿se cortó tras el vuelo LiDAR? ¿se limpió tras inspección?).

- `serie_s2_anual.py`: mediana de NDVI de cada verano 2017–2026 (3 escenas menos
  nubladas), media por rodal. **Diagnóstico de deriva limpio**: medianas de zona
  0,75–0,80 sin escalón en 2022, el archivo AWS es homogéneo. Reanudable.
- `detecta_eventos.py`: evento si caída ≥0,18 respecto al máximo de los 2 años
  previos Y NDVI <0,60, con efecto-año de zona descontado. Asimetría del rebrote:
  eucalipto cortado sigue prohibido; otra especie cortada pasa a DESCONOCIDA
  (la replantación gallega post-2010 tiende a eucalipto), nunca a exenta.

**Resultado**: 97,4 % del rodal-en-faixa persistente 2017–2026 — el miedo «el IFN
de 2010 está caducado» queda acotado a 17,7 ha con evento (15,6 ha a desconocida).
70 eventos en la comarca entera (el 71 que figuró aquí contaba uno de más); **37 son de 2018 y forman manchas contiguas: las
cicatrices de los incendios de octubre de 2017** (limite con As Neves) — validación
natural con verdad documentada. 5 rodales con evento posterior al vuelo LiDAR
(aviso de vigencia: ese arbolado puede ya no estar).

Trampas de esta fase:
- **Rodal ralo = NDVI de hierba.** El evento 2026 del rodal 86265 (Quercus, FCCARB
  45 %) es casi seguro agosto seco sobre prado, no corta: el panel lo enseñó. El
  efecto-año medido sobre la mediana de rodales (monte cerrado) NO corrige esto.
  Los eventos en rodales con FCCARB bajo se miran con lupa en la validación.
- El hueco 2010–2017 no lo cubre S2: es de las ortofotos históricas del PNOA.
- ~~Nada entra en el ranking hasta validar~~ **validado** (abajo): la persistencia
  entra como respaldo del IFN; eventos y vigilancia quedan fuera.
  `panel_eucalipto.py --x --y --bloque --titulo --salida` genera el panel de tres
  vistas de cualquier punto.

**Validación del detector — HECHA (19-08-2026, 65/65 anotadas, 0 dudosos). El
resultado parte el detector en dos:**

- **Persistentes: 23/26 confirmados, 1 falso negativo (3,8 % [0,4–16,6]), 2
  eventos pre-S2** (erosionan la etiqueta IFN, no son fallo). El titular queda
  acotado en **[81,2–99,4 %]**, y los falsos positivos de eventos empujan en la
  dirección segura: el 97,4 % es un **suelo** de la persistencia real.
- **Eventos: 13/33 = 39,4 % [24,2–56,4] de precisión**, pero partida por época:
  **11/16 (69 %)** donde hay ortofoto (2019–2023; 12/16 contando los vistos en el
  intervalo vecino) y **2/17 (12 %)** en 2024–2026 donde solo hay S2, con **0/8 en
  2026** — la firma de la sequía de agosto de 2026, el modo del 86265, ahora
  medido. **Ni FCCARB ni la magnitud de la caída lo separan** (13 de 17 no vistos
  son rodales densos; caída media 0,261 en no vistos vs 0,272 en confirmados): no
  hay filtro barato. **Y la regla de los dos veranos está medida y RECHAZADA**
  (`regla_dos_veranos.py`, retroactiva sobre la anotación): las cortas reales
  REBOTAN en un año (12 de 16 no sostienen la caída en t+1 — el eucalipto rebrota
  de cepa y la hierba coloniza; NDVI no es biomasa) mientras 3 de 9 espejismos sí
  la sostienen. Precisión 57 % con la regla vs 64 % sin ella (eventos evaluables,
  2026 excluido) perdiendo 12/16 eventos reales. Las cicatrices de INCENDIO son
  la excepción: 5/6 sostenidas — el fuego persiste en NDVI, la corta no. Arreglar
  la vigilancia exigiría compuestas subanuales (cazar la corta antes del rebrote),
  no otro umbral anual.
- **Vigencia: 1/13 avisos post-LiDAR confirmados.** Los «5 rodales con evento
  posterior al vuelo» NO se publican como hecho.
- **Controles de 2018: solo 2/6 vistos.** El fuego no siempre reemplaza el dosel
  visible al vuelo siguiente (copas supervivientes, rebrote para 2020). Límite del
  protocolo, se publica: por esto el 39,4 % es también un suelo.
- Consecuencia: **la persistencia respalda usar el IFN 2010 en el ranking; el
  listado de eventos y el servicio de vigilancia se quedan fuera.** El camino
  futuro declarado es subanual (compuestas mensuales de S2, cazar la corta antes
  del rebrote), no reglas sobre la serie anual: eso ya se probó y no da.
- **Lo confirmado por el ojo SÍ entra** (`verdades_en_ranking.py`): los 22
  reemplazos anotados corrigen la etiqueta rodal a rodal — no-eucalipto
  reemplazado → desconocida (sale de la cota inferior, sube a 1 en la superior;
  eucalipto rebrota y sigue prohibido). 5 rodales no-euca tocan faixa (~7,6 ha
  de arbolado afectado) y **la cota inferior baja de 302 a 297 ha**. Escribe
  `metricas_parroquia_especie_verdades.csv` y `ranking_final.py` lo prefiere si
  existe (mismo patrón que `resumen_producto.csv`). La erosión pre-S2 de la
  etiqueta IFN queda cuantificada: **2/26 = 7,7 % [1,6–22,5]** (Jeffreys).

Cómo se hizo:

- **El PNOA histórico tiene vuelo en la zona en 2004, 2008, 2010, 2014, 2017, 2020
  y 2023** (WMS `https://www.ign.es/wms/pnoa-historico`, capas `PNOA{año}`; los años
  sin vuelo devuelven blanco uniforme, se detecta con `std < 5`). Que exista 2010 —
  el año de la etiqueta del IFN — es un regalo.
- `muestra_persistencia.py`: 65 rodales barajados (semilla 20260819): TODOS los
  eventos no-2018 (33), 6 cicatrices de 2018 como control positivo, 20 persistentes
  en faixa + 6 fuera. Ciego parcial declarado: el anotador ya vio el mapa de eventos
  y el panel del 86265.
- `hojas_persistencia.py`: hoja de contacto por rodal, 8 paneles (PNOA 2010–2023 +
  S2 visual verano 2024 y reciente 2026 + contexto ×2,5) con el contorno del rodal.
  Los visuales de zona S2 se cachean en `s2/visual_{año}.tif`. Reanudable, ~14 s/hoja.
- `anotador_persistencia.py`: HTML ciego (solo ids barajados). Pregunta: ¿reemplazo
  del dosel? y **en qué intervalo(s)** — eso separa después fallo del detector de
  evento pre-S2 (2010–2017, hueco declarado). **Umbral de superficie declarado:
  «sí» a partir de ~1/3 del rodal reemplazado.** El detector va sobre la media de
  NDVI del rodal y una corta baja el NDVI local 0,4–0,5 desde ~0,78: mover la media
  0,18 exige ~40 % del área. Por debajo es ciego por diseño; anotar esas calvas como
  «sí» inflaría los falsos negativos con algo que el detector no puede ver.
  **El crecimiento no es reemplazo** (rodal joven que se cierra → «no»); una
  plantación nueva sobre suelo antes raso sí lo es (filas regulares la delatan). El CSV descargado va a
  `validacion_persistencia/` (LA MISMA trampa de carpetas de siempre).
- `valida_persistencia.py` (correr cuando exista `anotacion.csv`): mapea año del
  evento → intervalo de vuelos con tolerancia en los bordes (si t coincide con año
  de vuelo, valen los dos intervalos). Reporta precisión de eventos (sin 2018, sin
  dudosos, IC Jeffreys), falsos negativos de persistentes (solo cambios 2017+; los
  pre-S2 se cuentan aparte: erosionan la etiqueta IFN, no el detector) y la cota
  corregida del titular del 97,4 %.

## Fase 6 — especie por copa (20-08-2026): entrenada, validada e INTEGRADA por zonas

Del píxel a la copa: watershed sobre el CHM (1,18 M de copas en la comarca,
`copas_chm.py`, 0,6 s/bloque) + parche de ortofoto de 16×16 m a 0,25 m por copa
+ clasificador eucalipto/pino/frondosa. **Las etiquetas de entrenamiento salen
gratis del IFN**: 24.000 copas de rodales puros (O1 ≥ 80 %) y PERSISTENTES
(la fase 5 filtra el training set), erosionados 10 m. Acacia fuera (1 rodal puro).

- **Rasgos clásicos (color+textura+estructura): AUC eucalipto 0,845 OOS.**
  **+ embedding MobileNetV3 (`--cnn`): 0,860 — SUPERA el listón prefijado (0,85).**
  Prohibida-contra-frondosa: 0,865. Acierto 3 clases: 70,7 %. Todo GroupKFold
  dejando zonas de 5×5 km fuera.
- **Pero la inestabilidad del S2 reaparece en el este**: zonas 113_933 (AUC 0,31)
  y 113_934 (0,54), mediana 0,83, máx 0,94. A ojo (hoja `salidas/diag_zona_mala.png`):
  ahí la ortofoto es de otra pasada, oscura y con el contraste aplastado — las
  tres clases son indistinguibles hasta para el ojo. **Gray-world probado y
  RECHAZADO** (empeora: 0,823 global, la zona mala solo sube a 0,49): el color
  absoluto lleva señal real y aquello no es solo ganancia de canal.
- **El «contraste >35 m» NO es un contraste limpio**: el 39 % de las copas >35 m
  del entrenamiento cae en rodales puros NO-eucalipto — la pureza 80 % deja
  hasta un 20 % de ocupación de otra especie, y lo que asoma por encima de 35 m
  es justamente el eucalipto invasor. Consecuencia doble: (a) esa comprobación
  no sirve como verdad, y (b) **hay ruido de etiqueta real en el entrenamiento**,
  así que el 0,86 medido contra etiquetas ruidosas es más bien un suelo de la
  discriminación verdadera — pero la calibración hereda el ruido.
- **Cobertura del objetivo** (el disperso: 32.035 copas en faixa fuera de rodal,
  el 34 % de las copas en faixa): **54 % en zonas validadas (AUC ≥ 0,80), 21 % en
  zonas malas, 25 % en zonas sin rodal puro (sin validación posible)**.
- **INTEGRADO (decidido por el usuario): solo zonas con AUC OOS ≥ 0,80** (8
  zonas; el 45 % del disperso — 112_934 se queda fuera por décimas al recalcular
  el AUC binario). `aplica_copas.py`: clasifica el disperso validado (fracción
  observada prohibida 59,9 % ponderada por área), corrige con fpr 0,304
  [0,293–0,316] y fnr 0,167 [0,158–0,176] OOS (corrección estándar, cuatro
  esquinas del IC) → fracción real **[0,54–0,58]** frente a la cota ciega
  [0, 0,722]. Escribe `metricas_parroquia_especie_copas.csv` (encadena sobre
  verdades) y `ranking_final.py` lo prefiere. **Titular: [297–588] → [353–574] ha**
  (−24 % de anchura, cota inferior +57 ha). Mourentán sube a 32–42 (disperso
  eucaliptal medido); Arbo adelanta a Covelo. Advertencias declaradas: el IC no
  recoge heterogeneidad entre zonas ni el ruido de etiqueta del IFN.
- **Filtro de edificios del Catastro (21-08-2026), a raíz de la casa del usuario
  delineada como «copa» de 10 m**: un tejado a dos aguas pasa el umbral de 5,5 m
  (SMRF lo marca no-suelo) y el watershed lo segmenta. `descarga_catastro.py`
  baja las huellas BU:Building del WFS INSPIRE por celdas de **1×1 km** (el
  servicio rechaza 2×2: «Area of extension out of limits»; y hay DOS variantes
  de celda vacía: ExceptionReport y GML sin capa — las dos toleradas). 13.452
  edificios en zona de faixa; `aplica_copas.py` excluye las copas con ápice
  sobre huella+1 m: **589 copas eran tejados** (1,8 % del disperso; la fracción
  observada baja de 60,2 a 59,9 % — los tejados se colaban como prohibida). En
  agregado ya lo pagaba la tasa de FP; esto limpia el mapa y la fracción del
  disperso. Bajo el criterio del usuario (FN fatal, FP barato) es gratis: un
  tejado no es un eucalipto que se pueda perder. Titular: cota inferior 354→353.
  `fotos_verificacion.py` regenera la 2×2 y el panel de la casa
  (`salidas/diag_casa_usuario_filtrada.png`: huellas cian, tejados con ×).

Scripts: `copas_chm.py`, `muestra_copas.py`, `descarga_orto25.py` (0,25 m,
cache por bloque, `--trozo i/n` para paralelizar), `parches_copas.py`,
`embeddings_copas.py`, `entrena_copas.py` (`--cnn`, `--gw`),
`descarga_catastro.py`, `aplica_copas.py`, `fotos_copas.py` (figuras 11–13),
`fotos_verificacion.py` (la 2×2 y el panel de la casa). Ojo: cada corrida
de `entrena_copas.py` PISA `oos_predicciones.csv` y el joblib — la última debe
ser siempre la variante buena (--cnn).

**Claude como segundo anotador — piloto medido (20-08-2026):** 48 chips de la
fase 2 a ciegas: acuerdo árbol/no-árbol 76,5 %, kappa 0,51 — NO sustituye al
anotador humano (su retest: 90-94 %). Pero el error es asimétrico: 0 árboles
humanos entre sus 25 «no» — sirve como prefiltro que descarta negativos claros
(~la mitad de la carga) y deja al humano solo los «árbol» y dudosos.

## Fase 7 — de piloto a producto (21-08-2026, EN MARCHA)

Decisión del usuario: **A+B a la vez** — escalar a la provincia de Pontevedra
(tiempo de máquina, desatendido) y convertir el CSV en herramienta usable
(tiempo de desarrollo, en paralelo). El diagnóstico que la motiva: el valor de
hoy es metodológico, y A Paradanta es **el 1,7 % de la faixa gallega**.

### A — Pontevedra

- **El shapefile del PBA cubre Galicia entera** (4.006 registros de núcleos:
  A Coruña 1.065, Lugo 1.132, Ourense 1.049, Pontevedra 760). No hay que
  descargar nada nuevo para escalar. `prepara_provincia.py --provincia X`
  recorta y repara (155 + 95 geometrías inválidas en Pontevedra).
- Pontevedra: **1.268 registros, 38.627 ha de faixa, 3.197 bloques** que la
  tocan (12,2× el piloto). Redondela y Ponteareas encabezan.
- `malla_lidar.py` y `procesa_comarca.py` aceptan `--zona` / `--malla`.
- **TRAMPA DE ESCALA, medida: `gpd.overlay` contra un multipolígono
  provincial DISUELTO no escala.** Dos geometrías de medio millón de vértices
  dejan el índice espacial inútil y cada celda paga la geometría entera: 2 h
  de CPU al 95 % sin terminar. La versión que trocea en piezas de una parte
  (`interseca()`) y usa `shapely.intersection` vectorizado tarda **4 min**.
  **La misma trampa reapareció en `especie_faixas.py`** (28-08): el overlay
  IFN × faixas disueltas llevaba 3 h de CPU sin pasar de la sección 2 con
  la provincia. Arreglo idéntico: `dissolve().explode()` a piezas de una
  parte antes del overlay y re-dissolve por rodal después. Verificado byte
  a byte contra el piloto. Si algún otro script cruza capas provinciales,
  mirar esto ANTES de lanzarlo.
  Verificado contra la malla del piloto: **263 bloques y las hectáreas
  idénticas al céntimo**. Y de paso corrigió un fallo: el «concello dominante»
  se elegía por el mayor TROZO (núcleos e illadas contaban por separado), no
  por la mayor parroquia — 3 celdas de 263 mal etiquetadas.
- **ESCRITURA ATÓMICA del CHM** (`pipeline_chm.py`): antes se escribía directo
  sobre la ruta final y la reanudación da el bloque por hecho con solo ver el
  fichero. Un corte a mitad de escritura dejaba un TIFF truncado que se
  saltaría **para siempre**, envenenando las métricas en silencio. Ahora
  tmp + `os.replace`. Los 265 CHM previos verificados: 0 corruptos.
- **VIGILAR LA ALIMENTACIÓN.** Medido en esta corrida: **420 s/bloque con
  batería** (CPU a 1.696 de 1.896 MHz) frente a los 120 s enchufado. Son
  15,5 días contra 4,4. `Get-CimInstance Win32_Battery` → `BatteryStatus` 1 es
  descargando, 2 enchufado. La malla va ordenada por hectáreas de faixa, así
  que **una corrida parcial ya es entregable**: 1.200 bloques = 69 % de la
  faixa provincial (1,7 días enchufado); 2.000 = 90 %.
  `procesa_comarca.py` tiene ya **guardia de batería** (para limpio por debajo
  del 20 % sin enchufar, `psutil.sensors_battery()`), hermana de la de disco:
  reanudable, y evita que el portátil se apague de golpe a mitad de corrida.
- Lo que NO escala y se declara: el clasificador de copas de la fase 6 está
  validado solo en A Paradanta, y la tasa de FP necesita validación fresca en
  territorio nuevo (~150 puntos, con el prefiltro de Claude a mitad de carga).

**La cadena de después también acepta `--zona`** (si no, los días de máquina no
producen nada): `descarga_ifn.py`, `metricas_faixas.py`, `especie_faixas.py` y
`ranking_final.py`. Con `paradanta` los ficheros NO cambian de nombre (sufijo
vacío), así que el visor, los dossiers y todo lo existente siguen igual. Cada
uno verificado por no-regresión: `metricas_parroquia.csv` y `ranking_final.csv`
del piloto salen **idénticos** tras el refactor. Los CHM de todas las zonas
comparten carpeta —A Paradanta está DENTRO de Pontevedra—, así que se filtran
por la malla de la zona.

**El aborto por especie sin clasificar hizo su trabajo al salir de la comarca.**
IFN de Pontevedra: 11.472 rodales, 376.664 ha, 101 s; **51 especies, 22 que A
Paradanta no tenía**. Clasificadas literalmente contra la disposición adicional
tercera, y hay tres decisiones que conviene no reabrir a ciegas:

- **`Pinus_pinea` NO está prohibido** (96 ha en la provincia). La lista nombra
  tres pinos —*pinaster*, *sylvestris*, *radiata*— más el pino de Oregón. El
  pino manso no está, y meterlo «porque es un pino» sería inventar norma.
  Igual `Picea_abies`, `Chamaecyparis` y los dos `Cupressus`: coníferas exentas.
- **Todo el género Eucalyptus entra**, incluidas las grafías del IFN:
  `Eucalyptus_viminalis` (104 ha), `E. gomphocephalus`, `Mezcla_de_eucaliptos`
  y **`Eucaliptus_spp`, que el IFN escribe con una sola «p»** — leerla mal la
  dejaría fuera en silencio.
- **`Otras_coníferas` es ambigua de verdad** y se cuenta como prohibida, con el
  mecanismo de `AMBIGUAS` para medir cuánto mueve: puede ser radiata o Oregón
  (prohibidas) o un ciprés (exenta), y el error caro es el falso negativo.
  Medido: las ambiguas mueven **0,1 puntos** en la provincia (71,6 % → 71,5 %),
  así que la decisión no es crítica, pero queda declarada.

Fracción prohibida del IFN provincial: **71,6 %** de la superficie arbolada
(A Paradanta, 68,2 %: la comarca no es atípica en esto).

**La validación en territorio nuevo también está lista** (`muestra_producto.py
--zona --n --semilla`, `chips_producto.py --dir`, `anotador.py --dir`,
`valida_producto.py --dir`). Sortea en la carpeta `validacion_{zona}/`, no en la
del piloto: el HTML del anotador y el CSV descargado tienen que vivir juntos o
se pisan (la trampa de carpetas de siempre). Fuera de A Paradanta no se excluye
ningún bloque —la calibración no vio ninguno, todo es virgen— y `universo()`
filtra por la malla de la zona. No-regresión verificada: `resumen_producto.csv`
del piloto sale **idéntico**.

**Sin esa muestra fresca no se publican cifras provinciales.** La tasa de FP del
33,5 % está medida en A Paradanta; Redondela y Sanxenxo son otro paisaje
(costero, mucho más denso). El plan: ~150 puntos, con el prefiltro de Claude
descartando negativos claros para reducir a la mitad la carga del anotador.

### B — Producto usable

- `puntos_inspeccion.py`: del ranking por parroquia al **sitio donde aparcar**.
  464 puntos en el piloto — 69 eucaliptales seguros (>35 m), 103 rodales IFN
  prohibidos Y persistentes con arbolado real dentro, 292 clusters de disperso
  clasificado. Escribe también `areas_inspeccion.gpkg` con la MANCHA, no solo
  la chincheta.
- **Dos trampas de atribución, las dos cazadas mirando las fichas:**
  - **El punto no puede ser `representative_point()`**: garantiza estar dentro
    del polígono, no dentro del ARBOLADO. Una ficha señalaba una casa con
    piscina en medio del rodal — exactamente la crítica que hundió la
    confianza en el mapa de copas. Ahora `ancla()` devuelve el píxel de
    arbolado medido más cercano al centro de masa: siempre hay árbol debajo.
  - **El concello NO se atribuye por dónde cae el punto.** Al mover el ancla,
    un rodal de 6,94 ha a caballo del límite saltó de Arbo a A Cañiza. Se
    atribuye por **superficie de la mancha** en cada parroquia (argmax de la
    intersección). El dossier es por concello: una atribución inestable manda
    al inspector a la oficina equivocada.
- `visor.py`: un **HTML autocontenido** (2,1 MB, sin servidor ni CORS) con
  ortofoto PNOA de fondo, parroquias coloreadas por punto medio de las cotas y
  los puntos clicables con ficha y coordenadas. GeoJSON incrustado, simplificado
  a 10 m y reproyectado a WGS84.
- `dossier_concello.py`: **PDF por concello** para imprimir y llevar en el
  coche. Portada con resumen, parroquias ordenadas y el marco legal (incluidas
  las excepciones que ningún sensor evalúa); después una ficha por punto con
  recorte de ortofoto **mosaicado entre bloques vecinos** (la cache es de 1×1 km
  exacto y un punto de borde salía medio en negro — la misma trampa de los
  chips de la fase 2), la mancha dibujada, barra de escala y coordenadas en
  UTM29 y lat/lon para el GPS. El encuadre se ajusta a la mancha (200–700 m).

### Estado al 28-08-2026 — LA PROVINCIA ESTÁ MEDIDA; FALTA ANOTAR

**La corrida LiDAR terminó el 27-08 por la noche: 3.197/3.197 bloques, 0
corruptos, ~5 días de máquina.** Windows mató el proceso 3 veces (Application
Hang tras transición de sesión por acelerómetro — mover el portátil; stderr
vacío, sin reinicio); las 3 se curaron relanzando sin perder un dato
(escritura atómica). `scripts/vigila_pontevedra.ps1` queda para corridas
futuras (Claude no puede lanzarlo: clasificador de permisos).

**La cadena completa ya corrió (28-08)**: metricas → especie → ranking →
muestra. Resultado provincial: **38.601 ha de faixa, 12.709 ha de arbolado,
[3.635–7.113] ha prohibidas**. Top concellos: Ponteareas (283–510), A Estrada
(205–462), Salvaterra de Miño (200–333). A Cañiza (1ª del piloto) es 8ª.
Parroquia nº 1: O Hío (Cangas) — costera, fuera del dominio de validación.
En `metricas/ranking_final{,_concello}_pontevedra.csv`.

**Dos bugs de escala cazados en la cadena, arreglados y verificados byte a
byte contra el piloto** (los CSV del piloto salen idénticos):
- Ventana degenerada de rasterio (faixa que roza el borde del bloque con <1
  px de alto): try/except WindowError en `metricas_faixas.py` Y en su gemelo
  de `especie_faixas.py` (sección 4).
- La trampa del overlay disuelto reapareció en `especie_faixas.py` (ver
  arriba, sección de trampas de escala); además el dissolve provincial suelta
  esquirlas línea/punto que overlay rechaza — se filtran (área cero).

**VALIDACIÓN PROVINCIAL HECHA (30-08-2026): las cifras son publicables.**
150 puntos anotados: 134 por el usuario (anotador prefiltrado) + **16
delegados al prefiltro de Claude** («no» claros; propiedad de asimetría
medida en el piloto de la fase 6 — se declara en la publicación, no es
verificable en esta muestra porque el humano no los vio). La fusión la hace
`fusiona_prefiltro.py`: `anotacion.csv` = 150 filas en el orden de la muestra
(los delegados con `ms=0`), la descarga cruda queda en `anotacion_humana.csv`.
**Vivió en el scratchpad hasta el 09-09 y estuvo a punto de perderse**: sin ese
paso la tasa de FP provincial no es reproducible desde los CSV crudos, que es
justo lo que se le exige al resto del proyecto. Reconstruido y verificado —
reproduce `anotacion.csv` byte a byte y `resumen_producto.csv` sin cambiar un
dígito. El orden de filas no es cosmético: los bordes del IC bootstrap dependen
de él. Lleva tres guardias que abortan (el humano invade un delegado, faltan
puntos por anotar, ids ajenos a la muestra).

- **Tasa de FP provincial: 20,1 % [12,8–28,0]** — compatible con la fase 2
  (24,2 %) y MEJOR que la del producto del piloto (33,5 %). Sensibilidad
  90,1 % [83,6–96,5]. Dudosos 12 (8,3 %). **Estrato ≥35 m: 9/9 árbol** — el
  suelo del eucalipto aguanta también en la provincia.
- Concordancia prefiltro-humano en los 134 compartidos: de mis 59 «árbol» el
  humano confirma 45 (76 %); mis 75 «dudoso» se reparten 20 árbol / 39 no /
  8 edif / 8 dudoso. Claude sobre-marca árbol: el lado seguro.
- **Titular provincial FINAL: [4.493 – 8.288] ha prohibidas** (sube desde
  [3.635–7.113] porque la tasa de FP fresca descuenta menos). Orden estable:
  Ponteareas (350–593), A Estrada (253–538), Salvaterra (248–388); O Hío
  (Cangas) 1ª parroquia.
- **Arreglo en `ranking_final.py`**: la ruta del `resumen_producto.csv`
  estaba clavada a `validacion_producto` (piloto) — ahora cada zona lee su
  carpeta (`validacion_{zona}`). Verificado: ranking del piloto idéntico
  byte a byte.
- `anotador_prefiltrado.py` genera el anotador reducido desde
  `claude_prefiltro.csv` (reutiliza la página de `anotador.py`).

Pendiente de propagar: memoria/artifact, visor y dossiers siguen con las
cifras del piloto; decidir si se regeneran con la provincia (visor y
puntos_inspeccion necesitarían generalizarse a `--zona`).

Referencia de la cadena que ya corrió:

```
python scripts/metricas_faixas.py --zona pontevedra
python scripts/especie_faixas.py  --zona pontevedra
python scripts/ranking_final.py   --zona pontevedra
python scripts/muestra_producto.py --zona pontevedra --n 150
python scripts/chips_producto.py   --dir validacion_pontevedra
python scripts/anotador_prefiltrado.py --dir validacion_pontevedra
python scripts/fusiona_prefiltro.py    --dir validacion_pontevedra
python scripts/valida_producto.py      --dir validacion_pontevedra
```

Lo único que NO puede hacer la máquina sola: **anotar los ~150 puntos**. Y sin
esa tasa de FP propia no se publican cifras provinciales (la del 33,5 % es de
A Paradanta, interior; Redondela y Sanxenxo son costa densa).

Lo que NO se traslada a la provincia y hay que declararlo: el clasificador de
copas de la fase 6 y la validación de persistencia están hechos solo en
A Paradanta. El ranking provincial sale de FP × fracción IFN, sin fase 6.

Aún sin hacer, por si sobra tiempo: banda infrarroja del PNOA para rescatar las
dos zonas del este donde el clasificador de copas no valida, y auditoría de los
«exenta» con el prefiltro de Claude.

## Fases 5 y 6 a escala provincial (09/10-09-2026, EN MARCHA)

Decisión del usuario: llevar persistencia y clasificador de copas a Pontevedra,
que en el ranking provincial no estaban (salía de FP × fracción IFN).

**El orden está forzado**: `muestra_copas.py` entrena solo con rodales puros
**y persistentes**, así que la fase 5 va antes que la 6, no en paralelo.

**LA COMPOSICIÓN DE S2 TIENE QUE SER POR TILE.** A Paradanta cabía entera en
29TNG y por eso `compuesta_verano` podía coger las 3 escenas menos nubladas de
todo el bbox. Pontevedra son 8.500 km² (17× el piloto) y **cuatro tiles**:
29TNG, 29TMG, 29TNH, 29TMH. Con el método viejo las tres escenas podían salir
del mismo tile y el compuesto tendría dato en un cuarto de la provincia y NaN
en el resto — **sin avisar, porque un NaN no es un error**: se propaga a la
media del rodal y de ahí al detector. Ahora se compone por tile sobre su
intersección con la zona y las medias por rodal se acumulan como suma y cuenta
de píxeles válidos (un rodal en el solape recibe la media ponderada, que es lo
que se quiere). 29TMG y 29TMH aportan franjas de ~1,7 km en el borde oeste,
sobre la ría, con NDVI ~0: es correcto, la malla MGRS corta ahí.

**La trampa del overlay disuelto apareció en TRES sitios nuevos**, y ya van
seis. Regla: si un script cruza capas provinciales, mirar esto ANTES.
- `descarga_orto25.py`: marcos de bloque contra `union_all()` de las faixas.
- `detecta_eventos.py`: 11.472 rodales contra ese mismo multipolígono.
- `descarga_catastro.py`: peor, evaluándolo celda a celda en un bucle Python
  de ~8.600 iteraciones.
Los tres van ya por `sjoin` pieza a pieza. **Y en `detecta_eventos.py` hay un
matiz que no se puede perder: núcleos e illadas SE SOLAPAN**, así que las áreas
de intersección no se suman — se unen las (pocas) piezas que tocan cada rodal y
se interseca contra esa unión. Sumarlas contaría dos veces la zona común.

**Las carpetas compartidas entre zonas vuelven a morder.** Ya estaba documentado
para los CHM; pasa igual con `copas/` y con `catastro_celdas/`. El agregado
final de `descarga_catastro.py` hacía `glob("*.gpkg")` y habría mezclado las
celdas de Pontevedra en el resultado del piloto. Se filtra por la malla de la
zona, o por la lista de celdas de la zona.

**No concatenar antes de filtrar.** `muestra_copas.py` y `aplica_copas.py`
juntaban las copas de todos los bloques y filtraban después: en la provincia son
**12,9 M de copas**, varios GB para tirar el 90-99 %. Ahora cruzan bloque a
bloque, lo que da **exactamente el mismo orden** porque `sjoin` conserva el del
lado izquierdo (verificado: `entrenamiento.csv` sale idéntico).

Tres fallos pequeños que costaron una corrida cada uno:
- **Un bloque sin arbolado escribía un CSV sin cabecera.** En A Paradanta no
  pasaba; en la provincia hay bloques de mar, roca y suelo urbano. `copas_chm.py`
  reventó al cerrar, con los 2.934 bloques ya hechos. Se declaran las columnas.
- **La columna `bloque` de la malla trae el nombre con extensión `.LAZ`.**
- **`cx` es el indexador de coordenadas de GeoPandas**: una columna llamada así
  no se puede leer como atributo.

Medido en esta corrida: `copas_chm.py` 1,0 s/bloque; `descarga_orto25.py` 16-20
s/bloque y **5 MB/bloque** (los 2.919 pendientes son 14,6 GB y 16 h en serie, o
4 h con `--trozo i/4`, para lo que ya estaba pensado). Catastro: 3.197 celdas de
1 km de las 8.658 de la rejilla. **El disco es el límite real, no el tiempo.**

No-regresión verificada con el piloto en todo lo tocado: `serie_ndvi_rodal.csv`
(658 rodales), `persistencia_ifn.csv` (70 eventos), `edificios_catastro.gpkg`
(263 celdas, 13.452 edificios), `entrenamiento.csv` (24.000 copas) y —con copia
de seguridad, porque pisa ficheros del piloto— `disperso_clasificado.csv` y
`metricas_parroquia_especie_copas.csv` de `aplica_copas.py` salen idénticos,
con sus 8 zonas validadas, sus 589 tejados y su 59,9 %.

### Resultado de la fase 5 en Pontevedra (10-09-2026)

**Persistencia provincial: 98,2 %** del rodal-en-faixa (12.300 de 12.520 ha,
3.363 rodales que tocan faixa). El piloto dio 97,4 %: la comarca no era atípica
y **el IFN 2010 aguanta también en la provincia**. 126 rodales con evento,
219,7 ha. Impacto sobre la etiqueta: 81 rodales a desconocida (142 ha) y 45 de
rebrote de eucalipto (77,7 ha, siguen prohibidos).

**Diagnóstico de deriva limpio** en los dos tiles que importan: 29TNG y 29TNH
entre 0,695 y 0,793, sin escalón en 2022. 29TMG y 29TMH salen a 0,00–0,19
porque son franjas de ~1,7 km sobre la ría: correcto, no es un fallo.

**Los dos picos de eventos reproducen los del piloto, incluido el malo:** 53
rodales en 2018 (cicatrices de los incendios de octubre de 2017, validación
natural) y **21 en 2026, que son la firma de la sequía de agosto** — en el
piloto se midió 0/8 confirmados en ese año. Esas 28,6 ha no son cortas. Igual
que allí, el listado de eventos y el aviso de vigencia (14 rodales post-LiDAR;
en el piloto solo 1 de 13 se confirmó) **no se publican como hecho**: lo que
entra en el ranking es la persistencia.

10.857 de 11.472 rodales con serie (94,6 %).

### Entrenamiento de la fase 6 en Pontevedra

1,85 M de copas dentro de rodal puro persistente, frente a ~150.000 del piloto.
La muestra sigue capada a 8.000 por clase y ahora cubre **135 zonas de
eucalipto, 110 de frondosa y 162 de pino** (piloto: 18, 14 y 19), sobre
427/304/696 rodales.

**Decisión pendiente: `CAP` sigue en 8.000.** Con el pool 12 veces mayor, esas
8.000 copas por clase se reparten ahora entre cientos de zonas —unas 60 por
zona, frente a 444 en el piloto—. Más diversidad y más grupos para el
GroupKFold, pero menos densidad por zona. Se mantiene el valor validado en esta
pasada a propósito; si el AUC provincial se queda corto, subirlo es lo primero
que probar, y entonces hay que revalidar.

### Estado de la fase 6 provincial al 10-09-2026

Hecho: copas (12,87 M en 3.197 bloques), ortofoto a 0,25 m (3.197 bloques,
14 GB), parches (23.211 de 64x64, 789 descartados por borde negro), embeddings
MobileNetV3 (140 s en CPU) y entrenamiento.

**AUC eucalipto 0,866 OOS**, sobre el listón de 0,85 y sobre el 0,860 del
piloto. **Pero la inestabilidad por zonas no desaparece con la escala, se
confirma**: de 106 zonas con las dos clases, 60 pasan de 0,80 (57 %), mediana
0,820, y las peores caen a 0,04-0,37. Entre ellas está **113_933, que es una de
las dos que el piloto ya tenía diagnosticadas** como ortofoto de otra pasada,
oscura y con el contraste aplastado. El criterio de integración (aplicar solo
donde AUC ≥ 0,80) sigue siendo el correcto y `aplica_copas.py` ya lo aplica.

**PENDIENTE: el Catastro provincial.** 667 de 3.197 celdas. El WFS
(`ovc.catastro.meh.es`) empezó a 3,6 s/celda con dos procesos, se degradó a
42,7 y acabó devolviendo `HTTPError` sostenido incluso con uno solo: es
limitación por IP, no saturación puntual, y no se levantó en media hora. **No
insistir**: retomarlo más tarde con un único proceso. Sin él no corre
`aplica_copas.py --zona pontevedra`, que es el último paso.

Los cuatro fallos de la noche tienen la misma forma y conviene recordarla: **el
trabajo terminaba bien y el proceso moría en la contabilidad**. El recuento
final de `copas_chm.py`, un timeout que no debía ser fatal en
`descarga_catastro.py`, un contador de MB que hacía `stat` sobre los ficheros
temporales de los otros procesos en `descarga_orto25.py`, y un `print` con la
ruta sin sufijo en `entrena_copas.py`. Los caminos de éxito escalaron de 263 a
3.197 bloques; los de error, no.

## Cuestiones abiertas

- **Umbral de altura** para considerar "arbolado". Sin fijar. La maquinaria de
  calibración está lista; falta anotar los 400 puntos y correr `calibra_umbral.py`.
  Cuando exista `validacion/calibracion_resumen.csv`, `metricas_faixas.py` lo usa solo.
- **Clasificación de especie — prioridad subida a casi necesaria.** La disposición
  adicional tercera de la Ley 3/2007 lista 7 especies arbóreas (pinos, eucalipto,
  acacias) y su punto 3 **exime expresamente a las frondosas no listadas**: castaños y
  robles pueden estar dentro de la franja legalmente. Por tanto "arbolado sobre umbral"
  no es un indicador de incumplimiento, sino un proxy sesgado allá donde haya frondosa
  autóctona. Basta separar perennifolias de la lista frente a caducifolias — no hace
  falta identificar especie —, así que probar primero la banda infrarroja del propio
  PNOA (RGBI) y luego estacionalidad con Sentinel-2. Si no da tiempo, declarar el sesgo
  en portada, no en nota al pie. Detalle en `docs/03-marco-legal.md`.
- **Segmentación de copa individual** a 5 pts/m²: viabilidad por confirmar. Pendiente
  consulta al grupo SILVANET (UPM), que trabaja en cartografía de combustibles y
  análisis estructural de vegetación con LiDAR.

## Prioridades

1. ~~Desbloquear las geometrías~~ **hecho**: shapefile del PBA, verificado. En
   `datos/procesado/faixas_{nucleos,illadas}_paradanta_ok.gpkg`.
2. ~~Descargar bloques LiDAR y comprobar tiempos y volumen reales~~ **hecho**: 3 bloques,
   22 MB/s de descarga, 170 s/bloque de proceso.
3. ~~Prototipo del pipeline de extremo a extremo~~ **hecho**: CSV en
   `datos/procesado/metricas/`, MDT contrastado contra NPC01 (mediana +5 cm, σ 26 cm).
4. ~~Fase 2: calibrar el umbral~~ **hecho**: 5,5 m, tasa de FP 24,2 %, y la
   concordancia intra-anotador medida y publicada.
5. ~~Fase 3: verdad de referencia de especie~~ **hecha** (18-08-2026): el **IFN4 2010**
   del IDE de la Xunta. El MFE25 del MITECO es la fuente canónica pero su WMS devuelve
   `NullReferenceException` y sus descargas se pintan con JS; la Xunta sirve lo mismo
   por ArcGIS REST, **con geometrías y en EPSG:25829**. Ver `descarga_ifn.py`.
6. ~~Sentinel-2 multitemporal~~ **montado, SIN VALIDAR** (18-08-2026). Ver abajo.
7. ~~Fase 4: escalar a los 263 bloques~~ **hecha** (20-08-2026, `procesa_comarca.py`):
   streaming descarga→CHM→borrado por el límite de disco, 0 fallos, mediana 120 s/bloque
   enchufado (~480 s con batería: vigilar), 2.848 ha medidas (99,9 %), 41,0 % sobre
   5,5 m, 16,2 ha sobre 35 m (eucaliptal seguro; columna `ha_sobre_35m` nueva).
   La validación de la fenología S2 con la comarca entera es lo siguiente.

8. **Entregable montado y validado fuera de muestra** (19-08-2026,
   `ranking_final.py` + `valida_producto.py`): 2.848 ha de franja medidas, 1.167 ha
   de arbolado, **[353–574] ha prohibidas** (302→297 con los reemplazos
   confirmados; 353–574 con el clasificador de copas de la fase 6 en zonas
   validadas). Compone FP × fracción IFN (disperso a
   las cotas) con suelo de 35 m, ordena por punto medio. A Cañiza primera por
   concello, Valeixe (Santa Cristina) por parroquia. La validación del producto
   (250 puntos frescos, 127 bloques) dio **FP 33,5 % [25,2–41,8]** — compatible
   pero desplazada sobre el 24,2 % de la fase 2 — y `ranking_final.py` usa la tasa
   fuera de muestra automáticamente si existe `resumen_producto.csv`. Sensibilidad
   89,8 % y suelo del eucalipto (14/15) aguantan.

**Trampa del `anotacion.csv` (19-08-2026, casi pérdida de datos):** el
`validacion/anotacion.csv` final de la fase 2 NO es `anotacion_pase1.csv`: es
pase1 + las respuestas del retest pegadas encima de sus 126 puntos (13 cambian de
clase). Se reconstruyó y verificó contra `calibracion_resumen.csv` (estimadores
puntuales exactos; los bordes del IC bootstrap dependen del orden de filas). Si se
vuelve a pisar, esa es la receta. Y al anotar: el HTML de cada muestra vive en SU
carpeta (`validacion/`, `validacion_producto/`) y el CSV descargado va a ESA
carpeta, no a la otra.

Sigue en pie: no optimizar. La escala ya está medida y cabe de sobra en el plazo.
