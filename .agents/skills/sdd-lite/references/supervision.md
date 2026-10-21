# Supervisión

El supervisor responde del encargo hasta entregarlo: lanzar no es terminar.

## Registro
- Cada encargo de una fase o un cambio es una fila de la tabla Encargos de su `plan.md` o documento de cambio.
  Estados: en curso, bloqueado, necesita decisión, hecho, fallido, cancelado.
- Cada pregunta para el usuario es una fila de Decisiones del usuario. Estados: abierta, respondida, aplazada.
  Solo se cierra con la respuesta literal del usuario o con evidencia de que ya no aplica, nunca porque el encargo terminó.
- Un arreglo trivial suelto no necesita registro; basta su evidencia en el mensaje de entrega.
- El registro guarda tareas y decisiones, no agentes: un identificador de agente no prueba que siga vivo.

## Juzgar un informe
- Lee la línea `Estado:` y contrasta lo que afirma con la realidad: `git log`, `git diff --stat`, el plan marcado, `npm run check`.
- `hecho` sin evidencia por criterio, con el árbol sucio o fuera del alcance no es `hecho`: devuélvelo con lo que falta.
- Decide tú lo inequívoco: restaurar lo aceptado o corregir lo que la intención del usuario ya exige, aunque sea difícil.
- El lenguaje de un revisor o de un ejecutor no amplía el contrato; "seguridad" o "obligatorio" son evidencia, no autoridad.

## Decisiones del usuario
Escala solo:
- una ampliación del contrato: garantía, subsistema, abstracción o mecanismo nuevo;
- una decisión de producto o arquitectura sin resolver;
- hallazgos repetidos del mismo tema que acumulan maquinaria alrededor de una abstracción dudosa;
- algo destructivo, irreversible, de seguridad, una credencial o un coste.
Preséntala en cinco puntos: requisito original, propuesta, alternativa mínima, consecuencias de aceptar y de rechazar, y recomendación.
Pide la palabra del usuario solo cuando el siguiente paso exige revisión, aprobación o una elección.
El ejecutor nunca decide ni contesta su propia pregunta: la respuesta le llega del supervisor con las palabras del usuario.

## Atasco
Escalera, de menos a más:
1. Si pregunta algo que el brief ya responde, contéstale en una línea con `SendMessage`.
2. Si está confundido o en bucle, corrígele en una línea con `SendMessage`.
3. Si sigue igual, lanza un ejecutor nuevo sobre la misma rama con una nota de progreso: qué está hecho, qué falla y qué no repetir.
4. Si ese también falla, marca el encargo `fallido` y explícaselo al usuario con la evidencia y las opciones.
Un agente que terminó o se detuvo no se reanuda solo; un agente de una sesión anterior ya no existe.

## Cambios a mitad
Si el usuario cambia la petición con un encargo en curso, añade sus palabras a "Intención del usuario" y envíaselas al agente;
si invalida el trabajo entero, cancélalo y lanza otro.
Los requisitos nuevos que aparecen en una revisión van a un encargo o cambio de seguimiento, no amplían el actual.

## Reanudar
Al abrir la sesión llega el rumbo: rama, trabajo abierto, encargos sin cerrar y decisiones pendientes.
Antes de aceptar trabajo nuevo, reconcilia: lo que dice el registro frente a Git (ramas, commits, worktrees y árbol de trabajo).
Un encargo `en curso` de otra sesión se relanza con nota de progreso o se cierra con evidencia; nunca se da por hecho.
Las decisiones abiertas se recuerdan al usuario en el primer mensaje.

## Cierre
- La entrega la hace un ejecutor; el supervisor comprueba que la rama existe fuera de cualquier worktree desechable y que la PR no es borrador.
- Al usuario: resultado por criterio, URL completa de la PR o rama local, pendientes y decisiones que le tocan.
- Después del cierre, los worktrees sin trabajo pendiente se eliminan; si hay trabajo sin integrar, se investiga, nunca se fuerza.

## Comunicación
- El usuario oye resultados, consecuencias y decisiones: "la exportación ya rechaza fechas vacías; falta decidir el formato", no "el ejecutor E3 devolvió hecho".
- Sin jerga interna: ni IDs de agente, ni hooks, ni worktrees; "copia aislada" o "rama" si hace falta.
- Silencio ante lo rutinario: reintentos, esperas y progreso normal no se cuentan; lo no urgente se agrupa.
- Malas noticias, primero y con evidencia.
