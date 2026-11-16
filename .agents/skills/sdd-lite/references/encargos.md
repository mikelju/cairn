# Encargos

El brief es lo único que recibe el agente además de su contrato de `.claude/agents/` y de `AGENTS.md`.
Escríbelo como para un recién llegado: sin la conversación, sin tu razonamiento y sin marcadores sin rellenar.
Un hook rechaza el lanzamiento si faltan los encabezados obligatorios de su tipo.

## Ejecutor y explorador
Encabezados obligatorios: `## Intención del usuario` y `## Terminado`.

```markdown
Encargo E<n> de <fase-NN o cambio-NNN o "suelto">.

## Intención del usuario
Las palabras del usuario, literales, más el contexto justo para entenderlas, sin ampliarlas.
Si cambió la petición a mitad, se añaden sus palabras nuevas; no se reescriben las anteriores.
Incluye el texto literal del incremento y de los criterios C1, C3 que aplican (para que el ejecutor no tenga que leer `plan.md`).

## Encargo
Qué hay que construir, investigar o redactar, con las instrucciones imprescindibles.
Fuera de alcance: lo que no debe tocar aunque parezca natural.

## Contexto
Rutas de código y spec que debe leer y decisiones del usuario ya tomadas que le afectan (nunca le pases `plan.md` ni fases ya integradas).

## Dónde
Rama y carpeta de trabajo, y archivos o directorios que puede modificar.
Permisos: commit sí o no; push y PR sí o no.

## Terminado
Qué tiene que ser cierto para devolver `hecho`:
- Nivel de comprobación durante el desarrollo según el radio de impacto del cambio: `local` (comprobación directa del archivo o módulo tocado) o `profundo` (batería completa y regresión en cada paso); al cerrar el encargo, `npm run check` siempre en verde.
- Criterios cumplidos con evidencia empírica: comando o recorrido real del usuario ejecutado tras el último cambio y resultado observado (si el cambio toca interfaz, CLI o servidor, comprobado contra la aplicación en ejecución, no solo mediante mocks).
- Árbol limpio y commits hechos (el plan lo marca el supervisor al validar tu informe), o, para un explorador, la pregunta respondida con citas `archivo:línea`.
```

### Modos del ejecutor
- Implementación: incrementos copiados de `plan.md`; el ejecutor sigue `ejecucion.md`, en esta carpeta. Commit en la rama de trabajo, sin push y sin editar `plan.md`.
- Documento: borrador de plan maestro, spec, plan, cambio o desviación con su plantilla de `docs/templates/`. Sin commit salvo que se pida.
- Corrección: hallazgos confirmados de una revisión, cada uno con su escenario de fallo; nada fuera de ellos.
- Entrega: etapa 5 de `../../sdd-delivery/SKILL.md` en la rama indicada; devuelve la URL completa de la PR o la rama local.

### Explorador
- Sin "Dónde": no modifica el proyecto.
- En "Terminado", la pregunta concreta que debe quedar respondida y qué evidencia se espera.

## Revisor
Encabezados obligatorios: `## Criterios` y `## Rango`.
Bloque común y lentes en `../../sdd-review/references/lentes.md`; el brief solo añade lo concreto:

```markdown
Revisión R<n>, lente <corrección | seguridad y datos | ...>.

## Criterios
Ruta a `spec.md` de la fase o al documento del cambio.

## Rango
Base y comando: `git diff <base>` más archivos nuevos: <lista>. Rama: <rama>.

## Lente
El bloque de esa lente, copiado de `lentes.md`.
```

Nunca le pases el informe, el resumen ni el razonamiento del ejecutor: confirmaría el resumen, no el código.

## Lanzar
- `subagent_type`: `ejecutor`, `explorador` o `revisor`. Otro tipo o un fork se rechaza.
- `model`: ajusta el modelo a la dificultad del encargo para no agotar cuota sin motivo (`haiku` o `sonnet` en exploraciones acotadas y cambios mecánicos; `opus` o `sonnet` en diseño, fallos complejos y revisión adversarial).
- No lances un `explorador` para comprobar un dato que se resuelve con un `Grep`, un `Glob` o leyendo uno o dos archivos desde el supervisor.
- `description`: el ID del encargo y tres a cinco palabras.
- En segundo plano cuando el usuario pueda seguir hablando o haya varios en paralelo; su fin llega como notificación.
  En primer plano cuando lo siguiente depende del resultado y no hay nada más que hacer.
- Dimensiona cada brief para un contexto de Sonnet: como máximo dos incrementos que creen un módulo, y ningún brief que reescriba un registro y código a la vez.
  Un lote que falló por contexto se divide antes de relanzarlo; nunca se reenvía entero.
- No encargues a un ejecutor desplegar a producción ni ejecutar llamadas a Bedrock o AWS con el perfil del usuario.
  Pide al usuario que lo ejecute y registra el resultado.
- Paralelo con escritura: cada ejecutor en su worktree (`git worktree add ../<proyecto>-E<n> -b <rama>`), indicado en "Dónde".
