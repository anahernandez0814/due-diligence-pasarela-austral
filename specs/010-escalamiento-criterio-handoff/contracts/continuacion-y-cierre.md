# Contrato: continuación del caso y fin de turno (#10)

Amplía `contracts/cierre.md` del #9 y `contracts/caso.md` del #6. Las decisiones están en `research.md` R1 a R4.

## API del caso

```python
caso = await ejecutar_caso(solicitud, ...)  # primer turno, como hasta ahora
await caso.continuar(mensaje)  # turno siguiente en el mismo caso
caso.espera  # Espera | None: la del último fin de turno
caso.turnos_del_caso  # list[Clasificacion], una por turno
```

- **`continuar`** lanza `query(prompt=mensaje, options=...)` con `resume=<session_id del último ResultMessage>`. Los hooks, el `Delegador`, el estado y los eventos son los mismos.
  - Sin `session_id` lanza `CasoSinSesion`, con un mensaje en español.
- **Al empezar cada turno**:
  - se añade el texto a `estado.mensajes`;
  - se registra `mensaje_analista`;
  - `cierres_impedidos` vuelve a 0, y `cierre_sin_escalar` y `cierre_sin_informe` vuelven a `False` (R4).
- **`Caso.completo`** es falso si hay espera del analista (FR-018), además de lo del #9.

## Fin de turno (`Stop` del coordinador)

En este orden:

1. **`espera_del_analista(estado)`**: si hay espera, se permite, se registra `espera_analista` con su motivo y **no** se cuenta como cierre impedido.
2. **`evaluar_cierre(estado)`**: como en el #9. Primero va el escalamiento, que ahora solo cuenta si es del comercio actual (R8), y después el informe vigente.
3. **Devoluciones** con `MAX_CIERRES_IMPEDIDOS` por turno. Agotadas, se marca `cierre_sin_escalar` o `cierre_sin_informe`.

| Registro | Categoría | ¿Espera? |
|----------|-----------|----------|
| sin delegar, en curso o caído | con resultado o sin delegar | no (el registro caído, por sí solo, no es una espera) |
| varias coincidencias | cualquiera | sí (`identificador`) |
| ninguna coincidencia | cualquiera | sí (`nombre`) |
| fuentes que difieren en nombre o representante (D3 del #9) | con resultado o sin delegar | no |
| identificado | con resultado o sin delegar | no |
| cualquier otro estado (sin delegar, en curso, caído, D3 o identificado) | última delegación bloqueada por I.3 y sin resultado | sí (`categoria`) |

La espera `categoria` vale con cualquier estado del registro, también el caído. La tabla muestra la prioridad del motivo, no un orden de evaluación: con el registro en varias coincidencias, el motivo es el del identificador.

## Durante una espera

| Acción | Espera `identificador` / `nombre` | Espera `categoria` |
|--------|-----------------------------------|--------------------|
| consultar o delegar listas | bloqueado por I.1 (#7) | según I.1 |
| escalar | rechazado (FR-016); admitido con el sello | reglas de siempre |
| registrar el informe | rechazado (FR-016) con `MOTIVO_INFORME_ESPERA_IDENTIFICADOR` o `MOTIVO_INFORME_ESPERA_NOMBRE`; antes, en el #9, se aceptaba con el comercio pedido | reglas de siempre (sin `habilitar`) |
| delegar registro con el identificador | permitido; identifica aunque la consulta anterior fuera ambigua (FR-017) | permitido |

## Línea de comandos

```text
uv run python -m due_diligence "<solicitud>" [--sin-continuar]
```

Tras imprimir el caso, si hay espera, se pregunta en la entrada estándar:

- con un texto, sigue con `continuar` y vuelve a imprimir;
- con una línea vacía o fin de entrada, termina.

La salida muestra:
- «Esperando al analista: <motivo>», o «Sin espera del analista»;
- los escalamientos registrados, con su id y sus causas;
- los informes, como en el #9.
