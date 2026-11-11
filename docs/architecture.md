# Bilbao Bar Crawl Optimizer — Arquitectura propuesta

Estado: propuesta para revisión antes de la Fase 1.

## Decisión resumida

El proyecto se separará en dos capas:

1. **Pipeline reproducible offline (Python):** adquisición de OSM/Overpass, validación y normalización de establecimientos, construcción de la red peatonal, asociación bar-red, matriz de costes, optimización y exportación de artefactos.
2. **Aplicación estática (TypeScript):** carga de GeoJSON/JSON versionados, mapa, controles, comparación de rutas y animación. No calculará rutas ni dependerá de un backend para la primera publicación.

La separación evita repetir consultas externas al abrir la web y permite auditar cada resultado.

## Estructura propuesta

```text
data/
  raw/                 respuestas Overpass y descargas originales
  processed/           GeoJSON, grafos y matrices generadas
  study-areas/         perímetros editables por zona
src/pipeline/          adquisición, geografía, red y optimización
src/web/               aplicación del mapa y animación
tests/                 pruebas unitarias y fixtures pequeños
docs/                  metodología, ADRs, calidad y resultados
```

El pipeline usará Python con OSMnx, NetworkX, GeoPandas/Shapely y OR-Tools. Se recomienda gestionar dependencias con `uv` y fijarlas en `uv.lock`. La web usará Vite + TypeScript + Leaflet; Leaflet es suficiente para el primer perímetro y simplifica GeoJSON, popups y edición. MapLibre queda como alternativa si el volumen de datos o la necesidad de estilos/vector tiles lo justifican.

## Flujo de datos

El perímetro se mantendrá como GeoJSON WGS84, editado manualmente y versionado. Overpass consultará objetos `amenity` seleccionados dentro de ese polígono; cada registro conservará `osm_type`, `osm_id`, consulta, fecha, etiquetas originales y categoría normalizada. Las respuestas se cachearán y se respetará la política del servidor.

La red se descargará con margen alrededor del perímetro, se modelará como `MultiDiGraph` peatonal y se proyectará a un CRS métrico local para buffers y distancias. Cada establecimiento tendrá un nodo de acceso, método de asociación y bandera de revisión manual. NetworkX/OSMnx calculará caminos mínimos y geometrías; la matriz almacenará costes, rutas reconstruibles, versión del grafo y hash de entradas.

## Formulación inicial

Propuesta para aprobar: recorrido **abierto**, con inicio configurable y por defecto Plaza Nueva; final libre. Se reportará además un escenario cerrado como sensibilidad. Si una arista dirigida no tiene retorno equivalente, la matriz será asimétrica. NN, multi-start NN, 2-opt y OR-Tools recibirán exactamente la misma matriz. Los resultados se describirán como “mejor solución encontrada” salvo que exista una cota o demostración de optimalidad.

## Calidad, reproducibilidad y límites

Cada ejecución guardará configuración, fecha, versiones, semillas, fuentes, conteos, desconectados, duplicados y errores. Las rutas no se unirán con líneas rectas: se reconstruirán desde aristas peatonales. Los artefactos publicados incluirán atribución OpenStreetMap/ODbL y limitaciones de cobertura, accesos y horarios.

## Fuentes técnicas consultadas

- [Overpass API — OpenStreetMap Wiki](https://wiki.openstreetmap.org/wiki/Overpass_API): caché, límites, identificación del cliente y uso responsable.
- [OSMnx — Getting Started](https://osmnx.readthedocs.io/en/stable/getting-started.html): redes por modo, nodos cercanos, rutas y persistencia del grafo.
- [NetworkX — Shortest Paths](https://networkx.org/documentation/latest/reference/algorithms/shortest_paths.html): caminos mínimos ponderados en grafos dirigidos.
- [OR-Tools — Vehicle Routing](https://developers.google.com/optimization/routing): TSP/VRP, heurísticas y diferencia entre solución factible y óptimo garantizado.
- [Leaflet API reference](https://leafletjs.com/reference) y [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/): alternativas de visualización evaluadas.

