# Fase 0 — Plan de implementación y criterios de aceptación

## Orden de trabajo

1. **Base del proyecto:** crear entornos Python y web, scripts reproducibles y CI mínima.
2. **Perímetro:** dibujar y revisar el GeoJSON de Siete Calles, Plaza Nueva y Arenal; excluir Atxuri; añadir un informe de alcance.
3. **Establecimientos:** implementar consulta Overpass cacheada, normalización, deduplicación, GeoJSON y reporte de cobertura.
4. **Red:** descargar red peatonal con margen, validar conectividad, proyectar a CRS métrico, asociar accesos y generar rutas de prueba.
5. **Matriz:** calcular distancias/tiempos, guardar geometrías y validar desconectados, asimetrías y valores imposibles.
6. **Optimización:** implementar referencia aleatoria con semillas, NN, multi-start NN, 2-opt y OR-Tools; evaluar con el mismo dataset.
7. **Simulación y exportación:** añadir velocidad y tiempo fijo configurables, manifest de resultados y artefactos para la web.
8. **Web:** mostrar perímetro y establecimientos, luego rutas, controles y animación; publicar resultados precalculados.

## Criterios de aceptación transversal

- Una ejecución desde cero reproduce artefactos con la misma configuración y semilla.
- Toda entidad conserva procedencia OSM, identificador y fecha de captura.
- Las rutas visualizadas son geometrías de la red peatonal, no segmentos euclídeos.
- Los casos desconectados, duplicados y accesos aproximados aparecen en informes.
- La comparación incluye distancia, tiempo, duración del algoritmo y variabilidad.
- La web no realiza consultas masivas ni cálculos externos al abrirse.
- README y metodología permiten repetir el estudio; la atribución y limitaciones son visibles.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Datos OSM incompletos o cambiantes | Cachear respuestas, fechar snapshots, conservar IDs y validar muestra manual. |
| Límites o sobrecarga de Overpass | Pocas consultas, `User-Agent`, backoff, caché y posibilidad de endpoint alternativo. |
| Bar sin entrada modelada | Snap a red como proxy, marcar `access_method`, revisar manualmente casos críticos. |
| Red desconectada o sentidos incorrectos | Auditoría de componentes, grafo dirigido y lista explícita de excepciones. |
| Confundir heurística con óptimo | Lenguaje “mejor encontrado”, semillas, multi-start y benchmark exacto solo para tamaños pequeños. |
| Costes de tiles o cambios de proveedor | Separar datos de mapa base, atribución configurable y evitar dependencia de APIs de pago. |
| Animación inconsistente con métricas | Derivar contadores de la misma geometría/manifest que consume el frontend. |

