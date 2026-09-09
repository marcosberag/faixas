# Qué es esto, en cristiano

Documento de entrada. Explica el problema, qué es el LiDAR y qué significa cada sigla
que aparece en el resto del repo. Si vienes de fuera del proyecto, empieza aquí.

---

## El problema en cuatro frases

En Galicia, la ley obliga a mantener una franja de 50 m alrededor de cada casa y cada
núcleo de población sin determinadas especies de árboles (pinos, eucaliptos, acacias).
La Xunta publica un mapa de **dónde** existe esa obligación. Nadie publica un mapa de
**dónde se cumple**. Hoy se comprueba mandando inspectores a pie, parcela por parcela.

Este proyecto intenta estimar el segundo mapa a partir de datos públicos, para que la
inspección pueda priorizar dónde ir.

---

## Qué es el LiDAR

**LiDAR** = *Light Detection and Ranging*. Un escáner láser montado en una avioneta.
Dispara pulsos de luz hacia el suelo y cronometra cuánto tarda cada uno en volver. Como
la velocidad de la luz se conoce, el tiempo da la distancia; combinado con la posición
GPS y la orientación del avión, cada pulso se convierte en un punto con coordenadas
(x, y, z). El resultado es una **nube de puntos**: millones de coordenadas 3D que
describen la superficie del terreno y todo lo que hay encima.

### La idea clave: los retornos múltiples

Esto es lo que hace al LiDAR útil para vegetación y conviene entenderlo bien.

Un pulso láser no es infinitamente fino: al llegar a un árbol, **parte** de la energía
rebota en las hojas altas y **parte** se cuela por los huecos del follaje. Lo que se cuela
sigue bajando, y puede rebotar en una rama a media altura, y lo que quede puede llegar
hasta el suelo. Un solo disparo produce así **varios retornos** a distintas alturas:

```
        pulso
          |
          v
   ~~~~~~~~~~~~~~   <- 1er retorno: copa del árbol      (z = 18 m)
      ~~~~~~~~      <- 2º  retorno: rama intermedia     (z = 11 m)
   ______________   <- último retorno: suelo            (z =  3 m)
```

De ahí sale todo lo demás. Los **primeros retornos** dibujan la superficie de arriba
(copas, tejados). Los **últimos retornos**, allí donde el láser logró colarse, dibujan
el suelo real **por debajo del arbolado**. Por eso el LiDAR puede medir la altura de los
árboles: ve la copa y ve el suelo bajo la copa, y resta.

Una foto aérea no puede hacer esto. Ve las copas y punto: no sabe si ese verde tiene dos
metros o veinte.

### Densidad de puntos

Se mide en **puntos por metro cuadrado** (pts/m²). El PNOA de tercera cobertura da
**5 pts/m²** en Galicia: unos 5 puntos por cada baldosa de 1×1 m.

Es suficiente para medir altura de arbolado con solvencia. Es escaso para dibujar árboles
individuales, y claramente insuficiente para medir matorral bajo — con 5 puntos por metro
no distingues con fiabilidad un tojo de 20 cm del propio suelo.

### Clasificación

Cada punto de la nube lleva una etiqueta: suelo, vegetación, edificio, agua, ruido... La
clasificación viene hecha de fábrica, pero con distinta calidad según el nivel:

- **NPC01**: clasificación automática provisional. Es lo publicado hoy para Galicia.
- **NPC02**: clasificación revisada y depurada.

Como solo tenemos NPC01, **no nos fiamos de las etiquetas y rehacemos la clasificación
de suelo por nuestra cuenta**. De ahí que necesitemos SMRF (abajo).

---

## Los tres modelos: MDT, MDS, CHM

Aquí está el corazón del método. Son tres rásteres (imágenes donde cada píxel guarda un
número, en este caso una altura en metros).

**MDT — Modelo Digital del Terreno.** El suelo desnudo, como si hubiéramos afeitado el
paisaje. Se construye interpolando solo los puntos clasificados como suelo. En inglés,
DTM.

**MDS — Modelo Digital de Superficies.** Lo más alto que hay en cada punto: copas,
tejados, cables. Se construye con los primeros retornos. En inglés, DSM.

**CHM — Canopy Height Model**, modelo de altura de copa. La resta:

```
CHM = MDS - MDT
```

Y eso es exactamente la altura de la vegetación sobre el suelo, punto a punto. Un píxel
con CHM = 0,2 m es rasante; uno con CHM = 15 m tiene un árbol de quince metros encima.

La gracia de restar es que **elimina el relieve**. En una ladera con 30 % de pendiente,
las alturas absolutas no dicen nada; la diferencia entre superficie y terreno sí.

**SMRF — Simple Morphological Filter.** El algoritmo que usamos para decidir qué puntos
son suelo. Funciona por morfología matemática: aplica una "apertura" sobre la nube con
ventanas de tamaño creciente y va descartando lo que sobresale demasiado respecto a su
entorno. Un árbol sobresale; una loma suave no. Es el estándar razonable para terreno
forestal en pendiente y está implementado en PDAL.

---

## Glosario de siglas

### Datos y organismos

