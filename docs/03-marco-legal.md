# Marco legal: qué obliga exactamente la ley

Verificado el 16 de agosto de 2026 contra el texto consolidado de la
[Ley 3/2007, de 9 de abril, de prevención y defensa contra los incendios forestales de
Galicia](https://www.boe.es/buscar/act.php?id=BOE-A-2007-10022) y el
[listado oficial de especies](https://hoxe.vigo.org/pdf/medioambiente/rede_faixas/listado_especies_cas.pdf)
que publican los concellos.

Este documento existe porque el proyecto mide *cumplimiento de una norma*. Si la norma
está mal entendida, la métrica no vale nada.

---

## 1. La obligación

**Artículo 21 — "Redes secundarias de fajas de gestión de biomasa"**

Es el artículo que crea la franja de 50 m alrededor de núcleos y edificaciones. Impone
dos obligaciones distintas, y conviene no mezclarlas:

| | Qué obliga | Sobre qué vegetación |
|---|---|---|
| **Gestionar la biomasa** | art. 21.1 | Toda la vegetación: desbroce, romper la continuidad del combustible |
| **Retirar arbolado** | art. 21.2 | Solo las especies de la disposición adicional tercera |

Literal del art. 21.2:

> "Con carácter general, en la misma franja de 50 metros mencionada en el número
> anterior no podrá haber árboles de las especies señaladas en la disposición adicional
> tercera."

**Nuestro proyecto solo mide la segunda**, y ni siquiera entera. Ver limitaciones abajo.

---

## 2. Las especies (disposición adicional tercera)

No es un anexo, es una disposición adicional — importa para citarla bien. Contiene
**15 taxones**, y solo 7 son arbóreos:

### Arbóreas — las que nos interesan

| Especie | Nombre común |
|---|---|
| *Pinus pinaster* | pino gallego, pino del país |
| *Pinus sylvestris* | pino silvestre |
| *Pinus radiata* | pino de Monterrey |
| *Pseudotsuga menziesii* | pino de Oregón |
| *Acacia dealbata* | mimosa |
| *Acacia melanoxylum* | acacia negra |
| *Eucalyptus* spp | eucalipto |

### Matorral y herbáceas — fuera de nuestro alcance

*Calluna vulgaris* (brecina), *Chamaespartium tridentatum* (carquesa), *Cytisus* spp
(retama), *Erica* spp (brezo), *Genista* spp (retama, piorno), *Pteridium aquilinum*
(helecho), *Rubus* spp (zarza), *Ulex europaeus* (tojo).

Que el matorral esté en la lista confirma que la ley sí lo regula. Lo dejamos fuera por
motivos técnicos (ver [plan de trabajo](01-plan-de-trabajo.md)), no porque no cuente.

---

## 3. Los dos apartados que condicionan todo el proyecto

### 3.2 — Excepciones que el LiDAR no puede ver

> "En todo caso, podrán conservarse árboles de las especies señaladas en el número
> anterior [...] en caso de tratarse de árboles singulares o aquellos que cumplan
> funciones ornamentales o que se emplacen en zonas recreativas (siempre que se mantenga
> una discontinuidad horizontal y vertical del combustible) o se hallen aislados y no
> supongan un riesgo para la propagación de incendios forestales."

Un pino puede estar legalmente dentro de la franja si es singular, ornamental, está en
zona recreativa, o está aislado sin riesgo de propagación. **Ninguna de esas cuatro
condiciones es observable desde una nube de puntos.** El aislamiento es parcialmente
inferible (densidad de copas alrededor), las otras tres no.

Esto es un argumento fuerte a favor del framing de triaje: la ley misma admite
excepciones que nuestro método no puede evaluar.

### 3.3 — La exención que nos obliga a clasificar especie

> "No serán de aplicación las obligaciones de gestión de la biomasa establecidas en la
> presente ley a las frondosas no incluidas en el listado del número 1."

**Las frondosas no listadas están exentas.** Castaños, robles, abedules, fresnos: pueden
quedarse dentro de la franja legalmente y sin límite.

Consecuencia directa: **"arbolado por encima de un umbral de altura" NO es un indicador
de incumplimiento.** Un castañar dentro de la franja da exactamente la misma señal en un
CHM que un pinar, y uno es legal y el otro no. En Galicia, con presencia real de
castaño y roble en el entorno de los núcleos, el sesgo no es marginal.

Esto reabre una cuestión que `CLAUDE.md` daba por posiblemente aplazable. Ver el
[plan de trabajo](01-plan-de-trabajo.md), sección "clasificación de especie".

---

## 4. Qué NO dice la ley (y conviene no afirmar en público)

- No prohíbe "el arbolado" en general. Prohíbe siete taxones concretos.
- No prohíbe los castaños ni los robles. Los exime expresamente.
- La lista incluye mimosa, acacia negra y pino de Oregón, no solo "pinos y eucaliptos".
  Decir "pinos y eucaliptos" es una simplificación defendible en divulgación (son los
  dominantes en Galicia) pero incompleta en un documento técnico.
- La franja aplica solo donde hay plan municipal de prevención aprobado. La capa de la
  Xunta solo trae esos concellos.

---

## 5. Escalabilidad fuera de Galicia

Verificado el 17 de agosto de 2026 sobre tres comunidades. **No es extrapolable a las
diecisiete**: lo que sigue vale para las que se han mirado.

La pregunta "¿esto se puede llevar a toda España?" tiene dos mitades con respuestas
opuestas.

### La mitad que sí escala

El **LiDAR del PNOA es nacional**: mismo programa, mismo formato LAZ, misma licencia
CC-BY, cobertura de todo el Estado. El pipeline técnico —SMRF, MDT, MDS, CHM— no cambia
ni una línea al cruzar una frontera autonómica. Esa mitad del problema está resuelta de
serie.

### La mitad que no

La obligación es **competencia autonómica**, y no varía solo en la cifra de metros:
varía en qué se pregunta.

| | Galicia | Cataluña | Madrid |
|---|---|---|---|
| Norma | [Ley 3/2007](https://www.boe.es/buscar/act.php?id=BOE-A-2007-10022) | [Llei 5/2003](https://territori.gencat.cat/web/.content/home/06_territori_i_urbanisme/05_planejament_urbanistic/Planejament_general/marc_legal/legislacio_basica_i_sectorial/llei_5_2003.pdf) | [Ley 16/1995](https://www.boe.es/buscar/act.php?id=BOE-A-1995-19108) |
| Anchura | 50 m | 25 m (art. 3.1.a) | **no hay franja perimetral** |
| Ámbito | Todos los núcleos y viviendas | Solo urbanizaciones **sin continuidad con la trama urbana** a < 500 m de forestal, y edificaciones aisladas en monte (art. 1) | — |
| Criterio sobre el arbolado | **Eliminar** 7 especies concretas | **Aclarar** la masa arbórea, sin distinguir especie | — |
| Quién publica el mapa | La Xunta, capa autonómica única | **Cada ayuntamiento**, en pleno (art. 2) | Nadie |

Tres consecuencias, de menos a más grave:

1. **La anchura es lo de menos.** Cambiar 50 por 25 es un parámetro.
2. **El criterio cambia la métrica de raíz.** En Galicia la pregunta es *"¿hay un pino
   aquí?"* y necesita clasificación de especie. En Cataluña es *"¿cuánta copa hay?"* y
   necesita fracción de cabida cubierta o separación entre copas. Son dos indicadores
   distintos, no dos umbrales del mismo.
3. **Sin capa de obligación no hay producto.** Es el cuello de botella real. En Cataluña
   la ley es perfectamente concreta y aun así no hay nada que cruzar, porque la
   delimitación está atomizada en cientos de planos municipales. En Madrid no existe
   siquiera la obligación que cartografiar.

### La salida parcial

La geometría **sí** es reconstruible en cualquier sitio: Catastro es nacional, y el
buffer de la anchura que toque alrededor de las edificaciones se genera por cuenta
propia. Lo que no se reconstruye es la norma — qué anchura, qué criterio, qué
excepciones, y sobre todo qué edificaciones están afectadas, que en Cataluña depende de
un acto administrativo municipal.

**Conclusión para comunicar:** el método es replicable; el producto no. "Llevarlo a toda
España" son diecisiete problemas legales y uno solo técnico. Prometer el método está
justificado; prometer el mapa nacional, no.

---

## 6. Cómo se verifica hoy

Inspección presencial, parcela por parcela. La Xunta ha duplicado la plantilla de
inspección en 2026. El procedimiento sancionador y de ejecución subsidiaria está
regulado; existe notificación por edictos en el DOG a titulares desconocidos.

La capa de obligación está publicada. **La capa de cumplimiento no existe.** Eso es lo
que este proyecto intenta estimar.
