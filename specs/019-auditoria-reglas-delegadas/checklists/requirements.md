# Checklist de calidad de la especificación: Auditoría: reglas delegadas a otro ticket y uv.lock como referencia

**Propósito**: Validar que la especificación está completa y es consistente antes de planificar
**Creada**: 2026-10-17
**Funcionalidad**: [spec.md](../spec.md)

## Calidad del contenido

- [x] Sin detalles de implementación (lenguajes, frameworks, APIs)
- [x] Centrada en el valor para el usuario y la necesidad del negocio
- [x] Redactada para personas no técnicas
- [x] Todas las secciones obligatorias completas

## Completitud de los requisitos

- [x] No quedan marcadores [NEEDS CLARIFICATION]
- [x] Los requisitos son comprobables y no ambiguos
- [x] Los criterios de éxito son medibles
- [x] Los criterios de éxito no dependen de la tecnología
- [x] Todos los escenarios de aceptación están definidos
- [x] Los casos límite están identificados
- [x] El alcance está claramente acotado
- [x] Las dependencias y los supuestos están identificados

## Preparación de la funcionalidad

- [x] Todos los requisitos funcionales tienen criterios de aceptación claros
- [x] Los escenarios de usuario cubren los flujos principales
- [x] La funcionalidad cumple los resultados medibles de los criterios de éxito
- [x] No se filtran detalles de implementación en la especificación

## Notas

- Los nombres de los cuatro archivos de la puerta y de los tres archivos excluidos aparecen
  en la spec porque son el **alcance** del issue, no el cómo: la spec no dice cómo se
  redacta ni se compara el texto, solo qué debe decir y qué no se toca.
- Decisión tomada por defecto, sin marcador, y documentada en Supuestos: cuando una regla se
  delega, la delegación prevalece sobre "el diff toca código que la implementa" si ese código
  solo aporta datos o clasificación. Lo exige el criterio de aceptación del #5 (el servidor
  clasifica el riesgo de la categoría y aun así I.3 debe salir `no aplica`). **Confirmada por
  la analista** con una condición: solo si la spec nombra el ticket con su número (FR-002).
  Por eso no hizo falta `/speckit-clarify`.
- `preparar_revision.py` queda fuera del alcance: no marca `uv.lock` como referencia en la
  lista del contexto; la exención vive en el texto de los cuatro archivos.
