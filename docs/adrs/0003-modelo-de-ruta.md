# ADR 0003: Modelo de ruta investigado

- **Estado:** propuesta para aprobación
- **Fecha:** 2026-11-11

## Contexto

“Visitar todos los bares” puede significar TSP abierto o cerrado, con o sin inicio obligatorio. Las restricciones peatonales hacen que los costes puedan ser dirigidos y asimétricos.

## Decisión propuesta

Usar como escenario principal un recorrido abierto con inicio configurable —Plaza Nueva por defecto— y final libre. Comparar un recorrido cerrado como sensibilidad. Tratar como no visitables los establecimientos sin acceso a la red, pero reportarlos explícitamente; no ocultarlos para mejorar métricas.

## Consecuencias

Los algoritmos se comparan bajo el mismo contrato y matriz. La interfaz deberá mostrar el escenario, inicio, final y política de desconectados. La decisión final debe aprobarse antes de implementar la optimización.

