# Guion del hilo — faixas

Material en `salidas/hilo/`. Las imágenes generadas salen de `scripts/material_hilo.py`
(regenerables); las numeradas 01, 02, 07 y 10 son copias de material que ya existía.

**Reglas antes de publicar:**

- **Atribución obligatoria** (CC-BY): toda imagen con ortofoto lleva «ortofoto PNOA © IGN»
  y las de satélite «Sentinel-2 © Copernicus» ya horneadas. No recortar el pie.
- **Framing**: siempre «indicador de riesgo / herramienta de triaje», nunca «lista de
  infractores» ni «ilegales» aplicado a parcelas o personas. La ley admite excepciones
  que ningún sensor evalúa. Los números son cotas de un indicador, no infracción acreditada.
- Sin referencias a parcelas ni viviendas concretas: la unidad es parroquia y concello.

---

## HILO A — el general

**1 · gancho — imagen `01_comarca_franjas.jpg`**
> En Galicia es ilegal tener eucaliptos, pinos o acacias a menos de 50 m de las casas.
> Existe el mapa de dónde lo exige la ley. No existía el mapa de dónde se cumple.
> Lo hemos construido para una comarca entera, con datos públicos y código abierto. 🧵

*Alt: vista de satélite de la comarca de A Paradanta con cientos de anillos amarillos
alrededor de los núcleos de población: las franjas de protección.*

**2 · la franja — imagen `02_zoom_franja.jpg`**
> Cada mancha naranja es una franja: 50 m alrededor de cada núcleo y cada vivienda que
> deben estar libres de 7 especies (pinos, eucaliptos, acacias) — las que convierten un
> fuego en una catástrofe. Verificarlo hoy es un inspector andando parcela a parcela.
> La Xunta ha duplicado la plantilla en 2026 y no da abasto.

*Alt: ortofoto de aldeas gallegas con las franjas de 50 m dibujadas en naranja
rodeando las casas, muchas llenas de arbolado.*

**3 · el LiDAR — imagen `03_ortofoto_vs_chm.png`**
> ¿Cómo se mide sin ir? Con el LiDAR aéreo del PNOA (IGN): un láser desde avión que
> devuelve la altura de cada cosa. Restando el suelo obtienes la altura del dosel (CHM).
> Izquierda: lo que ve una foto. Derecha: lo que mide el láser. En rojo, copas de MÁS
> DE 35 METROS dentro de la franja. En Galicia solo el eucalipto llega ahí.

*Alt: comparación lado a lado de una ortofoto y su mapa de alturas LiDAR; en el mapa
de alturas, manchas rojas marcan copas de más de 35 m junto a un pueblo.*

**4 · la trampa de la especie — imagen `04_prohibido_vs_exento.png`**
> Contar árboles altos no basta. La ley EXIME a las frondosas autóctonas: un robledal o
> un castañar dentro de la franja es legal. Y desde el aire, un roble y un eucalipto dan
> la misma señal verde. Sin separar especie, mandas al inspector justo al sitio equivocado:
> la parroquia más arbolada de la comarca resulta ser monte de frondosa, en regla.

*Alt: dos ortofotos de bosque denso aparentemente idéntico; uno rotulado PROHIBIDA
(eucalipto), el otro EXENTA (roble).*

**4b · deep learning donde aporta (sin imagen, o repite la `03`)**
> ¿Y el arbolado suelto, el que ningún inventario cartografía? Partimos el mapa de
> alturas en 1,18 millones de copas individuales y entrenamos un clasificador de
> especie con la textura de cada copa a 25 cm — con 24.000 copas etiquetadas gratis
> por el inventario. AUC 0,86 validando con zonas enteras fuera. Y donde no valida
> (dos zonas con ortofoto de otra pasada), no se aplica. Así de simple.

