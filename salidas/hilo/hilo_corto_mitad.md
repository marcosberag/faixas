# Hilo corto — mitad de proceso, v3 (30-08-2026)

Explicador de qué hemos hecho: **un paso por tweet, una imagen por tweet**.
7 tweets, todos ≤280 verificados (conteo estilo X, emoji = 2). Sin rayas ni
punto y coma; topónimos con mayúscula, resto en minúsculas.

**Antes de publicar:** la imagen del tweet 5 es `10_chip_anotacion_ccby.jpg`
(el original sin `_ccby` no lleva el © del IGN). Jamás `post_zoom_limpia.jpg`.

---

**1 · el problema — `01_comarca_franjas.jpg`** (272)

> en Galicia, por ley, a menos de 50 m de las casas no puede haber eucaliptos, pinos ni acacias
>
> cada anillo amarillo es una de esas franjas. el mapa de dónde lo exige la ley existe. el de dónde se cumple, no existía
>
> lo he construido para una comarca entera: A Paradanta 🧵

*Alt: vista aérea de la comarca de A Paradanta con cientos de anillos amarillos
alrededor de los núcleos de población: las franjas de protección.*

**2 · la altura — `03_ortofoto_vs_chm.png`** (271)

> primero, la altura: el ign escanea España entera con láser desde avión, público y gratis. mide la altura de todo. quitando el suelo, queda la de cada árbol
>
> izquierda, la foto. derecha, el láser. en rojo, copas de más de 35 m dentro de franja: ahí solo llega el eucalipto

*Alt: comparación de una ortofoto y su mapa de alturas LiDAR; en el mapa de
alturas, manchas rojas marcan copas de más de 35 m junto a un pueblo.*

**3 · la especie — `04_prohibido_vs_exento.png`** (267)

> segundo, la trampa de la especie: la ley exime a las frondosas autóctonas. un robledal dentro de la franja es legal
>
> estos dos bosques dan la misma mancha verde desde el aire. solo uno está prohibido. sin separar especie, mandas al inspector justo al sitio equivocado

*Alt: dos ortofotos de bosque denso aparentemente idéntico; uno rotulado
PROHIBIDA (eucalipto), el otro EXENTA (roble).*

**4 · todo junto — `14_sat_lidar_clasificacion.png`** (279)

> tercero, juntarlo: la misma escena vista por ortofoto, láser y clasificador. cada círculo, un árbol suelto con su especie: eucalipto, pino o frondosa exenta
>
> la especie sale del inventario forestal público y de un clasificador entrenado con él. los tejados, fuera con el catastro

*Alt: panel de cuatro vistas de la misma aldea: ortofoto, mapa de alturas LiDAR
y las dos con círculos de colores sobre cada árbol clasificado.*

**5 · la prueba — `10_chip_anotacion_ccby.jpg`** (276)

> ¿y cuánto acierta el mapa? está medido, no supuesto: cientos de puntos comprobados a ciegas sobre ortofoto, sin ver lo que dijo el algoritmo
>
> de cada 3 avisos de árbol, 1 no lo es (33,5 %). y se escapa 1 árbol de cada 10. parece mucho, pero el resultado ya lo lleva descontado

*Alt: recorte de ortofoto con rejilla métrica de 10 m y mira central de 3 m,
tal como lo ve el anotador.*

**6 · el resultado — `08_ranking_parroquias.png`** (248)

> resultado, con los errores ya descontados: 2.848 ha de franja medidas, 1.167 con arbolado y entre 353 y 574 con alguna de las especies prohibidas
>
> 10 de 40 parroquias concentran el 55 %. es triaje: ordena dónde mirar primero, no acredita infracción

*Alt: gráfico de barras horizontales con las 10 parroquias prioritarias y el
intervalo de hectáreas de cada una.*

**7 · cierre — `15_pontevedra_contexto.png`** (229)

> la máquina no ha parado: Pontevedra entera ya está procesada. 3.197 km² de lidar, 12 veces esta comarca, en el mismo portátil de 8 años
>
> las cifras, cuando pasen su validación. el código abierto, en camino. sigo contando por aquí

*Alt: mapa de la provincia de Pontevedra dibujada por sus miles de franjas de
protección en naranja; un recuadro negro marca la comarca de A Paradanta.*
