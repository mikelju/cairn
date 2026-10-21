// Reglas del supervisor de SDD Lite: la sesion principal coordina y delega; no implementa.
// El hook es supervisor.mjs, que solo lee la entrada y llama a `evaluarSupervisor`;
// la suite importa este modulo.
//
// Contrato (docs oficiales de hooks): `agent_id` y `agent_type` solo llegan cuando la
// herramienta la usa un subagente; en la sesion principal `agent_id` no existe.
// Como en la guardia, se emite el JSON estructurado y ademas se sale con 2.
//
// Escape: con SDD_SUPERVISOR_LIBRE=1 el usuario trabaja sin supervisor.

import { isAbsolute, relative, resolve } from "node:path";
import { comandosAnalizables, separarCuerpos, SHELLS, tokens, trocear, verboDe } from "./lib.mjs";

const TIPOS = ["ejecutor", "explorador", "revisor"];

// Encabezados obligatorios del brief por tipo, ya normalizados (minusculas, sin tildes).
const ENCABEZADOS = {
  ejecutor: ["intencion del usuario", "terminado"],
  explorador: ["intencion del usuario", "terminado"],
  revisor: ["criterios", "rango"],
};
// Forma legible de cada encabezado para el mensaje.
const LEGIBLE = {
  "intencion del usuario": "## Intención del usuario",
  terminado: "## Terminado",
  criterios: "## Criterios",
  rango: "## Rango",
};

const ESCRITURA = new Set(["Write", "Edit", "MultiEdit", "NotebookEdit"]);

// Registros que el supervisor si escribe: planes, cambios, seguridad y traspasos de sesion.
const PREFIJOS_REGISTRO = ["docs/plans/", "docs/changes/", ".claude/relevo/"];
const ARCHIVOS_REGISTRO = ["docs/security.md"];

const BRIEF = ".agents/skills/sdd-lite/references/encargos.md";

