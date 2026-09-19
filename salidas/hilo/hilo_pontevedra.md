# Hilo Pontevedra — el entregable de la minibeca (revisado 19-09-2026)

Segundo hilo. El primero (30-08, 7 tweets, la comarca) cerraba con «Pontevedra
entera, las cifras cuando pasen su validación»: este es ese hilo. Es también el
entregable de las Mini-becas Mihura 2026, cuya condición era compartir en
público el output, qué se probó, qué funcionó y **qué salió mal**. Por eso los
tweets 8 a 10 son fallos con números, no relleno.

Estilo del primer hilo: minúsculas, topónimos con mayúscula, sin rayas ni punto
y coma. Todos los tweets ≤ 280 según `scripts/cuenta_tweets.py` (conteo estilo
X: emoji = 2, URL = 23).

**Antes de publicar:**

- Repositorio **público**, comprobado sin autenticación el 19-09-2026.
  Este guion es un borrador; su presencia en el repo no implica publicación en X.
- Tweet 3: se publica **citando** el primer tweet del hilo anterior
  (`x.com/Eclektiq1/status/2094164582021337173`), no pegando el enlace en el texto.
- Las imágenes con ortofoto o satélite llevan el © horneado: las 16–20 son
  elaboración propia con la fuente en el pie; la 02, 05, 09, 13 y 14 ya lo llevan.
- Pegar los alt de cada imagen (abajo de cada tweet).
- Tweet 15: mencionar a @XMihura para que pueda citarlo; es él quien amplifica.
- No citar juntos el rango de A Cañiza del piloto (148–239) y el provincial
  (150–280): cada zona usa su propia tasa de error y su propia cota alta.

---

**1 · gancho — `16_mapa_pontevedra_ranking.png`**

> en Pontevedra estimo entre 4.770 y 8.141 hectáreas de franja con especies de árboles sujetas a retirada
>
> un mapa para decidir dónde inspeccionar primero: 54 concellos, datos públicos y un portátil de 8 años. las cotas incluyen errores medidos y supuestos declarados 🧵

*Alt: mapa de la provincia de Pontevedra dibujada por sus miles de franjas de
protección, coloreadas de claro a rojo oscuro según las hectáreas de arbolado
prohibido estimadas en cada parroquia. Un recuadro negro marca la comarca de
A Paradanta, el primer hilo. Rotulados Ponteareas, A Estrada y Salvaterra.*

**2 · para quien llega nuevo — `02_zoom_franja.jpg`**

> en Galicia hay franjas de 50 m donde la ley exige gestionar la biomasa y retirar determinadas especies, con excepciones
>
> la Xunta publica esas franjas. cruzarlas con datos de arbolado ayuda a decidir dónde comprobar primero su estado

*Alt: ortofoto de aldeas gallegas con las franjas de 50 m dibujadas en naranja
rodeando las casas, muchas llenas de arbolado.*

**3 · cómo, en un tweet — `14_sat_lidar_clasificacion.png` + cita del hilo anterior**

> cómo: el láser aéreo del ign permite estimar la altura del arbolado. el inventario forestal y un clasificador aportan información de especie
>
> esta imagen muestra el piloto, con filtro de tejados del catastro. el ranking provincial se calculó sin ese filtro

*Alt: panel de cuatro vistas de la misma aldea: ortofoto, mapa de alturas LiDAR
y las dos con círculos de colores sobre cada árbol clasificado por especie.*

**4 · cambia el protagonista — `17_ranking_concellos.png`**

> cambia el protagonista. A Cañiza, que encabezaba la comarca, es la 7.ª de 54. arriba quedan Ponteareas (371 a 586 ha), A Estrada (280 a 550) y Salvaterra (248 a 395)
>
> donde empecé ni siquiera era el peor sitio: la comarca es el 7 % de la franja y el 7 % del problema

*Alt: gráfico de barras horizontales con los diez concellos de más arbolado
prohibido en franja y su horquilla; debajo, separados, los cuatro concellos de
A Paradanta en naranja, con A Cañiza en el puesto 7 y Covelo en el 36.*

**5 · las parroquias — `19_ranking_parroquias_pontevedra.png`**

> por parroquia, encabeza O Hío, en Cangas: entre 46 y 76 hectáreas de franja con especies sujetas a retirada
>
> cada barra combina errores medidos y supuestos sobre lo que falta por conocer. sirve para priorizar la comprobación en campo

*Alt: gráfico de barras horizontales con las diez parroquias prioritarias de la
provincia, cada una con su concello y el intervalo de hectáreas.*

**6 · la misma curva — `18_curva_concentracion.png`**

