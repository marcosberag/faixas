# Hilo Pontevedra — el entregable de la minibeca (16-09-2026)

Segundo hilo. El primero (30-08, 7 tweets, la comarca) cerraba con «Pontevedra
entera, las cifras cuando pasen su validación»: este es ese hilo. Es también el
entregable de las Mini-becas Mihura 2026, cuya condición era compartir en
público el output, qué se probó, qué funcionó y **qué salió mal**. Por eso los
tweets 8 a 10 son fallos con números, no relleno.

Estilo del primer hilo: minúsculas, topónimos con mayúscula, sin rayas ni punto
y coma. Todos los tweets ≤ 280 según `scripts/cuenta_tweets.py` (conteo estilo
X: emoji = 2, URL = 23).

**Antes de publicar:**

- El repo tiene que estar **público** antes del tweet 15, y el enlace comprobado
  en una ventana de incógnito.
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

> en Pontevedra hay entre 4.770 y 8.141 hectáreas de franja con eucaliptos, pinos o acacias a menos de 50 m de las casas, donde la ley los prohíbe
>
> nadie tenía ese mapa. lo he hecho para la provincia entera con datos públicos, un portátil de 8 años y el error medido 🧵

*Alt: mapa de la provincia de Pontevedra dibujada por sus miles de franjas de
protección, coloreadas de claro a rojo oscuro según las hectáreas de arbolado
prohibido estimadas en cada parroquia. Un recuadro negro marca la comarca de
A Paradanta, el primer hilo. Rotulados Ponteareas, A Estrada y Salvaterra.*

**2 · para quien llega nuevo — `02_zoom_franja.jpg`**

> para quien llega nuevo: en Galicia, por ley, a menos de 50 m de una casa no puede haber eucaliptos, pinos ni acacias, los que convierten un fuego en catástrofe
>
> la Xunta publica dónde rige la norma. si se cumple lo miran inspectores a pie. este mapa dice por dónde empezar

*Alt: ortofoto de aldeas gallegas con las franjas de 50 m dibujadas en naranja
rodeando las casas, muchas llenas de arbolado.*

**3 · cómo, en un tweet — `14_sat_lidar_clasificacion.png` + cita del hilo anterior**

> cómo: el láser aéreo del ign, público y gratis, da la altura de cada árbol. el inventario forestal y un clasificador entrenado con él ponen la especie. los tejados se quitan con el catastro
>
> el método, paso a paso y con sus tasas de error, lo conté en el hilo de la comarca 👇

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

> por parroquia, la primera es O Hío, en Cangas, en plena costa: entre 46 y 76 hectáreas de franja con arbolado prohibido
>
> cada barra es una horquilla, no un número. la horquilla no es una disculpa: es la parte del error que se pudo medir, y se declara

*Alt: gráfico de barras horizontales con las diez parroquias prioritarias de la
provincia, cada una con su concello y el intervalo de hectáreas.*

**6 · la misma curva — `18_curva_concentracion.png`**

> lo que más me sorprendió: en la comarca, la mitad del problema estaba en el 22 % de las parroquias. en la provincia, 14 veces mayor, también en el 22 %
>
> la misma curva. quien inspeccione en este orden encuentra la mitad del problema visitando menos de 1 parroquia de cada 4

*Alt: dos curvas de concentración casi superpuestas, naranja la comarca y azul la
provincia: porcentaje de parroquias frente a porcentaje del arbolado prohibido
acumulado. Un punto en cada una marca el 50 % del problema en el 22 % de las
parroquias. Una diagonal punteada indica el reparto uniforme.*

**7 · cuánto acierta en terreno nuevo — `20_tasa_fp_tres_veces.png`**

> ¿cuánto acierta en terreno nuevo? 150 puntos más anotados a ciegas sobre ortofoto, en sitios que el modelo no había visto, costa incluida
>
> de cada 5 avisos de árbol, 1 no lo es (20,1 %). en la comarca era 1 de cada 3. y de las copas de más de 35 m, 9 de 9 eran árboles

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

**11 · el inventario de 2010 aguanta — `05_serie_ndvi.png`**

> el inventario de especies es de 2010. ¿sigue valiendo en 2026? diez veranos de satélite sobre 11.472 rodales: el 98 % del monte en franja no ha cambiado
>
> y el detector volvió a encontrar solo los incendios de octubre de 2017: 53 rodales quemados, sin que nadie se lo dijera

*Alt: gráfico de líneas 2017–2026; la mediana de los rodales quemados se desploma
en 2018 y se recupera despacio; la de los persistentes se mantiene plana; en
2026 bajan todas por la sequía.*

**12 · los árboles sueltos — `13_disperso_clasificado.png`**

> árboles sueltos, que ningún inventario cartografía: 12,9 M de copas y un clasificador con 24.000 etiquetas gratis del inventario. auc 0,87 con zonas enteras fuera
>
> solo se aplica donde valida. fuera de la comarca el arbolado suelto es menos eucaliptal: 48 % prohibido, no 60 %

*Alt: ortofoto con decenas de círculos de colores sobre árboles sueltos: rojo
eucalipto, naranja pino, verde frondosa exenta.*

**13 · cómo usé la IA**

> cómo usé claude: programar, sí, pero lo más útil fue de segundo anotador. clasificó los 150 puntos a ciegas y sus «no» claros me los ahorré: 16
>
> medido antes en 48 chips: cuando falla, sobremarca árbol, nunca al revés. el lado seguro. no sustituye al humano, le quita trabajo

**14 · el aviso**

> importante: esto es triaje, no una lista de infractores. la ley admite excepciones que ningún sensor evalúa, y el matorral no se mide
>
> el mapa ordena dónde mirar primero. la palabra la sigue teniendo el inspector

**15 · el repo y la beca**

> código, anotaciones de validación y memoria, abiertos y reproducibles de punta a punta: github.com/marcosberag/faixas
>
> esto salió de las minibecas de @XMihura: un mes de claude max a cambio de contar qué funcionó y qué no. gracias

**16 · lo siguiente y la llamada**

> lo siguiente: A Coruña ya está preparada, 5.926 bloques. Galicia entera cabe en 3 semanas de portátil
>
> si trabajas en prevención de incendios, en un concello o en la Xunta y esto te sirve: hablemos. los 54 concellos están en el repo con sus cotas, parroquia a parroquia