// Bash y PowerShell en la sesion principal: lista de denegacion conservadora, no un clasificador.
// Deniega escribir, mover o borrar archivos e instalar cosas, sea cual sea el destino:
// el supervisor escribe sus registros con Write o Edit, que si distinguen la ruta.
// Tambien deniega los formateadores y arreglos que reescriben archivos (`ruff format`, `ruff check --fix`,
// `black`, `isort`) y analiza el comando interior de `uv run` y `uvx`; `uv run --with` instala.
// Sigue permitido: leer, git (salvo los subcomandos de abajo), gh, npm run, node script,
// `uv run pytest`, `uv run mypy` y `ruff check` sin `--fix`.
// NO cubre (lo frena el contrato de AGENTS.md, no este hook):
// - Write y Edit fuera de CLAUDE_PROJECT_DIR, como un worktree hermano: solo se vigila el proyecto abierto;
// - `uvx` de una herramienta no instalada, que la descarga a la cache como `npx`;
// - codigo que escribe archivos desde un interprete: `node -e`, `python -c`, scripts propios, `npm run <script>`;
// - herramientas no listadas que escriben como efecto (tar x, unzip, curl -o, make, docker);
// - git que integra commits ya hechos en el arbol: merge, pull, rebase, cherry-pick, revert, switch o checkout de rama,
//   y `git checkout <ruta>` sin `--` (no se distingue de `git checkout <rama>`);
// - `npx` o `pnpm dlx` de un paquete no instalado, que lo descarga a la cache aunque solo lo ejecute;
// - `yarn`, `pnpm` o `npx` invocados por ruta absoluta o con otro nombre;
// - alias o funciones del perfil del shell con otro nombre y variables que expanden a un comando.
const SHELL = new Set(["Bash", "PowerShell"]);
const VERBOS_ESCRITURA = new Set([
  // POSIX
  "cp", "mv", "rm", "rmdir", "mkdir", "touch", "tee", "ln", "install", "truncate", "dd", "rsync", "scp",
  // cmd y alias de PowerShell
  "copy", "move", "del", "erase", "ren", "rename", "rd", "md", "xcopy", "robocopy",
  "ni", "ri", "cpi", "mi", "rni", "ac", "clc",
  // cmdlets de PowerShell
  "set-content", "add-content", "out-file", "new-item", "remove-item", "copy-item", "move-item",
  "rename-item", "clear-content", "export-csv", "install-module", "install-package", "install-script",
  // gestores de paquetes del sistema
  "winget", "choco", "scoop", "apt", "apt-get", "brew",
]);
// Subcomandos que instalan o cambian dependencias, por gestor.
const INSTALA = {
  npm: new Set([
    "install", "i", "ci", "add", "uninstall", "un", "remove", "rm", "update", "up", "link",
    "init", "create", "exec", "x", "prune", "dedupe", "rebuild", "version",
  ]),
  pip: new Set(["install", "uninstall"]),
  pip3: new Set(["install", "uninstall"]),
  pipx: new Set(["install", "uninstall"]),
  uv: new Set(["add", "remove", "sync", "lock", "pip", "tool", "venv", "init"]),
  poetry: new Set(["add", "remove", "install"]),
  cargo: new Set(["add", "install"]),
  go: new Set(["get", "install"]),
};
// Subcomandos de npm que solo escriben con ciertas acciones: `npm pkg get` lee, `npm pkg set` escribe.
const NPM_ACCION_ESCRIBE = { pkg: ["set", "delete", "fix"], audit: ["fix"], config: ["set", "delete", "edit"] };
// Opciones globales de npm que llevan valor: `npm --prefix sub install`.
const NPM_FLAGS_CON_VALOR = new Set(["--prefix", "-C", "--workspace", "-w", "--registry", "--cache", "--userconfig"]);
// Opciones de `uv run` y `uvx` que llevan valor, para encontrar el comando interior que se analiza.
const UV_FLAGS_CON_VALOR = new Set([
  "--python", "-p", "--project", "--directory", "--package", "--env-file", "--group", "--extra",
  "--from", "--index", "--default-index", "--index-url", "--extra-index-url", "--cache-dir", "--config-file",
]);
// `python -m <modulo>`: los gestores de INSTALA y los que crean entornos.
const PYTHON = new Set(["python", "python3", "py"]);
const PYTHON_MODULO_ESCRIBE = new Set(["venv", "ensurepip"]);
// pnpm, yarn y npx son envoltorios en lib.mjs: su subcomando llega como verbo.
const VERBOS_INSTALA_ENVUELTOS = new Set(["add", "install"]);
// Por eso se miran tambien sin quitar: `yarn` a secas instala y `npx create-vite` genera un proyecto.
const ENVOLTORIO_INSTALA = new Set([
  "add", "install", "i", "remove", "rm", "up", "upgrade", "update", "dlx", "create", "import",
  "link", "unlink", "init", "patch", "set",
]);
const PREVIOS = new Set(["sudo", "env", "command", "time", "nohup", "exec", "if", "then", "else", "elif", "do", "while", "until", "!"]);
// git que reescribe archivos del arbol de trabajo, siempre o con ciertas opciones.
const GIT_ESCRIBE_ARBOL = new Set(["apply", "am", "restore", "clean", "rm", "mv", "checkout-index", "read-tree"]);
const GIT_ESCRIBE_CON = {
  reset: ["--hard", "--merge", "--keep"],
  checkout: ["--", ".", "-f", "--force", "-p", "--patch", "--ours", "--theirs"],
  switch: ["-f", "--force", "--discard-changes"],
};
// `git stash` saca los cambios del arbol; solo `list` y `show` leen.
const GIT_STASH_LEE = new Set(["list", "show"]);
// APIs de .NET que escriben, desde PowerShell.
const DOTNET_ESCRIBE = /\[(system\.)?io\.(file|directory)\]::(write|append|copy|move|delete|create|replace)/i;
// Destinos de redireccion que no son archivos.
const NULOS = /^(\/dev\/null|nul:?|\$null|&\d?|-)$/i;

function permitir() {
  return { codigo: 0, stdout: "", stderr: "" };
}

function denegar(motivo) {
  const texto = `[SDD Lite] Bloqueado por .claude/hooks/supervisor.mjs\n${motivo}`;
  return {
    codigo: 2,
    stdout: JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: texto,
      },
    }),
    stderr: `${texto}\n`,
  };
}

