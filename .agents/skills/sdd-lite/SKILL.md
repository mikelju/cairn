---
name: sdd-lite
description: Procedimiento del supervisor de SDD Lite - coordinar un proyecto desde el plan maestro y sus fases hasta entregas comprobadas y revisadas, delegando el trabajo en ejecutores, exploradores y revisores. Usar para iniciar un proyecto, planear el plan maestro, una fase o un cambio, implementar, arreglar, investigar, continuar o reanudar trabajo; no para consultas de solo lectura.
---
# SDD Lite: supervisor

El usuario decide qué se construye y con qué criterios; el supervisor decide quién lo hace y juzga la evidencia; los agentes lo hacen y lo demuestran.
Las dos aprobaciones humanas son el plan maestro y la spec de cada fase. Entre ambas, el trabajo es autónomo.
El supervisor no escribe en el proyecto salvo los registros: todo lo demás es un encargo.

## Clasificar la petición
- Por defecto, entregar un cambio: `ejecutor`.
- Investigar solo si el usuario pide conocimiento o si la duda puede cambiar qué se construye: `explorador`.
  Antes, mira si un plan, cambio o informe ya lo responde.
  No presentes una solución probable y a la vez lances un estudio que no la vaya a cambiar.
- Un diagnóstico o una recomendación no autoriza a implementar; una petición de implementar sí, dentro de su alcance.
- Consulta de solo lectura que se responde leyendo uno o dos archivos: respóndela tú, sin encargo.

## Enrutado: fase o cambio
- ¿Fija criterios congelados contra los que se medirá trabajo futuro? Fase, en `docs/plans/fase-NN-nombre/`.
- ¿No? Cambio, en `docs/changes/NNN-nombre.md`: arreglos, ajustes y mejoras acotadas.
- ¿Altera criterios de una fase aprobada? Desviación `NN.M-nombre.md` en la carpeta de esa fase, nunca un cambio suelto.
- Arreglo trivial: basta la petición, un encargo y la evidencia de entrega.
Plantillas en `docs/templates/`. Todo cambio sustancial sube: desviación a spec y plan, alcance a plan maestro.

## Flujo
1. Iniciar: si `/iniciar` llega sin la idea del producto en sus argumentos, haz al usuario una sola pregunta por la idea y nada más hasta tener respuesta;
   no la deduzcas del nombre de la carpeta, de `package.json` ni de otros archivos.
   Con la idea, si la carpeta no tiene commits, ejecuta `npm run arrancar`, que hace `git init` y el primer commit en `main`; después crea la rama `inicio`.
   Encarga a un ejecutor sustituir por los del producto la descripción y el Mapa de `AGENTS.md`, `README.md` y el nombre y el script `check` de `package.json`.
   El README del producto enlaza a `docs/como-trabajar.md`, que no se edita.
   Conversa con el usuario hasta entender el producto; si hace falta, un explorador reconoce el terreno.
   Encarga el borrador de `docs/plans/0_plan_maestro.md`, juzga que proponga fases pequeñas que dejen algo funcionando y preséntalo con sus decisiones abiertas.
   Aprobado el plan maestro, un ejecutor lo entrega en la rama `inicio` con el pipeline de `../sdd-delivery/SKILL.md`.
2. Especificar una fase: encarga `spec.md` con objetivo, alcance y criterios observables, suposiciones declaradas y dudas en "Decisiones abiertas".
   Lleva cada duda al usuario y anota su respuesta literal; al aprobarla queda congelada.
3. Planear: encarga `plan.md` con incrementos verificables ligados a criterios. No requiere nueva aprobación.
4. Ejecutar: crea o cambia a la rama de trabajo (`fase-NN-nombre` o `cambio-NNN`) y relee los incrementos pendientes de `plan.md`.
   Encarga los incrementos a ejecutores, de uno en uno o en grupos coherentes, y registra cada encargo en la tabla Encargos.
   Juzga cada informe antes de lanzar el siguiente: evidencia vigente, plan marcado y comprobaciones en verde.
5. Validar: carga `../sdd-delivery/SKILL.md`, que incluye la revisión adversarial de `../sdd-review/SKILL.md`.
6. Cerrar: un ejecutor entrega en rama y PR, nunca fusiona; tú actualizas el plan maestro, juzgas los resultados por criterio
   y presentas al usuario la PR, los pendientes y los aprendizajes candidatos.
Si el usuario pidió solo plan, termina en el paso que corresponda.
Una lista de tareas del harness, si existe, es copia efímera; la fuente es `plan.md` o el documento del cambio.

## Delegación
- Solo tres tipos de agente: `ejecutor`, `explorador` y `revisor`, definidos en `.claude/agents/`; un hook rechaza otros y briefs incompletos.
- Cada encargo lleva su brief según `references/encargos.md`; nunca la conversación ni tu razonamiento.
- Lectura y revisión en abanico: hasta cuatro agentes en paralelo, cada uno devuelve un resumen.
- Escritura: un ejecutor a la vez por carpeta de trabajo; en paralelo solo con un worktree por ejecutor y archivos disjuntos.
- Los agentes no delegan: si un encargo es demasiado grande, pártelo tú.
- Seguimiento, decisiones, atascos, reanudación y cierre: `references/supervision.md`.

## Cuándo parar y preguntar
Decisión del usuario, desviación que cambia criterios, coste o dependencia nueva, publicación no autorizada,
algo destructivo o un atasco que la escalera de `references/supervision.md` no resuelve:
conserva trabajo y evidencia, explica el bloqueo y la decisión necesaria.

## Sesiones y contexto
- Una fase o un cambio por sesión; reanuda desde el plan y Git, no desde la memoria de la conversación.
  Al abrir la sesión, un hook inyecta el rumbo: rama, trabajo abierto, encargos sin cerrar y decisiones pendientes.
- `AGENTS.md` no se edita a mitad de sesión porque invalida la caché del prefijo; las únicas excepciones son `/iniciar`
  y la pasada de aprendizaje, que van al final de su sesión.
- En el contexto principal solo decisiones y evidencia; lo amplio lo leen los agentes.

## Aprendizaje con presupuesto
Al cerrar una fase, propone al usuario como máximo cinco ediciones a `AGENTS.md`, a los agentes o a las skills.
Cada una necesita evidencia de al menos dos sesiones con cita textual; si no cabe en el presupuesto, otra sale.
Si el disparador es estrecho y detectable, va a una skill; si aplica a casi toda sesión, a `AGENTS.md`.
Las ediciones aceptadas las hace un ejecutor.

## Contexto bajo demanda
Encargos: `references/encargos.md`. Supervisión: `references/supervision.md`. Trabajo del ejecutor: `references/ejecucion.md`.
Revisión: `../sdd-review/SKILL.md`. Entrega y No Mistakes: `../sdd-delivery/SKILL.md`.
GitHub: `../github/SKILL.md`. Planes visuales: `../lavish/SKILL.md`.
