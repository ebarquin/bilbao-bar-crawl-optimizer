# ADR 0002: Leaflet como mapa inicial

- **Estado:** propuesta
- **Fecha:** 2026-11-11

## Contexto

La primera zona es pequeña y requiere puntos, GeoJSON, popups, un perímetro editable y animación de líneas. No se ha demostrado todavía la necesidad de vector tiles ni de grandes volúmenes.

## Decisión

Usar Leaflet con una librería de edición de geometrías revisada y una capa de ruta basada en GeoJSON. Evaluar MapLibre GL JS solo si aparecen problemas de rendimiento, necesidad de estilos vectoriales o un volumen que justifique WebGL.

## Consecuencias

La implementación inicial es más simple y portable. MapLibre ofrece mejor escalabilidad visual, pero añade complejidad de estilos, workers y fuentes de tiles; no aporta valor demostrado para el primer estudio.