/** Minusculas y sin tildes, para comparar encabezados escritos de cualquier forma. */
function normalizar(texto) {
  return String(texto).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function faltanEncabezados(tipo, prompt) {
  const texto = normalizar(prompt || "");
  return ENCABEZADOS[tipo].filter((e) => !new RegExp(`^[ \\t]*##[ \\t]+${e}`, "m").test(texto));
}

/** Ruta relativa a la raiz con `/`, o null si queda fuera. Sin distinguir mayusculas en Windows. */
function rutaEnProyecto(ruta, raiz) {
  const ajustar = (p) => (process.platform === "win32" ? p.toLowerCase() : p);
  const base = ajustar(resolve(raiz));
  const destino = ajustar(resolve(base, ruta));
  const rel = relative(base, destino);
  if (rel === "") return "";
  if (isAbsolute(rel) || rel === ".." || rel.startsWith(`..\\`) || rel.startsWith("../")) return null;
  return rel.replace(/\\/g, "/");
}

function esRegistro(rel) {
  const r = rel.toLowerCase();
  return PREFIJOS_REGISTRO.some((p) => r.startsWith(p)) || ARCHIVOS_REGISTRO.includes(r);
}

/** Redirecciones `>` y `>>` a un archivo, fuera de comillas y de cuerpos de heredoc. */
function redireccionAArchivo(fuera) {
  const sinComillas = fuera.replace(/"(?:\\.|[^"\\])*"|'[^']*'/g, "\"\"");
  for (const m of sinComillas.matchAll(/(?:\d|\*)?>>?\|?\s*(&\d?|[^\s;&|()<>]*)/g)) {
    if (!NULOS.test(m[1])) return m[1] || "(sin destino)";
  }
  return null;
}

/** Motivo por el que yarn, pnpm, npx o bunx (que lib.mjs quita como envoltorios) instalan o generan, o null. */
function envoltorioInstala(comando, profundidad = 0) {
  if (profundidad > 5) return null;
  const { fuera, cuerpos } = separarCuerpos(comando);
  for (const c of cuerpos) {
    const m = c.tipo === "shell" ? envoltorioInstala(c.texto, profundidad + 1) : null;
    if (m) return m;
  }
  for (const seg of trocear(fuera)) {
    const t = tokens(seg);
    let i = 0;
    while (i < t.length && (PREVIOS.has(t[i].toLowerCase()) || /^[A-Za-z_][A-Za-z0-9_]*=/.test(t[i]))) i += 1;
    const verbo = verboDe(t[i]);
    const args = t.slice(i + 1);
    const sub = (args.find((a) => !a.startsWith("-")) || "").toLowerCase();
    if (SHELLS.has(verbo)) {
      // bash -c, pwsh -Command y cmd /c: se mira el comando interior.
      const k = args.findIndex((a) => /^-[a-z]*c$|^-command$|^\/[ck]$/i.test(a));
      const m = k >= 0 ? envoltorioInstala(args.slice(k + 1).join(" "), profundidad + 1) : null;
      if (m) return m;
    }
    if (verbo === "yarn" && !sub) return "`yarn` sin subcomando, que instala";
    if ((verbo === "yarn" || verbo === "pnpm") && ENVOLTORIO_INSTALA.has(sub)) return `\`${verbo} ${sub}\``;
    if (verbo === "npx" || verbo === "bunx") {
      if (args.some((a) => /^(-y|--yes|-p|--package)(=|$)/.test(a))) return `\`${verbo}\` que instala un paquete`;
      if (/^(@[^/]+\/)?create(-|$)/.test(sub)) return `\`${verbo} ${sub}\`, que genera un proyecto`;
    }
  }
  return null;
}

/** Subcomando de npm y su accion, saltando opciones globales y sus valores. */
function subNpm(t) {
  for (let i = 1; i < t.length; i += 1) {
    if (NPM_FLAGS_CON_VALOR.has(t[i])) {
      i += 1;
      continue;
    }
    if (!t[i].startsWith("-")) {
      return { sub: t[i].toLowerCase(), accion: (t.slice(i + 1).find((a) => !a.startsWith("-")) || "").toLowerCase() };
    }
  }
  return { sub: "", accion: "" };
}

