# faixas

Estimación, a partir de datos públicos, de qué franjas de protección contra incendios en
Galicia tienen arbolado que la ley no permite.

En Galicia la [Ley 3/2007](https://www.boe.es/buscar/act.php?id=BOE-A-2007-10022) obliga
a mantener una franja de 50 m alrededor de cada núcleo de población y cada vivienda sin
determinadas especies arbóreas. La Xunta publica el mapa de **dónde** existe esa
obligación. Este proyecto estima dónde priorizar su comprobación mediante
inspección presencial.

Para ello cruza la capa oficial de franjas con el LiDAR del PNOA y las fuentes
de especie descritas a continuación.

**Es una herramienta de triaje, no una lista de infractores.** La propia ley admite
excepciones que el LiDAR no puede evaluar, y exime a las frondosas no listadas.

---

## Resultado

**La provincia de Pontevedra, entera.** 3.197 bloques LiDAR de 1×1 km procesados en un
portátil de ocho años, con datos que cuestan 0 €.

| | |
|---|---|
| Franja de protección medida | **38.601 ha**, en 54 concellos (todos los de la provincia con franja publicada) |
| Con arbolado (umbral calibrado, 5,5 m) | 12.709 ha |
| Con arbolado de especie prohibida | **[4.770 – 8.141] ha** |
| Tasa de falsos positivos, fuera de muestra | **20,1 %**, IC95 [12,8 – 28,0] |
| Sensibilidad | 90,1 % [83,6 – 96,5] |

Encabezan Ponteareas (371–586 ha), A Estrada (280–550) y Salvaterra de Miño (248–395).

El rango incorpora el clasificador de especie por copa allí donde valida fuera de zona
(45 zonas de 5×5 km, el 24 % del arbolado disperso de la provincia): sin él sería
[4.493 – 8.515] ha. Corre sin el filtro de tejados del Catastro, que en el piloto movía
la fracción del disperso 0,3 puntos, en dirección conocida (al alza); se declara. La
cota alta del arbolado disperso sale de la muestra anotada de la propia provincia
(78,0 % prohibido donde hay rodal), no de la del piloto (72,2 %).

El rango combina el error de detección del CHM, la composición del IFN, supuestos
sobre el arbolado disperso y la corrección del clasificador de especie. **No es un
intervalo de confianza conjunto del 95 % ni recoge toda la incertidumbre.** La
validación provincial usa 150 puntos: 134 anotados por el humano y 16 negativos
delegados al prefiltro de IA, sin comprobación humana independiente. Detalle en
[Del piloto al producto](#del-piloto-al-producto-fase-7).

También se publican los métodos que **no** funcionaron, con los números por los que se
descartaron: un clasificador de especie con Sentinel-2 (AUC 0,746 fuera de muestra, y
entre 0,30 y 0,93 según la zona) y una regla temporal para detectar cortas (la corta
gallega rebrota en un año, así que la regla pierde 12 de cada 16 eventos reales).

---

## Documentación

| Documento | Para qué |
|---|---|
| [00 — Qué es esto](docs/00-que-es-esto.md) | El problema, qué es el LiDAR y qué significa cada sigla. **Empieza aquí.** |
| [01 — Plan de trabajo](docs/01-plan-de-trabajo.md) | Fases, riesgos, decisiones cerradas y cuestiones abiertas. |
| [02 — Walkthrough](docs/02-walkthrough.md) | Estado real del código, cómo reproducirlo y las trampas encontradas. |
| [03 — Marco legal](docs/03-marco-legal.md) | Qué obliga exactamente la ley, verificado contra el texto consolidado. |
| [Memoria](salidas/memoria.html) | Resultados del piloto y de Pontevedra, método y limitaciones. Descargar y abrir en el navegador. |

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
calibrado. **Ese número no es incumplimiento**: la ley exime a las frondosas no listadas,
y en la franja del piloto un tercio del arbolado de monte lo es (fase 3). Detalle y
avisos en el
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
y al reinyectar ese error el umbral queda a ±1 m en el 98 % de las réplicas.
En el experimento de perturbación, añadir error de anotación
aumentó la tasa de falsos positivos medida. Esa dirección depende del modelo de
error usado: **no demuestra que el 24,2 % sea un techo del error verdadero**.

Y una medición independiente del CHM: por fotointerpretación, **el 27,7 % de la franja
tiene arbolado**. El CHM a 5,5 m marca 35,9 %. La diferencia de superficies refleja falsos positivos menos falsos negativos;
no equivale a la tasa de falsos positivos del producto, FP / (TP + FP).

**Sobre el sesgo de especie, un resultado negativo:** la subpregunta de tipo de copa
solo pudo contestarse en 25 de los 87 árboles, y en 15 de ellos la respuesta fue «no
distinguible». **La especie no se puede tipificar por fotointerpretación sobre
ortofoto a esta escala.** La fase 3 necesitó una verdad de referencia que no viniera
del ojo.

**Fase 3 completada.** Cruce con el Inventario Forestal Nacional (IFN4, 2010), que la
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

**Sentinel-2 estacional: montado, validado con la comarca y rechazado.** Se comprobó primero que el atajo era
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
| Sobre 35 m (atribución a eucalipto asumida por el modelo) | 16,2 ha |

**El entregable** (`scripts/ranking_final.py`) compone las piezas validadas y los
supuestos declarados en el ranking de parroquias y concellos por franja con arbolado prohibido:

> De las 2.848 ha de franja medidas, 1.167 ha tienen arbolado, y **entre 353 y
> 574 ha son de especie prohibida**. A Cañiza encabeza por concello (148–239 ha)
> y Valeixe (Santa Cristina) por parroquia (40–59 ha).

Las cotas componen la tasa de falsos positivos del CHM (con su IC95), la fracción
prohibida del IFN (con el arbolado disperso llevado a las cotas, no etiquetado) y
la regla de los 35 m. La atribución de ese arbolado a eucalipto es un supuesto
estructural del modelo: comprobar que los puntos son árboles no valida su especie.
El orden es para priorizar inspección; los números **no son
superficie de infracción**.

**Validación del producto, fuera de muestra.** 250 puntos frescos fotointerpretados
a ciegas en 127 de los 260 bloques que la calibración nunca vio:

| | fase 2 (3 bloques) | producto (260 bloques) |
|---|---|---|
| Tasa de falsos positivos | 24,2 % [17,0–31,2] | **33,5 % [25,2–41,8]** |
| Sensibilidad | 89,4 % | 89,8 % |
| Puntos >35 m que son árbol | — | 14 de 15 (1 dudoso) |

La sensibilidad y la detección de arbolado alto aguantan; la tasa de FP sale compatible
pero desplazada al alza, y **el ranking usa la tasa nueva** — está medida en el
dominio donde el producto se aplica, y pecar de pesimista es el criterio de la
casa. Medición independiente: por fotointerpretación el 28,6 % de la franja tiene
arbolado; el CHM marca 41,0 %, y esa diferencia es coherente con la tasa de FP.

**Fase 7 completada: la provincia de Pontevedra entera, medida y validada.**
3.197 bloques (12,2 × el piloto) en ~5 días de máquina desatendida, 0 CHM
corruptos, y validación fresca fuera de muestra en el territorio nuevo:

| | medido |
|---|---|
| Cobertura | **38.601 ha de franja — la provincia entera, 54 concellos** |
| Arbolado sobre 5,5 m | 12.709 ha (32,9 %) |
| **Especie prohibida (cotas)** | **[4.770 – 8.141] ha** (sin fase 6: [4.493 – 8.515]) |
| Tasa de FP provincial (150 puntos frescos) | **20,1 % [12,8–28,0]** |
| Sensibilidad | 90,1 % [83,6–96,5] |
| Puntos ≥35 m que son árbol | **9 de 9** |

Encabezan Ponteareas (371–586 ha), A Estrada (280–550) y Salvaterra de Miño
(248–395). A Cañiza, primera del piloto, queda séptima. De los 150 puntos de
validación, 16 negativos claros se delegaron al prefiltro de Claude (con la
asimetría medida en el piloto y declarada como límite). Detalle, comandos y
las trampas de escala en la [fase 7](#del-piloto-al-producto-fase-7).

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
pip install -r requirements.txt
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
python scripts/fenologia_especie.py  # caída estacional: validado y RECHAZADO (AUC 0,746)
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
# fases 5 y 6 en la provincia (en este orden: la 6 entrena solo con rodales persistentes)
python scripts/serie_s2_anual.py   --zona pontevedra
python scripts/detecta_eventos.py  --zona pontevedra
python scripts/copas_chm.py
python scripts/descarga_orto25.py  --zona pontevedra
python scripts/muestra_copas.py    --zona pontevedra
python scripts/parches_copas.py    --zona pontevedra
python scripts/embeddings_copas.py --parches datos/procesado/copas/parches_entrenamiento_pontevedra.npy --salida datos/procesado/copas/embeddings_entrenamiento_pontevedra.npy
python scripts/entrena_copas.py    --zona pontevedra --cnn
python scripts/aplica_copas.py     --zona pontevedra
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
python scripts/anotador_prefiltrado.py --dir validacion_pontevedra   # sin los «no» claros del prefiltro
python scripts/fusiona_prefiltro.py --dir validacion_pontevedra      # humano + delegados -> anotacion.csv
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
y [4.493 – 8.288] ha de especie prohibida**, en 54 concellos. Encabezan
Ponteareas (350–593 ha), A Estrada (253–538) y Salvaterra de Miño (248–388);
A Cañiza, primera del piloto, queda octava — el interior de A Paradanta ni
siquiera era el peor sitio. La validación fuera de muestra (150 puntos
frescos, 140 bloques, anotación ciega) dio **tasa de FP del 20,1 %
[12,8–28,0]** y sensibilidad del 90,1 % — compatible con la fase 2 y mejor
que la del piloto (33,5 %): el paisaje costero denso no rompió el producto.
El estrato ≥ 35 m salió **9/9 árbol**. De los 150 puntos, 16 negativos claros
se delegaron al prefiltro de Claude (asimetría medida en el piloto: cero
árboles humanos entre sus «no»; en esta muestra no es verificable y se
declara). Ese ranking salía de FP × fracción IFN con suelo de 35 m, sin la
fase 6, y con la cota del disperso heredada del piloto: era [4.493 – 8.288] ha.

**Fases 5 y 6 en la provincia (10 al 14-09-2026).** La persistencia se llevó
a Pontevedra componiendo Sentinel-2 **tile a tile** (la provincia cae en
cuatro tiles MGRS; con una sola rejilla las tres escenas menos nubladas
podían salir del mismo tile y dejar NaN en tres cuartos del territorio sin
avisar): **98,2 %** de la superficie de rodal en faixa no presenta eventos detectados
en 2017–2026 (piloto: 97,4 %). Esto respalda el uso del IFN, pero no comprueba
el hueco 2010–2017 ni confirma todas sus etiquetas. La validación del detector
se hizo en el piloto. Los 53 eventos de 2018 son compatibles con las cicatrices
de los incendios de 2017; la sequía es una explicación posible para los 21 de
2026. No se han confirmado individualmente esas atribuciones provinciales.

Se segmentaron **12,9 millones de copas** en el conjunto de los bloques, no solo
fuera de inventario. El CSV del disperso clasificado contiene **88.624 copas**
tras filtrar los parches, de 91.805 candidatas en zonas elegibles.
El clasificador de copas se reentrenó
con 24.000 copas de 407 zonas (piloto: 51): **AUC eucalipto 0,866** fuera de
zona, y la inestabilidad por zonas no se diluye con la escala —60 de 106
zonas evaluables pasan de 0,80, y entre las peores está una de las dos que el
piloto ya tenía diagnosticadas como ortofoto de otra pasada—. Aplicado solo
donde valida (45 zonas, el 24 % del disperso; error OOS fpr 0,252 / fnr 0,123,
mejor que el piloto), la fracción **observada** prohibida del disperso clasificado sale **47,8 %**
ponderada por área (aproximadamente 36 % tras corregir el error), frente al
59,9 % observado del piloto. No representa todo el disperso provincial ni una
comparación calculada excluyendo A Paradanta. **Titular: [4.770 – 8.141] ha, un 16 % más estrecho** que sin
la fase 6 ([4.493 – 8.515]). El podio no cambia (Spearman 0,990 por concello) pero
Lalín baja de 4º a 6º al
medirse su disperso. Sin filtro de Catastro: su WFS limita por IP y se quedó
en 954 de 3.197 celdas; el efecto medido en el piloto es +0,3 puntos en la
fracción del disperso y 1 ha en el titular. La tasa de FP recoge las edificaciones
de la muestra, pero no valida por sí
sola el efecto del filtro sobre la clasificación de especie en toda la provincia.

**Corrección del 14-09-2026.** Hasta ese día la cota alta del arbolado disperso de la
provincia se calculaba con la muestra anotada del piloto (72,2 % de especie prohibida
donde hay rodal), cuando Pontevedra tiene la suya (78,0 %). Corregido: cada zona usa su
muestra, igual que ya pasaba con la tasa de FP. La cota superior sube de 7.969 a
8.141 ha; la inferior no cambia y el orden apenas se mueve (Spearman 0,9996 por
concello; A Cañiza y Tomiño intercambian el 7.º y el 8.º). El piloto sale idéntico.

Al pasar de 263 a 3.197 bloques aparecieron varias trampas de escala. Las dos
principales: `gpd.overlay` contra un multipolígono provincial disuelto anula el
índice espacial (horas de CPU; se trocea en piezas de una parte y se recompone,
y reapareció en seis scripts), y una faixa que roza el borde de un bloque con
menos de un píxel hace reventar la ventana de rasterio (se salta: el bloque
vecino la mide entera). Todas, con su arreglo, en la
[sección 14 del walkthrough](docs/02-walkthrough.md#14-fases-4-a-7-lo-que-hay-que-saber-del-código).
Cada arreglo, verificado con los CSV del piloto byte a byte.

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
(~28 GB), los chips, las escenas de Sentinel-2 y los geopaquetes— porque se regeneran con los scripts de descarga y procesamiento. Ver
[`.gitignore`](.gitignore). La reproducción completa desde un clon limpio no
se ha verificado en esta revisión y depende de la disponibilidad de los servicios
externos. El filtro provincial de Catastro sigue pendiente.

## Cómo citar

Hay un [`CITATION.cff`](CITATION.cff) en la raíz (GitHub muestra el botón «Cite
this repository»). En texto:

> Bermejo Agenjo, M. (2026). *faixas: estimación por LiDAR del arbolado no
> permitido en las franjas de protección contra incendios de Galicia.*
> https://github.com/marcosberag/faixas

## Financiación

[Mini-becas Mihura 2026](https://x.com/XMihura/status/2085671573877313976):
una suscripción de Claude Max durante el mes del 15 de agosto al 15 de
septiembre de 2026, con la condición de documentar y compartir públicamente
el resultado, incluido lo que salió mal. Este repositorio y el
[hilo de resultados](salidas/hilo/hilo_pontevedra.md) son ese entregable.
Lo que salió mal está contado con números a lo largo del README: el
clasificador estacional de Sentinel-2, el detector de cortas, el Catastro
provincial y las trampas de escala.
