# Plan de trabajo

Plazo: **aproximadamente un mes**. Entregable: ranking de parroquias y concellos por
superficie de franja con arbolado no permitido, más el código abierto y reproducible.

Redactado el 16 de agosto de 2026. Ver el [estado real del código](02-walkthrough.md).

---

## Lo que ha cambiado respecto a la propuesta inicial

Dos hallazgos de los primeros días mueven prioridades:

1. **El servicio de la Xunta no exporta geometrías.** Sin polígonos no hay recorte, y sin
   recorte no hay métrica. Es el bloqueo nº 1 y va antes que cualquier otra cosa.
2. **La ley exime a las frondosas no listadas** (disposición adicional tercera, punto 3).
   Castaños y robles pueden estar dentro de la franja legalmente. Eso degrada "arbolado
   sobre umbral" de indicador a proxy sesgado, y sube la clasificación de especie de
   *deseable* a *casi necesaria*. Ver [marco legal](03-marco-legal.md).

---

## Por qué Galicia y por qué A Paradanta

### Por qué Galicia

No es preferencia: es la única de las comunidades revisadas donde el problema es
**medible con datos públicos**. Hacen falta tres cosas a la vez, y Galicia es la que las
reúne:

1. **Una norma concreta y verificable.** La Ley 3/2007 fija una anchura exacta (50 m) y
   una lista cerrada de siete especies arbóreas. Cataluña, en cambio, pide "aclarar la
   masa arbórea", que no es un criterio binario. Madrid no impone franja perimetral.
2. **Una capa de obligación publicada y única.** La Xunta publica los polígonos para
   toda la comunidad: **276 de los 313 concellos gallegos, el 88 %**. En Cataluña la
   delimitación la aprueba cada ayuntamiento por separado.
3. **LiDAR ya disponible.** El PNOA de tercera cobertura está publicado para Galicia.

