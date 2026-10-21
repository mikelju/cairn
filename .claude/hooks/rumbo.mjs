// Rumbo en SessionStart: resume en el contexto del agente donde se quedo el proyecto.
//
// Contrato (docs oficiales de hooks): en SessionStart, el stdout en texto plano se anade
// al contexto. Sale siempre con 0: un fallo aqui nunca impide abrir la sesion.
//
// Lee Git, el plan maestro y los planes y cambios abiertos con sus tablas de encargos
// y de decisiones del usuario. Solo lectura, sin red.
// Acepta los registros en espanol o en ingles: `Estado:` o `Status:`, `## Encargos` o `## Briefs`,
// `## Decisiones del usuario` o `## User decisions`, y los valores de estado de los dos idiomas.

import { execFileSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const MAX_LINEAS = 40;
const CERRADOS = new Set(["hecho", "fallido", "cancelado", "done", "failed", "cancelled", "canceled"]);
const DECISION_ABIERTA = new Set(["abierta", "open"]);

function git(raiz, ...args) {
  return execFileSync("git", args, { cwd: raiz, encoding: "utf8", timeout: 5000, stdio: ["ignore", "pipe", "ignore"] }).trim();
}

function leer(ruta) {
  try {
    return readFileSync(ruta, "utf8");
  } catch {
    return "";
  }
}

/** Valor de la primera linea `Estado:` o `Status:` del documento, o null. */
function estado(texto) {
  const m = texto.match(/^(?:Estado|Status):\s*(.*)$/m);
  return m ? m[1].trim() : null;
}

/** Filas de datos de la tabla bajo `## <titulo>` (cualquiera de los titulos), como listas de celdas. */
function filasDeTabla(texto, ...titulos) {
  const lineas = texto.split(/\r?\n/);
  const buscados = titulos.map((t) => `## ${t}`.toLowerCase());
  const inicio = lineas.findIndex((l) => buscados.includes(l.trim().toLowerCase()));
  if (inicio < 0) return [];
  const filas = [];
  for (const l of lineas.slice(inicio + 1)) {
    if (/^#{1,2}\s/.test(l)) break;
    const t = l.trim();
    if (!t.startsWith("|")) continue;
    if (/^[|\s:-]+$/.test(t)) continue;
    const celdas = t.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
    if (celdas.every((c) => !c)) continue;
    if (celdas[0].toLowerCase() === "id") continue;
    filas.push(celdas);
  }
  return filas;
}

function documentosAbiertos(raiz) {
  const candidatos = [];
  const planes = join(raiz, "docs", "plans");
  if (existsSync(planes)) {
    for (const d of readdirSync(planes, { withFileTypes: true })) {
      if (d.isDirectory() && existsSync(join(planes, d.name, "plan.md"))) candidatos.push(`docs/plans/${d.name}/plan.md`);
    }
  }
  const cambios = join(raiz, "docs", "changes");
  if (existsSync(cambios)) {
    for (const d of readdirSync(cambios, { withFileTypes: true })) {
      if (d.isFile() && d.name.endsWith(".md")) candidatos.push(`docs/changes/${d.name}`);
    }
  }
  const abiertos = [];
  for (const ruta of candidatos.sort()) {
    const texto = leer(join(raiz, ruta));
    const e = estado(texto);
    if (!e || e.includes("|") || /^(integrad[ao]|integrated)\b/i.test(e)) continue;
    abiertos.push({ ruta, estado: e, texto });
  }
  return abiertos;
}

function rumbo(raiz) {
  const lineas = ["[SDD Lite] Rumbo al abrir la sesión"];

  try {
    git(raiz, "rev-parse", "--verify", "HEAD");
    const rama = git(raiz, "rev-parse", "--abbrev-ref", "HEAD");
    const cambios = git(raiz, "status", "--porcelain").split(/\r?\n/).filter(Boolean).length;
    lineas.push(`Rama: ${rama}. Archivos con cambios sin commit: ${cambios}.`);
  } catch {
    lineas.push("El proyecto aun no esta arrancado (sin repositorio Git o sin commits): /iniciar ejecuta npm run arrancar.");
  }

  const maestro = leer(join(raiz, "docs", "plans", "0_plan_maestro.md"));
  if (maestro) lineas.push(`Plan maestro: docs/plans/0_plan_maestro.md, Estado: ${estado(maestro) ?? "sin linea Estado"}.`);

  const abiertos = documentosAbiertos(raiz);
  const encargos = [];
  const decisiones = [];
  for (const doc of abiertos) {
    for (const f of filasDeTabla(doc.texto, "Encargos", "Briefs")) {
      const est = (f[3] || "").toLowerCase();
      if (!CERRADOS.has(est)) encargos.push(`- ${doc.ruta}: ${f[0]} (${f[1] || "?"}) ${f[2] || ""} [${f[3] || "sin estado"}]`);
    }
    for (const f of filasDeTabla(doc.texto, "Decisiones del usuario", "User decisions")) {
      if (DECISION_ABIERTA.has((f[3] || "").toLowerCase())) decisiones.push(`- ${doc.ruta}: ${f[0]} ${f[1] || ""}`);
    }
  }

  if (!abiertos.length && !encargos.length && !decisiones.length) {
    lineas.push("No hay trabajo, encargos ni decisiones abiertos.");
  } else {
    if (abiertos.length) {
      lineas.push("Trabajo abierto:");
      for (const d of abiertos) lineas.push(`- ${d.ruta}: ${d.estado}`);
    }
    if (encargos.length) {
      lineas.push("Encargos abiertos:");
      lineas.push(...encargos);
      lineas.push("Los subagentes de una sesion anterior ya no existen; reconcilia con Git y el plan antes de relanzar.");
    }
    if (decisiones.length) {
      lineas.push("Decisiones pendientes del usuario:");
      lineas.push(...decisiones);
    }
  }

  if (lineas.length > MAX_LINEAS) {
    const resto = lineas.length - (MAX_LINEAS - 1);
    return [...lineas.slice(0, MAX_LINEAS - 1), `... y ${resto} linea(s) mas; consulta docs/plans y docs/changes.`];
  }
  return lineas;
}

try {
  let entrada = {};
  try {
    const { leerEntrada } = await import("./lib.mjs");
    entrada = await leerEntrada();
  } catch {
    // Sin entrada legible se usa el directorio del proyecto o el actual.
  }
  const raiz = process.env.CLAUDE_PROJECT_DIR || entrada.cwd || process.cwd();
  process.stdout.write(`${rumbo(raiz).join("\n")}\n`);
} catch (error) {
  process.stdout.write(`[SDD Lite] Rumbo no disponible: ${error.message}\n`);
}
process.exit(0);
