# Bilbao Bar Crawl Optimizer

Investigación reproducible sobre la ruta peatonal necesaria para visitar establecimientos del Casco Viejo de Bilbao.

La aplicación compara varios algoritmos sobre una red peatonal real de OpenStreetMap. No presenta una aproximación como óptimo global: los resultados se describen como la mejor solución encontrada bajo el escenario y los datos disponibles.

## Qué incluye

- 157 establecimientos dentro del perímetro definitivo de Siete Calles, Plaza Nueva, El Arenal y calles intermedias.
- Red peatonal OSM con 5.258 nodos, 14.526 aristas y un nodo virtual independiente por establecimiento.
- Matriz reproducible de distancias y geometrías peatonales.
- Comparación de Random, Nearest Neighbor, multi-start, 2-opt y OR-Tools.
- Simulación de 4,5 km/h y 15 minutos por establecimiento.
- Aplicación estática con mapa, comparación y animación de rutas.

## Ejecutar la aplicación

```bash
python3 -m http.server 8000 --directory .
```

Abre <http://localhost:8000/dist/>. La aplicación consume artefactos locales y no realiza consultas externas al abrirse.

## Regenerar el experimento

```bash
PATH=/opt/homebrew/bin:$PATH .venv/bin/python scripts/build_pedestrian_network.py --source osm-map
PATH=/opt/homebrew/bin:$PATH .venv/bin/python scripts/split_venue_nodes.py
PATH=/opt/homebrew/bin:$PATH .venv/bin/python scripts/build_distance_matrix.py
PATH=/opt/homebrew/bin:$PATH .venv/bin/python scripts/compare_optimizers.py
PATH=/opt/homebrew/bin:$PATH .venv/bin/python scripts/build_route_simulations.py
```

El pipeline separa adquisición, normalización, red geográfica, matriz de costes, optimización y presentación. Los resultados se guardan en `data/processed/`.

## Documentación y reproducibilidad

- Arquitectura y decisiones: [`docs/`](docs/)
- Datos activos: [`data/study-areas/`](data/study-areas/), [`data/processed/`](data/processed/)
- Scripts reproducibles: [`scripts/`](scripts/)
- Cuaderno de análisis: [`notebooks/`](notebooks/)

## Limitaciones

Los establecimientos proceden de OpenStreetMap y se utilizan como dataset realista para una prueba práctica de algoritmos; no se pretende construir un inventario exhaustivo ni validar cada entrada comercial. La proyección independiente sobre la arista peatonal más cercana evita compartir nodos artificialmente. Los tiempos son estimaciones: no incorporan horarios, esperas ni tiempos reales de consumo.

## Atribución

Datos © OpenStreetMap contributors, disponibles bajo la licencia ODbL. Las consultas se almacenan localmente para limitar peticiones y permitir la reproducción del estudio.
