# Hilo comarca v2 — «el valor es el método, no el cómputo» (30-08-2026)

Redactado sobre el guion original y pasado por crítica adversarial (datos contra
CLAUDE.md/guion, framing legal, pegada). Todos los tweets ≤ 280 (conteo estilo X,
emoji = 2). Cambios clave respecto al guion: gancho que siembra la tesis, 2+3
fusionados, la casa propia adelantada a la posición 6, el detector contado sin
sobreventa, «en regla» y «no da abasto» eliminados.

**Antes de publicar:**
- Usar `10_chip_anotacion_ccby.jpg` y `07_serie_historica_incendio_ccby.png`
  (los originales NO llevan el © CC-BY horneado). Jamás `post_zoom_limpia.jpg`.
- Tweet 6: la anécdota de la casa va SIN identificar vivienda (regla: nada de
  casas concretas) y sin imagen destacada de una casa; si lleva imagen, la 2×2
  anónima `14_sat_lidar_clasificacion.png`.
- Tweet 14: `[enlace]` exige repo/memoria públicos; si no, cambiar la línea.
- Pegar los alt de cada imagen (abajo).

---

**1 · gancho — `01_comarca_franjas.jpg`** (279)

> en galicia es ilegal tener eucaliptos, pinos o acacias a menos de 50 m de las casas
>
> existe el mapa de dónde lo exige la ley. no existía el de dónde se cumple
>
> lo he construido para una comarca entera: datos públicos, 0 €, un portátil de 8 años. y lo difícil no fue el cómputo 🧵

*Alt: vista aérea de la comarca de A Paradanta con cientos de anillos amarillos
alrededor de los núcleos de población: las franjas de protección.*

**2 · contraste + giro — `02_zoom_franja.jpg` + `03_ortofoto_vs_chm.png`** (274)

> cada mancha naranja debe quedar libre de 7 especies. hoy se comprueba a pie, parcela a parcela — la xunta ha duplicado los inspectores en 2026: esa es la escala
>
> el lidar del ign ya midió la altura de la vegetación de toda galicia, gratis: restas el suelo y tienes cada copa

*Alt 02: ortofoto de aldeas gallegas con las franjas de 50 m en naranja rodeando
las casas, muchas llenas de arbolado. Alt 03: comparación de ortofoto y mapa de
alturas LiDAR; en rojo, copas de más de 35 m junto a un pueblo.*

**3 · la trampa de la especie — `04_prohibido_vs_exento.png`** (279)

> trampa 1: la ley exime a las frondosas autóctonas. un robledal dentro de la franja es legal
>
> y desde el aire, un roble y un eucalipto dan la misma mancha verde
>
> sin especie mandas al inspector al revés: una de las parroquias más arboladas pasó de 19 % de arbolado a 3 % prohibido

*Alt: dos ortofotos de bosque denso aparentemente idéntico; uno rotulado
PROHIBIDA (eucalipto), el otro EXENTA (roble).*

**4 · lista legal literal — sin imagen** (273)

> la especie no es botánica: es una lista legal, literal (sí, arriba simplifiqué)
>
> el pinus pinea no está prohibido aunque sea un pino. la «falsa acacia» está exenta aunque se llame acacia
>
> el código aborta ante especie desconocida: un valor por defecto sería el bug más caro

**5 · anotación ciega — `10_chip_anotacion_ccby.jpg`** (273)

> ¿cómo sé que el mapa acierta? 650 puntos anotados a ciegas sobre ortofoto: el anotador nunca ve lo que dijo el algoritmo
>
> con rejilla de 10 m y mira de 3 m: sin escala no distingues un pino joven de un tojo, y esa es la frontera
>
> tasa de falsos positivos: 33,5 %, publicada

*Alt: recorte de ortofoto con rejilla métrica de 10 m y mira central de 3 m,
tal como lo ve el anotador.*

**6 · el tejado — sin imagen (o `14_sat_lidar_clasificacion.png`)** (259)

