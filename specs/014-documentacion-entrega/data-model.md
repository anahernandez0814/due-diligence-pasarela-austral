# Data Model: Documentación de entrega (#14)

No hay datos de la aplicación. Las «entidades» son documentos con una estructura que los
tests comprueban.

## DECISIONES.md (resumen, ≤ 100 líneas a 90 columnas)

| Sección | Contenido | Comprobación |
|---------|-----------|--------------|
| Título e introducción | 2–3 líneas: qué es y que el detalle está en `docs/decisiones-detalle.md` | — |
| Necesidades del ecosistema | Tabla: `N` · Necesidad · Mecanismo · Por qué · Descartado · Dónde (tickets y archivo principal, con enlace al detalle) | Filas 1 a 11; enlaces válidos |
| Sistema con el Agent SDK | 6–8 líneas: coordinador y subagentes con herramientas restringidas, hooks del SDK, servidor MCP, fallas y cobertura, interfaz de chat | Entre 6 y 8 líneas no vacías |
| Flujo de trabajo | Excepciones de arranque del #1; una rama por ticket con merge commit; workflows del Project con la corrección | — |
| Límites conocidos | Lista corta, cada punto con enlace al detalle | Enlaces válidos |

Reglas: cada ticket #1–#13 y #19 aparece al menos una vez; nada de los añadidos de R5 se
copia (solo se nombra y enlaza).

## docs/decisiones-detalle.md

- Todas las líneas no vacías del `DECISIONES.md` de `f9e82d6`, en el mismo orden (entradas 1
  a 14 con sus encabezados `## N. …`).
- Notas añadidas tras la línea que corrigen: entrada 3 (workflows del Project) y entrada 11
  (espera de la categoría con cualquier frente caído).
- Secciones nuevas al final: «Desviaciones declaradas», «Límites del plugin (PR #29)»,
  «Sugerencias no atendidas de los PR» y «Mejoras futuras».

## docs/entrega.md

1. Lista de verificación (casillas) con los siete puntos del issue y la frase de visibilidad.
2. Generar el .zip (PowerShell y bash) y comprobar contenido y tamaño.
3. Revisar credenciales en el historial: bloque de prefijos y bloque del detector.
4. Guion del video de funcionamiento, con tiempos.
5. Guion del video de defensa, con tiempos.

Los bloques de código de la sección 3 llevan una marca de identificación para que el test
los extraiga y los ejecute (ver `contracts/documentos.md`).

## README.md

- Presentación y enlaces (Project, video «pendiente», enunciado, constitución, decisiones).
- **Inicio rápido** (primera sección `##`).
- Resto actual como referencia, con los dos ajustes de R7.