> lo que más me sorprendió: en ambas escalas, el 22 % de las parroquias concentra la mitad de la superficie estimada
>
> en Pontevedra son 125 de 563. la concentración ayuda a priorizar, aunque todavía falta medir cuánto tiempo de inspección ahorra

*Alt: dos curvas de concentración casi superpuestas, naranja la comarca y azul la
provincia: porcentaje de parroquias frente a porcentaje del arbolado prohibido
acumulado. Un punto en cada una marca el 50 % del problema en el 22 % de las
parroquias. Una diagonal punteada indica el reparto uniforme.*

**7 · cuánto acierta en terreno nuevo — `20_tasa_fp_tres_veces.png`**

> ¿cuánto acierta al detectar árbol? validación en 150 puntos nuevos de Pontevedra: 134 revisados a mano y 16 negativos delegados a ia
>
> la tasa de falsos positivos es del 20,1 %, frente al 33,5 % comarcal. los 16 delegados no tienen comprobación humana independiente

*Alt: dos paneles con puntos e intervalos de confianza: la tasa de falsos
positivos medida tres veces (24,2 %, 33,5 % y 20,1 %) y la sensibilidad
(89,4 %, 89,8 % y 90,1 %), cada medición con su muestra descrita.*

**8 · la máquina (qué salió mal, 1)**

> máquina: 3.197 bloques de láser de 1 km², 5 días en un portátil de 8 años. enchufado: con batería tarda el triple
>
> windows mató el proceso 3 veces y no se perdió un bloque: cada resultado se escribe en un temporal y se renombra al acabar, o un fichero truncado pasa por bueno

**9 · la trampa de escala (qué salió mal, 2)**

> para técnicos, la trampa más cara: un overlay contra un multipolígono provincial disuelto anula el índice espacial. horas de cpu
>
> arreglo: trocear en piezas de una parte. reapareció en 6 scripts. y sentinel-2 va por tile, o deja NaN en 3/4 de la provincia sin avisar

**10 · lo que no funcionó (qué salió mal, 3) — `09_caida_estacional.png`**

> lo que no funcionó, con números: especie desde satélite (auc 0,75 fuera de zona: rechazado). cortas con la serie anual (la sequía de 2026 fabrica espejismos: 0 de 8 reales)
>
> y el catastro: su servidor limita por ip y se quedó en 954 de 3.197 celdas. se declara y se sigue

*Alt: gráfico de barras con la caída estacional de verdor por especie: 0,257 en
roble, 0,009 en pino, −0,033 en eucalipto. La señal existe pero no validó en
píxeles mezclados de 10 m.*

**11 · persistencia y límites del inventario — `05_serie_ndvi.png`**

> ¿cuánto aguanta el inventario de 2010? en Pontevedra, el 98,2 % del rodal en franja no tiene eventos detectados entre 2017 y 2026
>
> respalda usarlo, pero deja un hueco: 2010–2017. la gráfica es del piloto y muestra también cómo la sequía confunde al detector

*Alt: gráfico del piloto de A Paradanta, 2017–2026; la mediana del grupo de eventos de 2018 se desploma
en 2018 y se recupera despacio; la de los persistentes se mantiene plana; en
2026 bajan todas por la sequía.*

**12 · los árboles sueltos — `13_disperso_clasificado.png`**

> 12,9 millones de copas segmentadas. para clasificar el arbolado fuera de inventario, uso solo las zonas donde el modelo supera la validación
>
> ahí marca un 48 % como especie prohibida. el ranking corrige después sus errores. la imagen es un ejemplo del piloto

*Alt: ejemplo del piloto: ortofoto con copas dispersas en faixa, clasificadas
como especie prohibida (círculos rojos) o exenta (verdes).*

**13 · cómo usé la IA**

> la ia también ayudó a anotar: Claude revisó los 150 puntos y delegué en él 16 negativos claros. los otros 134 los revisé a mano
>
> el piloto apoyaba ese uso como prefiltro. esos 16 no tienen comprobación humana independiente: el límite queda declarado

**14 · el aviso**

> el mapa sirve para decidir dónde mirar primero. la inspección comprueba después la especie, el estado actual y las excepciones que contempla la ley
>
> la utilidad está ahí: ayudar a que el tiempo de campo se dedique donde más falta hace

**15 · el repo y la beca**

> código, resultados y anotaciones de validación, en abierto:
> https://github.com/marcosberag/faixas
>
> gracias a las minibecas de @XMihura por apoyar el proyecto y pedir que se contara también lo que salió mal. aquí queda documentado

**16 · lo siguiente y la llamada**

> y una noticia personal: este proyecto me ha llevado a incorporarme al equipo de SilvIA Earth para trabajar en gestión y prevención de incendios
>
> si trabajas en un concello o en el sector forestal, me interesa saber qué necesitarías para usar estos resultados. hablemos
