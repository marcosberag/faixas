# faixas

Estimación, a partir de datos públicos, de qué franjas de protección contra incendios en
Galicia tienen arbolado que la ley no permite.

En Galicia la [Ley 3/2007](https://www.boe.es/buscar/act.php?id=BOE-A-2007-10022) obliga
a mantener una franja de 50 m alrededor de cada núcleo de población y cada vivienda sin
determinadas especies arbóreas. La Xunta publica el mapa de **dónde** existe esa
obligación. No existe el mapa de **dónde se cumple**: hoy se verifica mandando
inspectores a pie, parcela por parcela.

Este proyecto intenta estimar el segundo cruzando la capa oficial de franjas con el
LiDAR del PNOA, para que la inspección pueda priorizar.

**Es una herramienta de triaje, no una lista de infractores.** La propia ley admite
excepciones que el LiDAR no puede evaluar, y exime a las frondosas no listadas.

---

## Documentación

| Documento | Para qué |
|---|---|
| [00 — Qué es esto](docs/00-que-es-esto.md) | El problema, qué es el LiDAR y qué significa cada sigla. **Empieza aquí.** |
| [01 — Plan de trabajo](docs/01-plan-de-trabajo.md) | Fases, riesgos, decisiones cerradas y cuestiones abiertas. |
| [02 — Walkthrough](docs/02-walkthrough.md) | Estado real del código, cómo reproducirlo y las trampas encontradas. |
| [03 — Marco legal](docs/03-marco-legal.md) | Qué obliga exactamente la ley, verificado contra el texto consolidado. |

`CLAUDE.md` es el contexto de trabajo para sesiones con Claude Code.

---

## Estado

**Fase 0 completada.** Las geometrías están descargadas, reparadas y verificadas: 49
polígonos de núcleos y 52 de edificaciones aisladas en la zona piloto (2.240 ha + 609 ha),
en EPSG:25829, contrastados contra el servicio oficial de la Xunta con **IoU 0,9996**.

**Fase 1 completada.** El pipeline funciona de extremo a extremo sobre tres bloques de
1×1 km, en tres concellos distintos: descarga del CNIG → SMRF → MDT / MDS → CHM a 1 m →
recorte por franja → CSV.

| | medido |
|---|---|
| Descarga | 22 MB/s. 331 MB de LAZ en 15 s |
| Proceso | **170 s por bloque** (i5-8350U, 16 GB) |
| Comarca completa, estimada | ~28 GB y **12,4 h en serie**; una noche en paralelo |
| MDT contra la clasificación NPC01 | mediana +0,05 a +0,08 m, σ 0,26 m |
| Control de rasterización | −0,04 % |

Sobre las 104 ha de franja cubiertas, el 35,9 % tiene vegetación por encima del umbral
calibrado. **Ese número no es incumplimiento**: la ley exime a las frondosas no listadas
y casi la mitad del arbolado detectado lo es. Detalle y avisos en el
[walkthrough](docs/02-walkthrough.md#9-métricas-y-tres-avisos-sobre-cómo-leerlas).

**Fase 2 completada.** 400 puntos fotointerpretados a ciegas contra ortofoto, con
muestreo estratificado por altura y ponderación por superficie.

| | |
|---|---|
| **Umbral calibrado** | **5,5 m** a 1 m de píxel (no transferible a otra resolución) |
| Sensibilidad | 89,4 % — IC95 [81,4 – 96,6] |
| **Tasa de falsos positivos** | **24,2 %** — IC95 [17,0 – 31,2] |
| AUC | 0,916 |
| Dudosos declarados y excluidos | 12,4 % de la superficie |
| Concordancia intra-anotador | kappa 0,88 en casos claros, **0,53 en la zona de decisión** |
| Umbral bajo una dosis extra de error de anotación | 5,5 m — a ±1 m en el 98 % de las réplicas |

La fiabilidad del fotointérprete está medida y propagada, no supuesta: el acuerdo
consigo mismo es del 94 % por debajo de 2 m y del 91 % en la zona de decisión de 2–8 m,
y reinyectando ese error en la muestra el umbral no se mueve. El error de anotación
**sube** la tasa de falsos positivos —el desacuerdo se le apunta siempre al CHM—, así
que **el 24,2 % es un techo**, no una cifra optimista.

Y una medición independiente del CHM: por fotointerpretación, **el 27,7 % de la franja
tiene arbolado**. El CHM a 5,5 m marca 35,9 %. Esa diferencia *es* la tasa de falsos
positivos, medida por otro camino.

**Sobre el sesgo de especie, un resultado negativo:** la subpregunta de tipo de copa
solo pudo contestarse en 25 de los 87 árboles, y en 15 de ellos la respuesta fue «no
distinguible». **La especie no se puede tipificar por fotointerpretación sobre
ortofoto a esta escala.** La fase 3 necesitó una verdad de referencia que no viniera
del ojo.

**Fase 3 en marcha.** Cruce con el Inventario Forestal Nacional (IFN4, 2010), que la
Xunta publica como servicio ArcGIS REST en EPSG:25829. Cada rodal se clasifica contra
la disposición adicional tercera **especie a especie** —agrupar por género o por
«perennifolia contra caducifolia» da la respuesta equivocada en los dos sentidos— y la
ocupación se aplica como factor continuo, porque 412 de los 658 rodales son mixtos.

| | Prohibida | Exenta |
|---|---|---|
| Monte de la comarca | 68,2 % | 31,8 % |
| Dentro de la faixa | 66,9 % | 33,1 % |

**Entre el 44 % y el 72 % del arbolado detectado en faixa es especie prohibida.** El
rango existe porque el IFN cartografía monte, no árboles sueltos: el 38,7 % del
arbolado en faixa es disperso y su composición no está medida (aunque 8 de los 10
puntos que se anotaron «frondosa» caen justo ahí).

Y lo que justifica la fase: **tres de cada cinco parroquias cambian de puesto** al
corregir, con una correlación de Spearman de 0,70 entre los dos órdenes. As Achas pasa
de 19,3 % de faixa arbolada a 2,7 % de faixa con arbolado prohibido. El ranking sin
corregir manda al inspector al sitio equivocado.

**Sentinel-2 estacional: montado y sin validar.** Se comprobó primero que el atajo era
legítimo —el proxy perennifolia/caducifolia reproduce el corte legal con **99,37 %** de
acuerdo aquí, aunque no valdría en un alcornocal— y la señal sale inequívoca: *Quercus
robur* pierde 0,257 de NDVI del verano al invierno, *Pinus pinaster* 0,009 y
*Eucalyptus globulus* −0,033.

Con la comarca entera la validación se pudo hacer por fin — dejando fuera zonas de
5×5 km cada vez — y **no valida**: AUC 0,746 fuera de muestra, acierto 65,8 %, y una
precisión del 45,8 % al declarar «caducifolia exenta». Peor aún, el rendimiento por
zonas oscila entre AUC 0,93 y 0,30, así que no hay corrección estadística posible.
**El clasificador por píxel no entra en el producto** y se publica como resultado
negativo medido: parte del desacuerdo puede deberse a que la referencia (IFN) es de
2010, pero un método que no se puede validar no se usa. La especie queda acotada por
el IFN como fracción continua y por la regla estructural de los 35 m.

De paso quedó medido que la **mezcla dentro del píxel de 10 m** es el límite duro: solo
el 67,9 % del arbolado en faixa cae en píxeles suficientemente puros para clasificar.

**Fase 4 completada.** Los 263 bloques de la comarca, procesados en streaming
(descargar → CHM → borrar el LAZ, que el disco no admite 27 GB de crudo) con
`scripts/procesa_comarca.py`: **cero fallos**, 22,8 GB descargados, mediana de
120 s por bloque y 10,4 h de cómputo total en un i5-8350U.

| | medido |
|---|---|
| Cobertura | **2.848 ha de franja, el 99,9 % de la comarca** |
| Control de rasterización | −0,05 % |
| Arbolado sobre el umbral calibrado (5,5 m) | **1.167 ha, el 41,0 %** |
| Sobre 35 m (eucaliptal maduro seguro) | 16,2 ha |

**El entregable** (`scripts/ranking_final.py`) compone las piezas validadas — y solo
esas — en el ranking de parroquias y concellos por franja con arbolado prohibido:

> De las 2.848 ha de franja medidas, 1.167 ha tienen arbolado, y **entre 353 y
> 574 ha son de especie prohibida**. A Cañiza encabeza por concello (148–239 ha)
> y Valeixe (Santa Cristina) por parroquia (40–59 ha).

Las cotas componen la tasa de falsos positivos del CHM (con su IC95), la fracción
prohibida del IFN (con el arbolado disperso llevado a las cotas, no etiquetado) y
el suelo de los 35 m. El orden es para priorizar inspección; los números **no son
superficie de infracción**.

**Validación del producto, fuera de muestra.** 250 puntos frescos fotointerpretados
a ciegas en 127 de los 260 bloques que la calibración nunca vio:

| | fase 2 (3 bloques) | producto (260 bloques) |
|---|---|---|
| Tasa de falsos positivos | 24,2 % [17,0–31,2] | **33,5 % [25,2–41,8]** |
| Sensibilidad | 89,4 % | 89,8 % |
| Puntos >35 m que son árbol | — | 14 de 15 (1 dudoso) |

La sensibilidad y el suelo del eucalipto aguantan; la tasa de FP sale compatible
pero desplazada al alza, y **el ranking usa la tasa nueva** — está medida en el
dominio donde el producto se aplica, y pecar de pesimista es el criterio de la
casa. Medición independiente: por fotointerpretación el 28,6 % de la franja tiene
arbolado; el CHM marca 41,0 %, y esa diferencia es coherente con la tasa de FP.

**Fase 7 completada: la provincia de Pontevedra entera, medida y validada.**
3.197 bloques (12,2 × el piloto) en ~5 días de máquina desatendida, 0 CHM
corruptos, y validación fresca fuera de muestra en el territorio nuevo:

| | medido |
|---|---|
| Cobertura | **38.601 ha de franja — la provincia entera, 60 concellos** |
| Arbolado sobre 5,5 m | 12.709 ha (32,9 %) |
| **Especie prohibida (cotas)** | **[4.493 – 8.288] ha** |
| Tasa de FP provincial (150 puntos frescos) | **20,1 % [12,8–28,0]** |
| Sensibilidad | 90,1 % [83,6–96,5] |
| Puntos ≥35 m que son árbol | **9 de 9** |

Encabezan Ponteareas (350–593 ha), A Estrada (253–538) y Salvaterra de Miño
(248–388). A Cañiza, primera del piloto, queda octava. De los 150 puntos de
validación, 16 negativos claros se delegaron al prefiltro de Claude (con la
asimetría medida en el piloto y declarada como límite). Detalle, comandos y
las dos trampas de escala en la [fase 7](#del-piloto-al-producto-fase-7).

## Zona piloto

A Paradanta (Pontevedra): Arbo, A Cañiza, Covelo, Crecente. 18,5 × 23,9 km, 2.850 ha de
franja, 40 parroquias.

Comarca completa —los cuatro concellos tienen plan aprobado y capa publicada— y más
exigente que la media gallega: el poblamiento disperso multiplica por tres a cinco la
mediana de Galicia y los polígonos son un 31 % más pequeños. Es el 1,70 % de la franja
gallega, así que **sirve para calibrar el método, no para extrapolar tasas de error al
resto de la comunidad**. Justificación completa en
[el plan de trabajo](docs/01-plan-de-trabajo.md#por-qué-galicia-y-por-qué-a-paradanta).

## Uso

```bash
pip install requests pillow numpy scipy matplotlib geopandas pyogrio rasterio "laspy[lazrs]"
```

PDAL va aparte, en un entorno conda propio: en Windows no hay wheel de `pip`. Con
[micromamba](https://mamba.readthedocs.io), que es un solo ejecutable de 11 MB:

```powershell
& "$HOME\.local\bin\micromamba.exe" create -y -p "$HOME\.local\micromamba\envs\pdal" -c conda-forge pdal gdal
```

### Las franjas

Descargar los shapefiles (PowerShell, por el TLS incompleto del servidor):

```powershell
$b="https://visorgis.cmati.xunta.es/cdix/descargas/faixas_xestion_biomasa"; foreach($f in @("FaixaProteccion50m.zip","FaixaProteccion50m_Illadas.zip")){Invoke-WebRequest "$b/$f" -OutFile "datos/crudo/$f" -UseBasicParsing}
```

Y procesarlos:

```bash
python scripts/carga_faixas.py
python scripts/repara_faixas.py
python scripts/verifica_faixas.py
```

### El LiDAR

```bash
python scripts/malla_lidar.py       # qué bloques de 1 km tocan franja
python scripts/descarga_lidar.py    # los baja del CNIG y cronometra
python scripts/pipeline_chm.py      # SMRF -> MDT / MDS / CHM
python scripts/verifica_chm.py      # contraste con NPC01 + panel visual
python scripts/metricas_faixas.py   # recorte por franja y CSV
```

Para la comarca entera (fase 4) hay un orquestador que descarga, procesa y
**borra cada LAZ** antes de pasar al siguiente — los 263 bloques son ~27 GB de
crudo y no hace falta conservarlo, los rásteres finales son ~2 GB. Es reanudable
(salta lo que ya tiene CHM) y un bloque que falle no tumba la corrida:

```bash
python scripts/procesa_comarca.py
```

### La validación (fase 2)

```bash
python scripts/muestra_validacion.py    # 400 puntos estratificados por altura
python scripts/chips_validacion.py      # ortofoto del IGN + un chip por punto
python scripts/anotador.py              # monta el HTML de fotointerpretación
python scripts/chuleta_especie.py       # hoja de referencia de tipo de copa
```

La subpregunta de tipo de copa es **opcional**: no entra en el umbral ni en la tasa
de falsos positivos. Si estorba, `python scripts/anotador.py --sin-tipo` la quita y
quedan solo las cuatro categorías principales.

Abrir `datos/procesado/validacion/anotador.html` con doble clic y anotar con el teclado
(`1` árbol, `2` no árbol, `3` edificación, `4` dudoso; `z` aleja a 120 m para ver el
contexto). Los chips llevan **rejilla de 10 m** dibujada y la mira mide **3 m de
diámetro**: sin esa referencia no se distingue un pino joven de una mata de tojo. El
progreso se guarda solo. Al terminar, descargar el CSV a esa misma carpeta como
`anotacion.csv` y:

```bash
python scripts/calibra_umbral.py        # umbral, tasa de FP con IC, curva ROC
python scripts/revisa_discrepancias.py  # hojas de contacto de los desacuerdos
python scripts/metricas_faixas.py       # recalcula ya con el umbral calibrado
```

Y para saber cuánto de todo esto depende del ojo de quien anotó — segunda pasada a
ciegas y propagación del error medido hasta el umbral y la tasa de FP:

```bash
python scripts/retest_validacion.py
python scripts/retest_validacion.py --compara
python scripts/fiabilidad_anotador.py
```

### La especie (fase 3)

```bash
python scripts/descarga_ifn.py     # IFN4 2010 del IDE de la Xunta, en EPSG:25829
python scripts/especie_faixas.py   # clasifica contra la ley y corrige el ranking
python scripts/descarga_s2.py      # NDVI de invierno y verano (COG de AWS, sin registro)
python scripts/fenologia_especie.py  # caída estacional. OJO: aún sin validar
```

### Validar el producto final (fase 4)

Muestra fresca de los 260 bloques que la fase 2 no vio, sin pregunta de especie
(quedó medido que la especie no se tipifica a ojo). Se comprueba que la tasa de
FP calibrada aguanta fuera de muestra, y que los puntos >35 m son árboles:

```bash
python scripts/muestra_producto.py     # 250 puntos, sin los bloques del piloto
python scripts/chips_producto.py       # chips por punto contra el WMS (reanudable)
python scripts/anotador.py --sin-tipo --dir validacion_producto
python scripts/valida_producto.py      # tras anotar: FP fuera de muestra vs 24,2 %
```

El anotador tiene pruebas propias, que no necesitan navegador:

```bash
node scripts/test_anotador.js
```

### Persistencia y vigilancia (fase 5, validada)

Los árboles no cambian de especie: si un rodal del IFN 2010 no ha sufrido un
evento de reemplazo (corta, incendio, plantación), su etiqueta vale hoy. El
detector encontró, sin saber que existieron, las cicatrices de los incendios
de octubre de 2017. La validación contra el PNOA histórico partió el resultado
en dos: **la persistencia aguanta** (falsos negativos 3,8 %, titular del 97,4 %
acotado en [81–99 %]) y **el listado de eventos no** (39 % de precisión, con la
sequía de 2026 fabricando espejismos que ni la densidad ni la magnitud de la
caída separan — y la regla de los dos veranos, medida retroactivamente, también
rechazada: la corta rebota en un año, el incendio persiste). Del detector nada
entra en el ranking; los 22 reemplazos **confirmados por el ojo** sí: el rodal
no-eucalipto reemplazado pasa a especie desconocida y la cota inferior baja de
302 a 297 ha.

```bash
python scripts/serie_s2_anual.py         # NDVI de cada verano 2017-2026, por rodal
python scripts/detecta_eventos.py        # eventos de dosel; 97,4 % persistente en faixa
python scripts/muestra_persistencia.py   # 65 rodales: eventos + persistentes, barajados
python scripts/hojas_persistencia.py     # hojas de contacto PNOA 2010-2023 + S2 (reanudable)
python scripts/anotador_persistencia.py  # anotador ciego: ¿reemplazo? ¿en qué intervalo?
python scripts/valida_persistencia.py    # tras anotar: precisión y falsos negativos
python scripts/regla_dos_veranos.py      # regla de caída sostenida: medida y rechazada
python scripts/verdades_en_ranking.py    # los reemplazos confirmados corrigen el ranking
```

### Especie por copa (fase 6, integrada por zonas)

Del píxel a la copa: 1,18 M de copas segmentadas sobre el CHM, 24.000
etiquetadas gratis con rodales puros y persistentes del IFN, y un clasificador
eucalipto/pino/frondosa (rasgos de textura + embedding CNN) con **AUC 0,86
dejando zonas de 5×5 km fuera**. Se aplica **solo en las zonas donde valida**
(AUC ≥ 0,80; el 45 % del arbolado disperso): ahí la fracción prohibida del
disperso pasa de cota ciega [0–72 %] a **54–58 % medida**, y el titular se
estrecha de [297–588] a **[353–574] ha**. En las dos zonas del este la ortofoto
es de otra pasada (oscura, sin contraste) y el clasificador no valida: cota
ancha y a otra cosa.

```bash
python scripts/copas_chm.py          # segmentacion de copas (watershed, 263 bloques)
python scripts/descarga_orto25.py    # cache de ortofoto 0,25 m (--trozo i/n paraleliza)
python scripts/muestra_copas.py      # 24k copas etiquetadas con el IFN persistente
python scripts/parches_copas.py      # parche de 16x16 m por copa
python scripts/embeddings_copas.py   # embedding MobileNetV3 (CPU)
python scripts/entrena_copas.py --cnn  # entrena y valida fuera de zona
python scripts/aplica_copas.py       # clasifica el disperso y ajusta las cotas
python scripts/ranking_final.py      # ranking con todo integrado
```

### Del piloto al producto (fase 7)

Dos cosas a la vez: **escalar** a la provincia y **hacerlo usable**.

```bash
python scripts/prepara_provincia.py --provincia Pontevedra   # recorta y repara las faixas
python scripts/malla_lidar.py --zona pontevedra              # 3.197 bloques, 4 min
python scripts/descarga_ifn.py --zona pontevedra             # 11.472 rodales, 101 s
python scripts/procesa_comarca.py --malla datos/procesado/malla_lidar_pontevedra.csv
# y cuando haya CHM:
python scripts/metricas_faixas.py  --zona pontevedra
python scripts/especie_faixas.py   --zona pontevedra
python scripts/ranking_final.py    --zona pontevedra
```

Con `--zona paradanta` (el valor por defecto) los ficheros no cambian de nombre,
así que nada de lo ya construido se mueve: verificado por no-regresión, el
`metricas_parroquia.csv` y el `ranking_final.csv` del piloto salen idénticos.

Al salir de la comarca, el aborto por especie sin clasificar de
`especie_faixas.py` saltó con **22 especies nuevas**. Tres decisiones que no hay
que reabrir a la ligera: *Pinus pinea* **no** está en la lista legal (ni las
piceas ni los cipreses), todo el género *Eucalyptus* sí —incluida la grafía
`Eucaliptus_spp` con una sola «p» que usa el IFN—, y `Otras_coníferas` se cuenta
como prohibida por prudencia, con el mecanismo de ambiguas para medir cuánto
mueve (0,1 puntos).

Y la validación en territorio nuevo, que es **condición para publicar cifras**
provinciales (la tasa de error está medida en A Paradanta, no en la costa):

```bash
python scripts/muestra_producto.py --zona pontevedra --n 150
python scripts/chips_producto.py --dir validacion_pontevedra
python scripts/anotador.py --dir validacion_pontevedra --sin-tipo
python scripts/valida_producto.py --dir validacion_pontevedra
```

El shapefile del PBA cubre **Galicia entera**, así que escalar no exige datos
nuevos. Pontevedra son 38.601 ha de franja y 3.197 bloques: **~5 días** de
máquina desatendida... **enchufada**. Con batería la CPU baja a 1,7 GHz y el
bloque pasa de 120 a 420 s — 15,5 días. La malla va ordenada por superficie de
franja, así que una corrida parcial ya es coherente: 1.200 bloques cubren el
69 % de la franja provincial.

**Resultado (30-08-2026), con la corrida completa y la validación fresca:**
la provincia entera son **38.601 ha de franja medidas, 12.709 ha de arbolado
y [4.493 – 8.288] ha de especie prohibida**, en 60 concellos. Encabezan
Ponteareas (350–593 ha), A Estrada (253–538) y Salvaterra de Miño (248–388);
A Cañiza, primera del piloto, queda octava — el interior de A Paradanta ni
siquiera era el peor sitio. La validación fuera de muestra (150 puntos
frescos, 140 bloques, anotación ciega) dio **tasa de FP del 20,1 %
[12,8–28,0]** y sensibilidad del 90,1 % — compatible con la fase 2 y mejor
que la del piloto (33,5 %): el paisaje costero denso no rompió el producto.
El estrato ≥ 35 m salió **9/9 árbol**. De los 150 puntos, 16 negativos claros
se delegaron al prefiltro de Claude (asimetría medida en el piloto: cero
árboles humanos entre sus «no»; en esta muestra no es verificable y se
declara). El ranking provincial sale de FP × fracción IFN con suelo de 35 m
— el clasificador de copas de la fase 6 y la persistencia siguen validados
solo en A Paradanta y no se trasladan.

Dos trampas de escala aparecieron al pasar de 263 a 3.197 bloques, las dos
con la misma moraleja: `gpd.overlay` contra un multipolígono provincial
disuelto anula el índice espacial (horas de CPU; se trocea en piezas de una
parte y se recompone), y una faixa que roza el borde de un bloque con menos
de un píxel hace reventar la ventana de rasterio (se salta: el bloque vecino
la mide entera). Cada arreglo, verificado con los CSV del piloto byte a byte.

```bash
python scripts/puntos_inspeccion.py   # 464 sitios concretos + la mancha de cada uno
python scripts/visor.py               # salidas/visor/index.html, autocontenido
python scripts/dossier_concello.py    # un PDF por concello, listo para imprimir
```

Los puntos se anclan en **arbolado medido** (nunca en el centro geométrico del
rodal, que cae en cualquier claro o tejado) y se atribuyen al concello **por
superficie de la mancha**, no por dónde cae el punto.

## Fuentes

- **Franjas de protección** — Xunta de Galicia, servicio ArcGIS REST de la IDEG.
  El servicio no devuelve geometrías: se descargan del visor del PBA.
- **LiDAR y ortofoto (actual e histórica)** — PNOA, IGN/CNIG. CC BY 4.0:
  **la atribución es obligatoria** en cualquier imagen publicada.
- **IFN4 2010, especies arbóreas** — IDE de la Xunta de Galicia.
- **Sentinel-2** — Copernicus, vía el STAC de Element84 sobre los COG de AWS.
- **Huellas de edificios** — Dirección General del Catastro, WFS INSPIRE.

Ortofoto de la zona piloto: vuelo de septiembre de 2023, 0,15 m de resolución.
Vuelo LiDAR: junio–julio de 2024. Hay un año de desfase entre ambos.

## Licencia

- **Código** (`scripts/`): [Apache-2.0](LICENSE).
- **Datos generados, anotaciones y figuras**: [CC BY 4.0](LICENSE-DATOS.md).

Copyright 2026 Marcos Bermejo Agenjo. La cadena de atribución de las fuentes de
entrada y las obligaciones de cada una están en [`LICENSE-DATOS.md`](LICENSE-DATOS.md).

Las ~900 anotaciones de `datos/procesado/validacion*/` son obra original, no
derivan de ninguna fuente pública, y son lo que permite publicar una tasa de
falsos positivos medida en lugar de una estimación sin garantía.

**Uso previsto:** indicador de riesgo para priorizar inspección, no determinación
de incumplimiento. La Ley 3/2007 contempla excepciones que ningún sensor evalúa.

## Reproducir

```bash
pip install -r requirements.txt
micromamba create -f environment-pdal.yml   # PDAL no tiene wheel en Windows
```

El repositorio versiona el código, la documentación, las anotaciones de
validación y las métricas. **No versiona los derivados pesados** —los 3.197 CHM
(~28 GB), los chips, las escenas de Sentinel-2 y los geopaquetes— porque los
regeneran los propios scripts de descarga. Ver [`.gitignore`](.gitignore).

## Financiación

Mini-beca privada (X. Mihura), aproximadamente un mes de trabajo. El único
compromiso adquirido es publicar el resultado en abierto y de forma reproducible.