/** Motivo por el que git reescribe el arbol de trabajo, o null. */
function gitEscribe(t) {
  const resto = t.slice(1);
  const k = resto.findIndex((a, i, r) => !a.startsWith("-") && !["-C", "-c"].includes(r[i - 1]));
  if (k < 0) return null;
  const sub = resto[k];
  const args = resto.slice(k + 1);
  if (GIT_ESCRIBE_ARBOL.has(sub)) return `\`git ${sub}\``;
  const op = GIT_ESCRIBE_CON[sub]?.find((o) => args.includes(o));
  if (op) return `\`git ${sub} ${op}\``;
  if (sub === "stash" && !GIT_STASH_LEE.has(args.find((a) => !a.startsWith("-")))) return "`git stash`";
  return null;
}

/** Motivo por el que un comando de shell escribe o instala, o null. */
function shellEscribe(comando) {
  const envuelto = envoltorioInstala(comando);
  if (envuelto) return envuelto;
  if (DOTNET_ESCRIBE.test(comando)) return "una API de .NET que escribe archivos";
  const destino = redireccionAArchivo(separarCuerpos(comando).fuera);
  if (destino) return `una redireccion a ${destino}`;
  for (const t of comandosAnalizables(comando)) {
    const m = tokensEscriben(t);
    if (m) return m;
  }
  return null;
}

/** Comando interior de `uv run` o `uvx`, o el motivo si instala con `--with`; null si no es uno de ellos. */
function interiorUv(t) {
  const verbo = verboDe(t[0]);
  let i;
  if (verbo === "uvx") i = 1;
  else if (verbo === "uv") {
    const k = t.findIndex((a, j) => j > 0 && !a.startsWith("-"));
    if (k < 0 || t[k].toLowerCase() !== "run") return null;
    i = k + 1;
  } else return null;
  while (i < t.length && t[i].startsWith("-")) {
    const op = t[i].split("=")[0];
    if (/^--with(-requirements|-editable)?$/.test(op)) return { motivo: `\`${verbo} ${op}\`, que instala paquetes` };
    if (!t[i].includes("=") && UV_FLAGS_CON_VALOR.has(op)) i += 1;
    i += 1;
  }
  return { interior: t.slice(i) };
}

/** Motivo por el que un formateador o un arreglo automatico reescribe archivos, o null. */
function formateaEscribe(verbo, t, sub) {
  const args = t.slice(1);
  const solo = (...ops) => args.some((a) => ops.includes(a.split("=")[0]));
  if (verbo === "ruff" && sub === "format" && !solo("--check", "--diff")) return "`ruff format`";
  if (verbo === "ruff" && sub === "check" && solo("--fix", "--fix-only") && !solo("--diff")) return "`ruff check --fix`";
  if (verbo === "black" && !solo("--check", "--diff")) return "`black`";
  if (verbo === "isort" && !solo("--check", "--check-only", "-c", "--diff")) return "`isort`";
  return null;
}

