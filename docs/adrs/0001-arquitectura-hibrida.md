# ADR 0001: Pipeline offline y frontend estático

- **Estado:** propuesta
- **Fecha:** 2026-11-11

## Contexto

La investigación necesita datos trazables, cálculos repetibles y una demo pública sencilla. Consultar Overpass, construir la red o ejecutar optimización desde el navegador introduciría latencia, límites de servicio y resultados difíciles de reproducir.

## Decisión

Separar un pipeline Python offline de una aplicación TypeScript estática. El pipeline publicará artefactos versionados; la web solo leerá esos artefactos y animará geometrías ya calculadas. El alojamiento podrá ser estático, inicialmente GitHub Pages u otro proveedor equivalente.

## Consecuencias

Se facilita la auditoría y no se necesita servidor permanente. A cambio, cambiar el perímetro o los parámetros requiere regenerar y publicar artefactos. La ejecución de algoritmos en navegador queda como experimento posterior, no como requisito de la primera versión.