| Sigla | Qué es |
|---|---|
| **IGN** | Instituto Geográfico Nacional. Publica el LiDAR y las ortofotos. |
| **CNIG** | Centro Nacional de Información Geográfica. El brazo del IGN que distribuye los ficheros. |
| **PNOA** | Plan Nacional de Ortofotografía Aérea. Programa que produce tanto las ortofotos como el LiDAR. |
| **PNOA-MA** | PNOA "máxima actualidad": mosaico con la ortofoto más reciente disponible de cada zona. |
| **Xunta / IDEG** | Xunta de Galicia y su Infraestructura de Datos Espaciais. Publica la capa de franjas. |
| **DOG** | Diario Oficial de Galicia. |

### Formatos y protocolos

| Sigla | Qué es |
|---|---|
| **LAS / LAZ** | Formato estándar de nubes de puntos LiDAR. LAZ es LAS comprimido. |
| **WMS** | *Web Map Service*. Servicio que devuelve una **imagen** de un mapa para un recuadro dado. No da datos, da píxeles. |
| **WFS** | *Web Feature Service*. Como el WMS pero devuelve **geometrías** (los polígonos de verdad). |
| **ArcGIS REST** | API propietaria de Esri. Es lo que sirve la capa de franjas de la Xunta. |
| **GeoJSON / Esri JSON** | Dos formas de escribir geometrías en JSON. La Xunta habla la segunda. |
| **RGBI** | Red, Green, Blue, Infrared. Las cuatro bandas de color del PNOA. El infrarrojo es informativo para vegetación. |

### Coordenadas

| Sigla | Qué es |
|---|---|
| **CRS** | *Coordinate Reference System*. El sistema en que se expresan las coordenadas. |
| **EPSG:25829** | Nuestro CRS: ETRS89 / UTM zona 29N. Coordenadas en **metros**, no en grados. |
| **ETRS89** | El datum europeo. Define dónde está el origen y la forma del elipsoide. |
| **UTM 29N** | Proyección: aplana el trozo de globo entre 12°O y 6°O. Galicia cae aquí. |
| **EPSG:4326** | El de toda la vida, latitud/longitud en grados (WGS84). **No** lo usamos: en grados no se pueden medir áreas ni distancias directamente. |

Trabajar todo en 25829 significa que un buffer de 50 m es literalmente 50 unidades, y que
un área en m² sale de contar píxeles. Sin reproyecciones y sin sorpresas.

### Herramientas

| Sigla | Qué es |
|---|---|
| **PDAL** | *Point Data Abstraction Library*. La navaja suiza de nubes de puntos: lee LAZ, filtra, clasifica, rasteriza. |
| **GDAL** | La librería que lee y escribe cualquier formato ráster/vectorial. Debajo de casi todo. |
| **rasterio** | Envoltorio pythónico de GDAL para rásteres. |
| **GeoPandas** | Pandas con geometrías. Para los polígonos de las franjas. |

### Métricas forestales

| Término | Qué es |
|---|---|
| **FCC** | Fracción de Cabida Cubierta. Porcentaje de suelo cubierto por copa vista desde arriba. |
| **Segmentación de copa** | Separar la masa de vegetación en árboles individuales. A 5 pts/m² es dudoso; por confirmar. |
| **Umbral de altura** | El valor de CHM a partir del cual decimos "esto es un árbol". A calibrar, no fijado a priori. |

---

## Qué vamos a hacer en realidad

Sin jerga, por orden:

1. **Bajar los polígonos** de las franjas de 50 m de la Xunta para cuatro concellos de
   prueba. *(Bloqueado: ver [walkthrough](02-walkthrough.md). El servicio no los suelta.)*
2. **Bajar el LiDAR** del IGN de esa misma zona, en bloques de 1×1 km.
3. Por cada bloque: **decidir qué puntos son suelo** (SMRF), construir el **MDT**,
   construir el **MDS**, y restar para obtener el **CHM**.
4. **Recortar** el CHM con los polígonos de las franjas.
5. **Contar**: cuántos metros cuadrados dentro de cada franja tienen vegetación por
   encima del umbral de altura.
6. **Agregar** por parroquia y por concello, y ordenar.
7. **Validar a mano** contra ortofoto sobre una muestra aleatoria, y publicar la tasa de
   falsos positivos que salga.

El resultado es un **ranking de dónde mirar primero**, no una lista de infractores.

## Qué NO vamos a hacer

- **No medimos matorral.** El LiDAR es una foto fija y el matorral rebrota entre vuelos;
  además a 5 pts/m² no se discrimina bien. La ley sí lo regula: nos dejamos fuera una
  parte real de la obligación.
- **No bajamos a parcela.** La capa oficial no trae referencia catastral y la unidad
  mínima es la parroquia. Atribuir a un propietario concreto sería otro proyecto, y con
  responsabilidad legal distinta.
- **No afirmamos incumplimiento.** La ley admite excepciones que el LiDAR no puede ver
  (árbol singular, ornamental, aislado sin riesgo) y exime a las frondosas no listadas.
  Ver [marco legal](03-marco-legal.md).
- **No detectamos especie todavía**, y eso es un problema mayor de lo que parecía. Un
  castañar es legal dentro de la franja y da la misma señal en el CHM que un pinar.