**5 · el resultado — imagen `08_ranking_parroquias.png`**
> El resultado, con su incertidumbre a la vista: de 2.848 ha de franja medidas,
> 1.167 tienen arbolado y entre 353 y 574 ha son de especie prohibida.
> 10 de las 40 parroquias concentran el 55 % del problema. Un servicio de inspección
> que siga este orden encuentra más de la mitad del incumplimiento visitando un
> cuarto del territorio.

*Alt: gráfico de barras horizontales con las 10 parroquias prioritarias y el intervalo
de hectáreas prohibidas de cada una.*

**6 · el aviso (sin imagen, o cita al tuit 5)**
> Importante: esto es una herramienta de TRIAJE, no una lista de infractores. La propia
> ley admite excepciones que ningún sensor puede evaluar. El mapa ordena dónde mirar
> primero; la palabra la sigue teniendo el inspector.

**7 · la película — imagen `05_serie_ndvi.png`**
> El inventario de especies es de 2010. ¿Sigue valiendo? Pusimos 10 veranos de satélite
> (Sentinel-2) sobre cada rodal. La línea roja son los rodales que se quemaron en los
> incendios de octubre de 2017: el detector los encontró solo, sin saber que existieron.
> El 97 % del monte en franja no ha cambiado — la etiqueta de 2010 aguanta.

*Alt: gráfico de líneas 2017–2026; la mediana de los rodales quemados se desploma en
2018 y se recupera lentamente; la de los persistentes se mantiene plana.*

**8 · la honestidad — imagen `06_mapa_eventos.png`**
> También publicamos lo que NO funciona: el mismo detector, usado para cazar cortas
> recientes, falla — la sequía de agosto de 2026 baja el verdor de toda la comarca y
> fabrica espejismos (0 de 8 comprobados). Lo medimos, lo contamos y no lo usamos.
> En este proyecto los resultados negativos también se publican, con números.

*Alt: mapa de la comarca con los rodales con evento coloreados por año; una gran
mancha roja al suroeste son las cicatrices de los incendios de 2017.*

**9 · la validación histórica — imagen `07_serie_historica_incendio.png`**
> ¿Y cómo se comprueba un detector de cambios? Con la máquina del tiempo: las ortofotos
> históricas del PNOA. Para 65 rodales montamos su historia 2010→2026 y un anotador
> ciego dijo si veía el reemplazo y cuándo. Esta es la hoja de un rodal quemado en 2017:
> se ve a simple vista en el vuelo de 2020.

*Alt: hoja de contacto con 8 vistas del mismo rodal entre 2010 y 2026: bosque intacto
hasta 2017, cicatriz de incendio en 2020, recuperación después.*

**10 · la validación a ciegas — imagen `10_chip_anotacion.jpg`**
> Cada número lleva su tasa de error, medida así: cientos de puntos anotados A CIEGAS
> sobre ortofoto (el anotador nunca ve lo que dice el algoritmo), con rejilla de 10 m
> para no confundir un pino joven con un tojo. Tasa de falsos positivos del producto:
> 33,5 % — medida fuera de muestra y publicada. Pecar de pesimista es el criterio.

*Alt: recorte de ortofoto con rejilla métrica y una mira central de 3 m, tal como lo
ve el anotador.*

**11 · la escala (sin imagen)**
> Coste de los datos: 0 €. Todo es público — LiDAR y ortofotos del IGN, franjas de la
> Xunta, inventario forestal, Sentinel-2 de Copernicus. La comarca se procesó en un
> portátil de 8 años. Galicia entera son ~3 semanas en ese mismo portátil, o un día
> en la nube por decenas de euros. El único límite: concellos sin plan aprobado no
> tienen franja publicada.

**12 · cierre**
> Memoria completa, con todas las tasas de error y las decisiones documentadas:
> [enlace a la memoria]. Código y datos, reproducibles de punta a punta.
> Proyecto financiado por una mini-beca privada (X. Mihura). Si trabajas en prevención
> de incendios o en administración local y esto te sirve: hablemos.