Añádase el contexto: es la comunidad con mayor presión de incendios del Estado, y la
Xunta duplicó la plantilla de inspección en 2026 — hay un destinatario real para una
herramienta de priorización. Detalle comparado en
[marco legal, §5](03-marco-legal.md#5-escalabilidad-fuera-de-galicia).

### Por qué A Paradanta

**Aviso de honestidad:** la elección de la comarca es anterior a esta documentación y no
consta argumentada en ninguna parte. Lo que sigue es una **verificación a posteriori**
contra la capa completa de Galicia (`scripts/justifica_piloto.py`), no la motivación
original.

La comarca aguanta el examen, y por un motivo mejor que ser "representativa":

| | A Paradanta | Galicia |
|---|---|---|
| Concellos con capa publicada | 4 de 4 | 276 de 313 (88 %) |
| Superficie de franja | 2.850 ha | mediana 478 ha/concello |
| Percentil por concello | 52 %, 59 %, 65 % y 91 % | — |
| Franja en edificaciones aisladas | **17–26 %** | mediana **4,8 %** |
| Área mediana por polígono | 1.886 m² | 2.718 m² (**0,69×**) |

Lo que dicen esos números:

- **Comarca completa, sin huecos.** Los cuatro concellos tienen plan aprobado y capa
  publicada. No hay que explicar por qué falta un municipio en medio del mapa.
- **Tamaño bien calibrado.** 2.850 ha de franja, el 1,70 % del total gallego: bastante
  para que un ranking de 40 parroquias signifique algo, poco para caber en un mes.
- **Es un caso difícil, no uno cómodo.** El poblamiento disperso es entre tres y cinco
  veces la mediana gallega, y los polígonos son un 31 % más pequeños que la mediana. Más
  fragmentación y más edificación aislada significan más perímetro por hectárea, más
  efecto de borde en el recorte del CHM y más superficie en contacto con monte. Si el
  método funciona aquí, en una comarca de núcleos compactos funciona mejor.

**Limitación que hay que declarar:** es una sola comarca, de una sola provincia, con un
solo tipo de paisaje. El 1,70 % de la franja gallega no es una muestra representativa de
Galicia, y las tasas de error medidas aquí **no son extrapolables** al resto de la
comunidad sin validación adicional. Sirve para demostrar el método y calibrar el umbral,
no para afirmar nada sobre Lugo o A Coruña.

---

## Fases

### Fase 0 — Desbloquear las geometrías 🔴 crítica

Nada avanza sin esto. Por orden de coste:

1. Buscar las capas en el **WFS de la IDEG**.
2. Buscar **descarga directa** (shapefile/GPKG) en datos abiertos de la Xunta.
3. Inspeccionar el tráfico del **visor oficial** de faixas.
4. Si todo falla: **vectorizar el ráster** de `/export` a resolución alta, asumiendo y
   documentando el error de frontera.

**Criterio de salida:** polígonos de los 49 + 52 registros en EPSG:25829, con `PARROQUIA`
y `CONCELLO`, y área total contrastada contra una medición independiente.

**Si se atasca más de dos o tres días**, tirar de la opción 4 y seguir. Un error de
frontera de un metro es asumible; quedarse sin pipeline no lo es.

---

### Fase 1 — Un bloque LiDAR de extremo a extremo ✅ completada

Hecho sobre **tres** bloques de 1×1 km, no uno, en tres concellos distintos: 559-4674
(A Cañiza), 562-4668 (Crecente) y 549-4679 (Covelo).

Criterio de salida cumplido: `datos/procesado/metricas/metricas_faixa_bloque.csv` y
`metricas_parroquia.csv`, con tiempos en `datos/procesado/lidar/tiempos_proceso.csv`.
Números y trampas en el [walkthrough](02-walkthrough.md).

**La escala no es un problema.** 170 s por bloque en un i5-8350U, 263 bloques con franja
en la comarca: 12,4 h en serie, una noche en paralelo, ~28 GB de LAZ. Se mantiene la
decisión de no optimizar nada.

Tres cosas que salieron de aquí y cambian lo que viene:

1. **La resolución del píxel mueve la métrica un 17 %** entre 1 m y 0,5 m, sistemático y
   en el mismo sentido en todos los umbrales, porque el MDS toma el máximo de la celda.
   Se fija **1 m** para producción.
2. **El LiDAR trae banda infrarroja** (formato de punto 8, con RGB + NIR). La fase 3 no
   necesita descargar nada más para intentar el NDVI.
3. **Los edificios contaminan poco** (1–2 % a umbrales altos): la capa de la Xunta ya
   recorta la huella de las edificaciones. Descontar casco urbano baja de prioridad.

---

### Fase 2 — Calibrar el umbral y validar ✅ completada

**Umbral: 5,5 m. Tasa de falsos positivos: 24,2 %, IC95 [17,0 – 31,2].** A 1 m de
píxel y no transferible a otra resolución. Números completos en la
[sección 11 del walkthrough](02-walkthrough.md#11-fase-2-el-resultado).

Dos hallazgos que condicionan lo que viene:

1. **El sesgo de especie sigue sin medir, y la vía barata para medirlo se ha caído.**
   La subpregunta de tipo de copa solo se pudo contestar en 25 de 87 árboles, con 15
   «no distinguible» y **cero** de la lista prohibida: la especie no se tipifica por
   fotointerpretación a esta escala. La fase 3 pasa de «casi necesaria» a **bloqueante
   para el entregable** —sin ella el ranking no ordena lo que dice ordenar— y además
   arranca sin verdad de referencia, que es lo primero que hay que resolver.
2. **La consistencia del anotador en la zona de decisión es kappa 0,53.** Moderada.
   Es una limitación real del producto y se publica junto a la tasa de FP. Si hubiera
   presupuesto para un segundo anotador, ahí es donde más valdría.

Cómo se montó, en la
[sección 10 del walkthrough](02-walkthrough.md#10-fase-2-calibrar-el-umbral-contra-ortofoto).

Decisiones de diseño que ya están tomadas:

- **La unidad de validación es el punto**, no el polígono. Una franja no es "arbolada" o
  "no arbolada"; el punto es la única unidad con respuesta binaria fiable.
- **Muestreo estratificado por altura de CHM**, sobremuestreando los 1–6 m, que es donde
  el umbral decide. Con reponderación por `peso_m2`: se suman metros cuadrados, nunca se
  cuentan puntos. Separación mínima de 15 m para no medir dos veces la misma copa.
- **Anotación ciega sin excepciones.** La altura del CHM no se enseña ni después de
  responder, y ni siquiera viaja al HTML. Las discrepancias se revisan al final.
- **Se publica la tasa de FP del producto** (1 − precisión: de lo que marco, cuánto no lo
  es), no el FPR de la ROC, que es más bonito y responde a otra pregunta. Intervalos por
  bootstrap estratificado.
- **A 1 m de píxel, y escrito en el CSV de salida.** El umbral calibrado no es
  transferible a otra resolución: a 0,5 m la métrica cae un 17 %. `metricas_faixas.py`
  aborta si detecta que la calibración es de otra resolución.
- Registradas las dos fechas: **LiDAR 2024, ortofoto septiembre 2023.** Una corta
  intermedia aparece como falso negativo y no es un error del método; se cuentan aparte
  pero **no se descuentan** de la tasa publicada.

De regalo, la anotación pregunta el **tipo de copa** (conífera/eucalipto contra frondosa
caducifolia) cuando hay árbol. Eso le da a la fase 3 una verdad de referencia sin coste
adicional y una primera cota del sesgo de especie.

---

### Fase 3 — Distinguir especie 🔵 en marcha

**La verdad de referencia ya está resuelta (18-08-2026): IFN4 2010 vía el IDE de la
Xunta**, con geometrías y en EPSG:25829. Clasificación literal contra la disposición
adicional tercera, ocupación como factor continuo. Resultado: **44–72 % del arbolado
en faixa es especie prohibida**, y **3 de 5 parroquias cambian de puesto** al corregir.
Detalle en la [sección 12 del walkthrough](02-walkthrough.md#12-fase-3-separar-lo-prohibido-de-lo-exento).

**La parte de teledetección está montada y sin validar.** Sentinel-2 estacional desde
los COG de AWS (sin registro), con el proxy fenológico comprobado antes contra el IFN:
reproduce el corte legal con 99,37 % de acuerdo *en esta comarca*. La señal sale
inequívoca por especie. Pero con tres bloques la validación cruzada es imposible —solo
dos tienen rodales puros en faixa y uno no tiene ningún píxel caducifolio—, así que el
AUC 0,853 es in-sample y **el resultado no se publica**.

Eso convierte la fase 4 en prerrequisito de la 3, no al revés: lo que falta no es
cómputo sobre los mismos datos, son sitios con robledal y pinar dentro de la misma
faixa.



Ya no es opcional. Sin esto, el indicador confunde un castañar legal con un pinar ilegal.

La buena noticia: **no hace falta identificar especie**. Basta separar dos grupos:

| Hay que detectar | Es legal |
|---|---|
| Pinos, eucalipto, acacias (perennifolias de la lista) | Castaño, roble y demás frondosas caducifolias |

Esa separación es mucho más fácil que la identificación taxonómica, pero arranca con
dos problemas que no estaban previstos y que hay que resolver en este orden.

**Problema 1: no hay verdad de referencia.** La subpregunta de tipo de copa del
anotador iba a darla gratis y se ha caído (25 de 87 árboles contestados, 15 de ellos
«no distinguible», cero de la lista prohibida). No se puede validar un clasificador de
especie contra diez puntos. **Primera tarea de la fase, antes que cualquier señal:**
conseguir referencia independiente. Candidata principal el **MFE del MITECO** (Mapa
Forestal de España, especie dominante por rodal): es la fuente estándar en España, es
descargable y no depende del ojo de nadie. Limitaciones a documentar: escala de rodal,
no de píxel, y fecha de vuelo distinta a la del LiDAR.

**Problema 2: el NIR del propio LiDAR no sirve para lo que hacía falta.** Verificado
sobre el `gps_time` de los tres bloques: **el vuelo es de junio y julio de 2024**,
pleno verano. La separación caducifolia / perennifolia es fenológica —una tiene hoja
en invierno y la otra no— y en junio **todas tienen hoja**. Un castaño y un pino dan
NDVI alto los dos. La banda infrarroja está ahí, alineada y gratis, pero eso es
conveniencia, no adecuación al problema.

Vías, reordenadas por lo que dice la física y no por lo que es cómodo:

- **Estacionalidad con Sentinel-2.** Ahora es la vía principal. Invierno contra verano
  separa caducifolia de perennifolia directamente, que es justo el corte legal. A 10 m
  de píxel, con franjas de 50 m de ancho, hay mezcla de borde — tolerable porque la
  unidad de análisis es la parroquia, pero hay que medirla. El desarrollador ya tiene
  experiencia con Copernicus, así que el coste de entrada es bajo.
- **RGBI del LiDAR como complemento, no como vía principal.** En verano puede aportar
  por reflectancia de hoja (el eucalipto es glauco y da NDVI más bajo que una frondosa;
  el pino es verde oscuro), pero es señal débil y sin fenología detrás. Su ventaja real
  es la resolución y que ya está descargado: sirve para afinar dentro de un rodal que
  Sentinel-2 ya haya etiquetado, no para hacer el corte.
- **Estructura del retorno LiDAR.** Menos directo a esta densidad.

**Si no da tiempo:** publicar el indicador como "arbolado sobre umbral" y declarar el
sesgo de forma explícita y visible, no en una nota al pie.

---

### Fase 4 — Escalar y agregar 🟡 media

Los cuatro concellos, agregado por parroquia y concello, ranking, y el repo publicable.

---

### Fuera de plazo

- Segmentación de copa individual a 5 pts/m². Viabilidad sin confirmar; pendiente de
  consulta al grupo **SILVANET** (UPM). No está en la ruta crítica: la métrica principal
  es superficie, no número de pies.
- Descontar el casco urbano del interior de los polígonos.
- Cualquier cosa a nivel de parcela.

---

## Riesgos

| Riesgo | Impacto | Qué hacemos |
|---|---|---|
| ~~No aparecen las geometrías por ninguna vía~~ | — | **Cerrado en fase 0.** Shapefile del PBA, IoU 0,9996 |
| ~~El LiDAR pesa o tarda más de lo previsto~~ | — | **Cerrado en fase 1.** 170 s/bloque, 12,4 h y 28 GB la comarca |
| ~~NPC01 da clasificación de suelo mala en pendiente~~ | — | **Cerrado en fase 1.** SMRF coincide con NPC01: mediana +5 cm, σ 26 cm, discrepancia > 2 m en el 0,2 % |
| ~~El polígono incluye el casco urbano~~ | Bajo | **Acotado en fase 1.** Los edificios son el 1–2 % de la superficie sobre umbral: la capa ya recorta su huella |
| No da tiempo a clasificar especie | **Alto** | Publicar con el sesgo declarado en portada. Sigue siendo el riesgo nº 1 |
| El umbral calibrado se aplica a otra resolución | Medio | Fijado 1 m; dejarlo escrito en la calibración. 0,5 m da un 17 % menos |
| Lectura pública como "lista de infractores" | Alto | Framing de triaje en todo material; ver más abajo |

---

## Decisiones cerradas

No se reabren salvo motivo de peso:

- **Solo arbolado, no matorral.** El LiDAR es una foto fija, el matorral rebrota entre
  vuelos y a 5 pts/m² no se discrimina bien. La ley sí lo regula: se documenta como
  limitación, no se disimula.
- **Salida como indicador de riesgo, nunca como acusación.** Refuerzo legal: la propia
  ley admite excepciones que el LiDAR no puede evaluar — árbol singular, ornamental, en
  zona recreativa, o aislado sin riesgo de propagación (disp. ad. 3ª, punto 2).
- **Unidad de análisis: parroquia y concello.** La capa oficial no trae referencia
  catastral.
- **Validación manual obligatoria**, con tasa de falsos positivos publicada.
- **Todo en EPSG:25829**, sin reproyecciones.

---

## Cuestiones abiertas

| Cuestión | Estado |
|---|---|
| Umbral de altura | Abierta. Se calibra en fase 2 con la muestra de validación. |
| Clasificación de especie | **Reclasificada como casi necesaria.** Probar RGBI del PNOA primero. |
| Segmentación de copa individual | Abierta. Fuera de ruta crítica. Consultar a SILVANET. |
| Descontar casco urbano | Abierta. Documentar como mínimo. |
| Extender fuera de Galicia | **Cerrada: replicable el método, no el producto.** Verificado sobre tres comunidades el 17-08-2026. El LiDAR del PNOA es nacional; la obligación no. Cataluña son 25 m, solo urbanizaciones aisladas, y pide **aclarar** la masa en vez de eliminar especies — otra métrica, no otro umbral —, con el mapa en manos de cada ayuntamiento. Madrid no tiene franja perimetral obligatoria. Detalle en [marco legal, §5](03-marco-legal.md#5-escalabilidad-fuera-de-galicia). |
