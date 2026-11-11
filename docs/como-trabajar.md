# Cómo trabajar con SDD Lite

Guía de uso del marco de trabajo, para la persona que dirige el proyecto.
El README describe el producto; este archivo describe cómo se trabaja con el agente, y es igual en todos los proyectos.
Para ver el esquema visual interactivo de extremo a extremo (ciclo de 6 etapas, delegación, hooks, relevo y presupuesto de tokens), abre [docs/arquitectura-sdd-lite.html](arquitectura-sdd-lite.html) en tu navegador.

## Reparto de papeles

Tú decides qué se construye y con qué criterios.
Hablas con un solo agente, el supervisor: no programa, sino que encarga el trabajo a otros agentes, juzga su evidencia y te trae resultados y decisiones.
- `ejecutor`: implementa, corrige, redacta specs y planes y entrega la rama o la PR.
- `explorador`: investiga y reproduce fallos sin tocar nada.
- `revisor`: busca cómo falla lo hecho, sin corregir.
Nunca hablas con ellos ni tienes que repartirles trabajo.
Apruebas en tres momentos: el plan maestro, la spec de cada fase y la PR.
Entre medias, el supervisor y sus agentes trabajan solos y solo te interrumpen para decisiones que te tocan.

## Crear un proyecto

Proyecto nuevo:
1. Copia la carpeta del esqueleto SDD Lite y ponle el nombre del proyecto.
2. Ábrela en Claude Code y escribe `/iniciar <de qué va el proyecto>`.
   El supervisor ejecuta antes `npm run arrancar`: `git init` en `main`, nombre del paquete, comprobaciones y primer commit.

Repositorio ya empezado (adopción en rama):
1. Desde su raíz, con el árbol limpio, ejecuta `node "<ruta al esqueleto>/scripts/incluir.mjs"`.
   Deja SDD Lite en la rama `sdd-lite` con un commit, sin pisar tu `AGENTS.md` ni tu `.claude/settings.json`, y copia las guías y esquemas a `docs/`.
2. Abre Claude Code en una sesión nueva en esa carpeta y escribe `/iniciar`.

Repositorio ajeno o evaluación (adopción local / modo aporte):
1. Para trabajar o evaluar un proyecto ajeno sin dejar rastro en Git: ejecuta `node "<ruta al esqueleto>/scripts/incluir.mjs" --local`.
   No crea rama ni hace commits en el proyecto ajeno.
   Todos los archivos de SDD Lite quedan ignorados localmente en `.git/info/exclude`.
   El modo aporte se activa en `.git/sdd-lite/config.json`, y la guardia bloquea cualquier mención al marco en commits o PRs.
2. Abre Claude Code en esa carpeta y escribe `/iniciar`.

Actualizar un proyecto con SDD Lite previo:
1. Para poner al día un repositorio con una versión anterior del marco: ejecuta `node "<ruta al esqueleto>/scripts/actualizar.mjs"`.
   Actualiza carpetas del método, guías y esquemas interactivos, limpia scripts viejos como `test-hooks.mjs` y sanea el estado de fases anteriores en `docs/plans/`.
   Admite `--dry-run` para previsualizar los cambios, `--no-commit` para omitir el commit y `--force` si hay cambios pendientes.

Sabes que el framework está activo porque el supervisor empieza cada respuesta con "Jefe:".
Opcional: crea el remoto con `gh repo create <usuario>/<proyecto> --private --source . --push` para recibir las entregas como PR.

## Los cuatro comandos

| Comando | Cuándo | Qué obtienes |
|---|---|---|
| `/iniciar <idea>` | Una vez, al empezar | Plan maestro con las fases, para aprobar |
| `/planear <qué>` | Antes de cada fase o de un cambio suelto | Spec de fase o documento de cambio, para aprobar |
| `/ejecutar <qué>` | Con la spec aprobada | Implementación, revisión adversarial y PR |
| `/verificar <qué>` | Cuando quieras una segunda opinión | Solo hallazgos: no corrige ni publica |

Las skills de `.agents/skills/` no se llaman a mano: cada comando carga las que necesita.
Los comandos son atajos; pedirlo en lenguaje natural funciona igual.

## El ciclo de una fase

1. `/planear fase 01`: el supervisor encarga `docs/plans/fase-01-nombre/spec.md` con criterios de aceptación y dudas abiertas.
   Respondes las dudas y dices "spec aprobada"; desde ese momento los criterios quedan congelados.
2. `/ejecutar fase 01`: el supervisor crea la rama y encarga los incrementos; los agentes implementan, pasan las comprobaciones,
   se someten a revisión adversarial, corrigen lo confirmado y abren la PR a `main` con la evidencia por criterio.
   Solo te interrumpe si hay una desviación, un coste nuevo o una decisión tuya.
3. Revisas la PR en GitHub.
   Si hay que cambiar algo, díselo en el chat ("en la PR, el criterio C3 no me convence porque...") y actualiza la PR.
4. Fusionas tú; ningún agente puede fusionar ni aprobar.
   Después, en local: `git switch main` y `git pull`.
5. Al cerrar la fase propone como máximo cinco aprendizajes para sus reglas; aceptas o descartas.
6. Siguiente fase: `/planear fase 02`.

## Situaciones habituales

- Bug o ajuste pequeño: `/planear arreglar X` y después `/ejecutar cambio NNN`; si es trivial, basta con "arregla X".
- Retomar otro día: "continúa la fase 02" en una sesión nueva; el estado está en `plan.md` y en Git, no en la conversación.
  Al abrir la sesión el supervisor recibe el rumbo: trabajo abierto, encargos sin cerrar y decisiones que te debe.
- Ver qué está pasando: pregúntale "¿cómo va?"; los encargos y decisiones están en la tabla de su plan o cambio.
- Cambiar un criterio ya aprobado: el supervisor abre una desviación en la carpeta de la fase y te la propone; no lo cambia solo.
- Revisar algo sin tocarlo: `/verificar fase 02` o `/verificar rama X`.
- Auditoría de seguridad, por ejemplo antes de publicar o desplegar: `/verificar seguridad completo`.
  Da hallazgos por gravedad y no toca nada; los alcances posibles están en `.agents/skills/sdd-delivery/SKILL.md`.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Plan maestro | `docs/plans/0_plan_maestro.md` |
| Spec, plan y resultados de una fase | `docs/plans/fase-NN-nombre/` |
| Cambios sueltos | `docs/changes/NNN-nombre.md` |
| Reglas que el agente carga siempre | `AGENTS.md` |
| Comando de comprobación, de formato y rama por defecto (proyectos que no son Node) | `.sdd-lite.json` |
| Procedimientos del supervisor y los agentes | `.agents/skills/` |
| Definición de los agentes | `.claude/agents/` |
| Hallazgos de seguridad abiertos o aplazados | `docs/security.md` (se crea con el primero) |
| Bloqueos automáticos (push a `main`, secretos, fusionar) | `.claude/settings.json` y `.claude/hooks/` |

## Consejos

- Una fase por sesión: el contexto se mantiene limpio, sale más barato y el agente trabaja mejor.
- Criterios observables en la spec ("el informe marca las facturas con sobrecoste mayor del 5 %"), no deseos ("que funcione bien").
- Si un agente se atasca, el supervisor lo corrige o lo relanza; si no lo consigue, te explica la decisión que necesita.
- Para tocar algo tú mismo con Claude sin supervisor, arranca la sesión con la variable `SDD_SUPERVISOR_LIBRE=1`.
- Tu primer commit lo hace `npm run arrancar`; a partir de ahí nadie escribe directamente en `main`, solo por PR.