---

## HILO B — el técnico (para quien quiera las tripas)

**1 — stack y fuentes**
> Cómo se hizo, en técnico 🧵: Python con PDAL, GDAL, rasterio y GeoPandas.
> Fuentes: LiDAR PNOA 3ª cobertura (bloques LAZ de 1×1 km, ~5 pulsos/m²), franjas
> oficiales de la Xunta (ArcGIS REST), IFN4 2010 (IDE Xunta), Sentinel-2 L2A en COG
> sobre AWS leído por rangos HTTP. Todo EPSG:25829.

**2 — la nube de puntos engaña**
> El fichero LAZ trae 17,5 pts/m², pero el 64 % es solape entre pasadas (clase 12).
> Sin filtrarlo ANTES (streaming), PDAL revienta la RAM. Tras un retorno por pulso:
> 4,9 pts/m² reales. Y la clasificación NPC01 es provisional: el suelo se reclasifica
> desde cero (SMRF, slope 0.20, window 16 — subido por el relieve gallego).

**3 — CHM**
> MDT por IDW desde puntos de suelo; MDS por máximo de primeros retornos;
> CHM = MDS − MDT, rasterizado a 1 m. El tamaño de píxel NO es un detalle: a 0,5 m
> el mismo arbolado da un 17 % menos de superficie. Se calibró a 1 m y no se toca
> sin recalibrar. 170 s/bloque; la comarca entera (263 bloques), una tarde-noche.

**4 — ¿qué es «un árbol»? Se calibra, no se decide**
> Umbral de arbolado: 5,5 m, calibrado contra 400 puntos de ortofoto anotados a ciegas
> (muestreo estratificado por altura, chips con rejilla de 10 m y mira de 3 m).
> Sensibilidad 89,8 %. La tasa de falsos positivos se midió DOS veces: 24,2 % en
> calibración y 33,5 % [25–42] fuera de muestra, en 127 bloques nuevos. El producto
> usa la peor.

**5 — hasta el anotador tiene tasa de error**
> El fotointérprete se contrastó consigo mismo: retest ciego de 126 puntos, kappa 0,88
> en casos claros y 0,53 en la zona de decisión (2–8 m). Ese ruido se reinyectó en la
> muestra: el umbral aguanta ±1 m en el 98 % de 1.000 réplicas. Y ojo con kappa en
> clases desbalanceadas: 93,6 % de acuerdo puede dar kappa ≈ 0 (paradoja de kappa).

**6 — la especie es una lista legal, no botánica**
> La Ley 3/2007 prohíbe 7 taxones LITERALES. Pinus pinea NO está (aunque sea un pino);
> Quercus suber y el laurel son perennifolios y SÍ están exentos; la «falsa acacia»
> (Robinia) está exenta. El código ABORTA si el inventario trae una especie sin
> clasificar: un .get(especie, exenta) silencioso es el bug más caro del proyecto.
> Los rodales mixtos se tratan con la ocupación como fracción continua (¡son décimas!).

**7 — el clasificador satelital que NO entró**
> La idea bonita: el roble pierde hoja en invierno (ΔNDVI 0,26), el eucalipto no (−0,03).
> Funciona en rodal puro (AUC 0,87)… y se muere en el píxel mezclado de 10 m: validación
> cruzada dejando zonas fuera → AUC 0,746 y varianza espacial 0,30–0,93. Rechazado y
> publicado como resultado negativo, con el porqué medido. (imagen `09_caida_estacional.png`)