/** Motivo por el que un comando ya tokenizado escribe o instala, o null. */
function tokensEscriben(t, profundidad = 0) {
  if (!t.length || t[0] === "__codigo__" || profundidad > 5) return null;
  const verbo = verboDe(t[0]);
  const sub = (t.find((a, i) => i > 0 && !a.startsWith("-")) || "").toLowerCase();
  const uv = interiorUv(t);
  if (uv?.motivo) return uv.motivo;
  if (uv) return tokensEscriben(uv.interior, profundidad + 1);
  const formato = formateaEscribe(verbo, t, sub);
  if (formato) return formato;
  if (VERBOS_ESCRITURA.has(verbo)) return `\`${verbo}\``;
  if (VERBOS_INSTALA_ENVUELTOS.has(verbo)) return `\`${verbo}\` de un gestor de paquetes`;
  if (verbo === "npm") {
    const n = subNpm(t);
    if (INSTALA.npm.has(n.sub)) return `\`npm ${n.sub}\``;
    if (NPM_ACCION_ESCRIBE[n.sub]?.includes(n.accion)) return `\`npm ${n.sub} ${n.accion}\``;
  } else if (INSTALA[verbo]?.has(sub)) return `\`${verbo} ${sub}\``;
  if (PYTHON.has(verbo)) {
    const m = t.indexOf("-m");
    const modulo = m > 0 ? (t[m + 1] || "").toLowerCase() : "";
    const accion = m > 0 ? (t.slice(m + 2).find((a) => !a.startsWith("-")) || "").toLowerCase() : "";
    if (PYTHON_MODULO_ESCRIBE.has(modulo)) return `\`${verbo} -m ${modulo}\``;
    if (INSTALA[modulo]?.has(accion)) return `\`${verbo} -m ${modulo} ${accion}\``;
    const formatoModulo = formateaEscribe(modulo, t.slice(m + 1), accion);
    if (formatoModulo) return formatoModulo;
  }
  if ((verbo === "sed" || verbo === "perl") && t.some((a) => /^-[a-z]*i|^--in-place/i.test(a))) return `\`${verbo} -i\``;
  if (verbo === "git") {
    const m = gitEscribe(t);
    if (m) return m;
  }
  return null;
}

/**
 * Evalua una entrada de PreToolUse para el supervisor y devuelve `{ codigo, stdout, stderr }`,
 * con la misma forma que `evaluar` de guard-reglas.mjs.
 */
export function evaluarSupervisor(entrada, raiz, env = process.env) {
  if (env.SDD_SUPERVISOR_LIBRE === "1") return permitir();
  const herramienta = entrada?.tool_name;
  const datos = entrada?.tool_input || {};
  const enSubagente = Boolean(entrada?.agent_id);

  if (herramienta === "Agent") {
    if (enSubagente) {
      return denegar("Un subagente no delega en otro subagente.\nHaz el encargo tu mismo o devuelve el bloqueo al supervisor.");
    }
    const tipo = datos.subagent_type;
    if (!TIPOS.includes(tipo)) {
      return denegar(
        `El supervisor solo delega en los subagentes del proyecto; tipo recibido: ${tipo ? `\`${tipo}\`` : "ninguno"}.\n`
        + "Usa `ejecutor` (implementa), `explorador` (investiga, solo lectura) o `revisor` (revision adversarial).\n"
        + `El brief de cada uno esta en ${BRIEF}.`,
      );
    }
    const faltan = faltanEncabezados(tipo, datos.prompt);
    if (faltan.length) {
      return denegar(
        `El brief para \`${tipo}\` esta incompleto; faltan: ${faltan.map((e) => LEGIBLE[e]).join(", ")}.\n`
        + `Redactalo segun ${BRIEF}.`,
      );
    }
    return permitir();
  }

  if (ESCRITURA.has(herramienta) && !enSubagente) {
    const ruta = datos.file_path || datos.notebook_path;
    if (typeof ruta !== "string" || !ruta.trim()) return permitir();
    const rel = rutaEnProyecto(ruta, raiz);
    if (rel === null || esRegistro(rel)) return permitir();
    return denegar(
      `El supervisor no escribe en el proyecto: ${rel || "."}.\n`
      + "Solo escribe registros: docs/plans/, docs/changes/, docs/security.md y .claude/relevo/.\n"
      + `Encarga el cambio a un \`ejecutor\` (brief en ${BRIEF}).\n`
      + "Si el usuario quiere trabajar sin supervisor, que arranque la sesion con SDD_SUPERVISOR_LIBRE=1.",
    );
  }

  if (SHELL.has(herramienta) && !enSubagente && typeof datos.command === "string") {
    const motivo = shellEscribe(datos.command);
    if (motivo) {
      return denegar(
        `El supervisor no escribe archivos ni instala desde el shell: el comando usa ${motivo}.\n`
        + "Puede leer, usar git y gh y ejecutar npm run check; los registros los escribe con Write o Edit.\n"
        + `Encarga el cambio a un \`ejecutor\` (brief en ${BRIEF}).\n`
        + "Si el usuario quiere trabajar sin supervisor, que arranque la sesion con SDD_SUPERVISOR_LIBRE=1.",
      );
    }
  }

  return permitir();
}
