# Visor publico de Pontevedra

URL: <https://marcosberag.github.io/faixas/>

GitHub Pages sirve exclusivamente `salidas/visor/pontevedra`, exportado a la raiz
de la rama `gh-pages`. El codigo y las fuentes se conservan en `main`. No necesita
Python, credenciales ni un servidor de datos en produccion.

Leaflet 1.9.4 se distribuye localmente en `vendor/leaflet`, con su licencia BSD
y sus imagenes, para que la carga del mapa no dependa de un CDN externo. Los
fondos cartograficos siguen solicitandose a OpenStreetMap o al IGN.
El HTML incluye una version de contenido en las URLs del CSS y JavaScript para
evitar que el navegador reutilice estilos anteriores despues de un despliegue.

## Regenerar y publicar

Desde la raiz del repositorio, con los derivados geoespaciales disponibles:

```powershell
python scripts/puntos_inspeccion.py --zona pontevedra
python scripts/visor.py --zona pontevedra
python scripts/verifica_visor.py
```

Revisar el visor servido por HTTP, incluyendo una pantalla pequena, y guardar
los cambios revisados en un commit. Despues:

```powershell
git push origin main
./scripts/publica_visor.ps1
```

El script usa `git subtree split` para publicar solo los archivos estaticos.
Rechaza cambios del visor sin commit y nunca fuerza la rama remota. Pages debe
estar configurado con origen **Deploy from a branch**, rama **gh-pages**, carpeta
**/ (root)**. Las actualizaciones se publican explicitamente con el script; un
cambio en `main` por si solo no actualiza la web.

## Datos y limites

El mapa muestra las franjas oficiales, no los limites administrativos de las
parroquias. Consulta las 563 parroquias de 54 concellos con resultados en la capa
disponible. No cubre lugares sin franja publicada.

Las cotas y el orden se copian del ranking validado, sin recalcular el modelo.
Los puntos y las manchas se generan para esta zona, con ficheros independientes
del piloto. El detalle se descarga por concello al llegar al zoom 13; las
geometrias se simplifican para visualizacion. La atribucion municipal de las
manchas se decide por superficie, aunque un ancla pueda quedar al otro lado
del limite. Las superficies de los puntos pueden solaparse y no son sumables.

Se conservan los avisos del producto: indicador para priorizar inspeccion,
LiDAR de 2024, IFN de 2010, ausencia de evento detectado en 2017–2026 (sin
comprobar 2010–2017), clasificador solo donde valida, filtro provincial de
Catastro incompleto, especie de >35 m inferida por altura y cotas que no son
un IC95 conjunto. No se publican eventos del detector como cortas confirmadas.

El piloto sigue generandose con `python scripts/visor.py`, en su ruta anterior.