**7b — del píxel a la copa**
> El disperso se atacó a nivel de árbol: watershed sobre el CHM (1,18 M de copas),
> parche de ortofoto de 16×16 m por copa, y HistGradientBoosting sobre rasgos de
> textura + embedding MobileNetV3 (CPU, sin GPU). Etiquetas débiles de rodales puros
> del IFN filtrados por persistencia. AUC 0,86 fuera de zona; fpr/fnr OOS propagados
> a las cotas con la corrección clásica de mala clasificación. Aplicado solo en
> zonas con AUC ≥ 0,80 — lo demás conserva la cota ancha.
> Y una anécdota que vale un tuit: un tejado a dos aguas también "mide" 10 m para
> el LiDAR, y una casa salió delineada como copa. Se cruzó con las huellas de
> edificio del Catastro y 589 "copas" resultaron ser tejados (el 1,8 %) — fuera
> del mapa. (imagen `14_sat_lidar_clasificacion.png`)

**8 — trampas de datos reales**
> El STAC declara offset −0,1 para estos COG… que ya vienen armonizados: aplicarlo da
> NDVI mediana 1,89. Guardia de rango que aborta si >1 % sale de [−1,1]. El WMS devuelve
> errores como HTTP 200+XML. El nombre del bloque LiDAR codifica la esquina NOROESTE,
> no la SW. Cuando el metadato y el dato discrepan, mandan los datos.

**9 — persistencia: la validación con ortofoto histórica**
> ¿Vale un inventario de 2010 en 2026? Detector sobre la serie anual de NDVI
> (caída ≥0,18 respecto al techo de 2 años y suelo <0,60, efecto-año descontado),
> y validación contra los 7 vuelos históricos del PNOA (2010–2023) con anotación ciega
> por intervalos. Persistencia: 97,4 % en faixa, acotada [81–99]. Falsos negativos: 3,8 %.

**10 — y el detector de cortas, partido en dos**
> Precisión de eventos: 69 % donde hay ortofoto para comprobar (2019–23) y 12 % en la
> era solo-satélite (2024–26): la sequía de 2026 fabrica espejismos que ni la densidad
> del rodal ni la magnitud de la caída separan. ¿Exigir la caída 2 veranos? Medido y
> rechazado: la corta gallega REBOTA en un año (el eucalipto rebrota de cepa; NDVI no
> es biomasa). El fuego sí persiste (5/6). Vigilar cortas pide compuestas mensuales.

**11 — reproducibilidad**
> Semillas fijadas, cada figura y cada número se regeneran por script desde los datos
> crudos, y las decisiones (con sus trampas) están documentadas en el repo. La memoria:
> [enlace]. Si quieres replicarlo en tu comarca: el código está abierto.

---

## Material de reserva (ya existe en `salidas/`)

| Fichero | Para qué |
|---|---|
| `chuleta_tipo_copa.png` | cómo distingue el anotador pino/eucalipto/acacia/frondosa |
| `vigencia_86265.png` | el panel del falso evento de sequía (rodal ralo) — la trampa contada |
| `discrepancias_fp_*.png` | ejemplos reales de falsos positivos del CHM |
| `faixas_geometrias_paradanta.png` | mapa limpio de las geometrías de franja |
| `post_zoom_limpia.jpg` | el zoom del tuit 2 sin atribución horneada (NO publicar sin añadirla) |
| hojas `validacion_persistencia/hojas/v*.png` | 65 historias 2010→2026; v017 y v063 son cicatrices confirmadas |

## Cifras de bolsillo (por si preguntan)

- Franja medida: 2.848 ha (99,9 % de la comarca) · arbolado >5,5 m: 1.167 ha (41 %)
- Prohibido: **[353–574] ha** · sobre 35 m (eucaliptal seguro): 16,2 ha
- Clasificador de copas: AUC 0,86 fuera de zona; aplicado en el 45 % del disperso
- FP del producto: 33,5 % [25,2–41,8], fuera de muestra · sensibilidad 89,8 %
- Persistencia del monte en franja 2017–2026: 97,4 % [81–99]
- Incendios oct-2017: 37 rodales encontrados a ciegas por el detector
- Coste de datos: 0 € · comarca procesada en un i5-8350U · Galicia ≈ 3 semanas
