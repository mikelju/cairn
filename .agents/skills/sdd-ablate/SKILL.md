---
name: sdd-ablate
description: Consolidar aprendizajes candidatos al cerrar una fase, auditar el presupuesto de 5.000 tokens de AGENTS.md, podar instrucciones redundantes y migrar reglas deterministas a .claude/hooks/. Usar al cerrar una fase o cuando un agente incumpla repetidamente una regla escrita.
---
# Aprendizaje y poda con presupuesto

Las reglas en lenguaje natural son probabilísticas y consumen atención; los hooks son deterministas y gratuitos en tokens.
Esta skill aplica la pasada de aprendizaje al cerrar una fase o cuando `AGENTS.md` se acerca a su tope de 5.000 tokens.
El supervisor encarga el análisis a un `explorador` y la edición aprobada por el usuario a un `ejecutor`.

## Requisitos para aceptar un aprendizaje
Cada propuesta nacida de `## Aprendizajes candidatos` exige:
- Evidencia en al menos dos sesiones o encargos distintos con cita textual del fallo o retrabajo.
- Destino en el archivo más específico posible según el árbol de ubicación.
- Si el destino es `AGENTS.md` y supera el presupuesto, indicar qué regla existente se compacta o sale.

## Árbol de ubicación (de mayor a menor garantía)
1. Hook en `.claude/hooks/` (`guard-reglas.mjs` o `supervisor-reglas.mjs`): cuando la regla es una prohibición o requisito mecánico verificable sobre el comando, la ruta o el estado de Git sin juicio semántico. Al pasar a hook, la explicación larga se borra del Markdown.
2. Skill en `.agents/skills/`: cuando el procedimiento solo aplica en una actividad concreta (planear, ejecutar, revisar, entregar, GitHub o Lavish).
3. Contrato de agente en `.claude/agents/`: cuando corrige el comportamiento interno de `ejecutor`, `explorador` o `revisor`.
4. `AGENTS.md`: solo cuando aplica a casi toda sesión tanto del supervisor como de los subagentes.

## Qué podar para hacer hueco
- Instrucciones ya bloqueadas por `guard.mjs`, `supervisor.mjs` o `stop-gate.mjs`.
- Reglas duplicadas entre `AGENTS.md`, `SKILL.md` y el contrato del subagente.
- Comportamientos que el modelo actual ya cumple de serie sin instrucción.
- Párrafos explicativos reducibles a una oración imperativa en una línea.

## Presentación al usuario
Al cerrar la fase, presenta como máximo cinco ediciones candidatas:
- Cambio propuesto (texto exacto o regla de hook).
- Archivo de destino.
- Cita de las sesiones que lo justifican.
- Regla que se elimina o compacta a cambio.
Nunca edites `AGENTS.md` a mitad de sesión: solo tras la aprobación del usuario al cierre de la fase.