> mi error favorito: una casa salió en el mapa como un árbol de 10 m
>
> para un láser, un tejado a dos aguas y una copa se parecen demasiado. crucé con las huellas de edificio del catastro: 589 «copas» eran tejados
>
> cazar esto vale más que cualquier décima de auc

*Alt (si lleva la 14): panel de cuatro vistas de la misma aldea: ortofoto, mapa
de alturas LiDAR y las dos con círculos de colores sobre cada árbol clasificado.*

**7 · medir al que mide — sin imagen** (279)

> lo que casi nunca se publica: medir también al que mide
>
> el anotador (yo) repitió 126 puntos en un retest ciego: kappa 0,88 en lo claro, 0,53 en la duda. ese ruido, reinyectado en 1.000 réplicas, mueve el umbral menos de 1 m en el 98 %
>
> aquí hasta el error humano lleva su número

**8 · lo que no funciona — `09_caida_estacional.png`** (275)

> también publico lo que no funciona
>
> la idea bonita: el roble pierde la hoja en invierno y el eucalipto no, se ve desde satélite. en rodal puro, funciona. en el píxel mezclado de 10 m, se muere. medido, rechazado y contado con números
>
> un resultado negativo también es ciencia

*Alt: gráfico de barras con la caída estacional de NDVI: 0,257 en roble,
0,009 en pino, −0,033 en eucalipto.*

**9 · máquina del tiempo — `07_serie_historica_incendio_ccby.png`** (269)

> el inventario de especies es de 2010. ¿sigue valiendo?
>
> monté un detector de cambios con satélite. 37 de sus avisos forman manchas contiguas en 2018: los incendios de octubre de 2017, encontrados sin saber que existieron
>
> el 97 % de los rodales en franja no ha cambiado

*Alt: hoja de contacto con 8 vistas del mismo rodal entre 2010 y 2026: bosque
intacto hasta 2017, cicatriz de incendio en 2020, recuperación después.*

**10 · el disperso — `13_disperso_clasificado.png`** (279)

> ¿y el arbolado suelto, el que ningún inventario cartografía? es más de un tercio del de la franja
>
> 1,18 millones de copas, un clasificador por textura de ortofoto, 24.000 etiquetas gratis del inventario. auc 0,86 validando con zonas enteras fuera
>
> y donde no valida, no se aplica

*Alt: ortofoto con decenas de círculos de colores sobre árboles sueltos:
rojo eucalipto, naranja pino, verde frondosa.*

**11 · el resultado — `08_ranking_parroquias.png`** (271)

> el resultado: 2.848 ha de franja medidas, 1.167 con arbolado, entre 353 y 574 de especie prohibida. la horquilla no es una disculpa: es la parte del error que se pudo medir
>
> 10 de 40 parroquias concentran el 55 %: más de la mitad del problema visitando una de cada cuatro

*Alt: gráfico de barras horizontales con las 10 parroquias prioritarias y el
intervalo de hectáreas de cada una.*

**12 · el aviso — sin imagen** (224)

> importante: esto es una herramienta de triaje, no una lista de infractores
>
> la propia ley admite excepciones que ningún sensor puede evaluar. el mapa solo ordena dónde mirar primero; la palabra la sigue teniendo el inspector

**13 · cierre — sin imagen** (271)

> coste de los datos: 0 €. cómputo: un i5 de hace 8 años
>
> el valor: leer la ley al pie de la letra, anotar a ciegas, medir hasta mi propio error y publicar lo que falla
>
> lo siguiente ya está medido: la provincia de pontevedra entera, 12 veces esta comarca. pronto, por aquí

**14 · remate — sin imagen** (220)

> memoria y código, abiertos y reproducibles de punta a punta: [enlace]
>
> proyecto financiado por una mini-beca privada (x. mihura). si trabajas en prevención de incendios o en administración local y esto te sirve: hablemos

---

El hilo B técnico del guion original sigue vigente tal cual: publicarlo como
respuesta al tweet 14 o citándolo 2-3 días después.
