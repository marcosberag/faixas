# Licencia de los datos

El **código** de este repositorio está bajo Apache-2.0 (ver `LICENSE`).

Los **datos generados por este proyecto** —las anotaciones de validación, las
métricas por parroquia y concello, los rankings y las figuras— están bajo
**Creative Commons Atribución 4.0 Internacional (CC BY 4.0)**:

> https://creativecommons.org/licenses/by/4.0/deed.es

Copyright 2026 Marcos Bermejo Agenjo.

Puedes copiarlos, redistribuirlos, transformarlos y usarlos comercialmente,
siempre que cites la autoría y enlaces a la licencia.

**Cita sugerida:**

> Bermejo Agenjo, M. (2026). *faixas: estimación por LiDAR del arbolado no
> permitido en las franjas de protección contra incendios de Galicia.*
> Financiado por una mini-beca privada (Mini-becas Mihura 2026). CC BY 4.0.
> https://github.com/marcosberag/faixas

Hay un `CITATION.cff` en la raíz con los mismos datos en formato legible por
GitHub y Zenodo.

---

## Datos de entrada: de dónde salen y qué obligan

Ninguna fuente de entrada impone copyleft, así que la combinación anterior es
compatible. Pero **todas obligan a atribuir**, y la atribución no es decorativa:
viaja con cualquier figura, mapa o cifra que se publique.

| Fuente | Titular | Licencia / régimen | Qué obliga |
|---|---|---|---|
| **LiDAR PNOA 3ª cobertura** | IGN / CNIG | CC BY 4.0 | Citar «© Instituto Geográfico Nacional de España» en cualquier imagen derivada |
| **Ortofoto PNOA (actual e histórica)** | IGN / CNIG | CC BY 4.0 | Ídem. Se usa en los chips de validación, el visor y los dossiers |
| **Franjas de protección (PBA)** | Xunta de Galicia | Reutilización de información del sector público (Ley 37/2007, RD 1495/2011) | Citar origen y fecha de actualización; no desnaturalizar el sentido del dato |
| **IFN4 2010, especies arbóreas** | Xunta de Galicia / MITECO | Ídem | Ídem |
| **Sentinel-2 (Copernicus)** | Comisión Europea / ESA | Datos Copernicus, libres y abiertos (Reg. UE 1159/2013) | Citar «Contiene datos Copernicus modificados [2017–2026]» |
| **Huellas de edificios** | Dirección General del Catastro | Reutilización libre, INSPIRE | Citar «Dirección General del Catastro» |

## Lo que NO deriva de ninguna fuente pública

Las **anotaciones de validación** (`datos/procesado/validacion*/anotacion*.csv`)
son obra original: ~900 puntos fotointerpretados a mano, con retest ciego y
acuerdo intra-anotador medido. No se derivan de ningún dato de terceros y no
están sujetas a las condiciones de arriba. Son lo que permite publicar una tasa
de falsos positivos en vez de una estimación sin garantía.

## Advertencia sobre el uso

Los resultados son un **indicador de riesgo para priorizar inspección**, no una
determinación de incumplimiento legal. La Ley 3/2007 contempla excepciones que
ningún sensor evalúa, y el producto lleva una tasa de falsos positivos medida y
publicada. Cualquier reutilización que presente estas cifras como una lista de
infractores desnaturaliza el dato y contradice el diseño del proyecto.
