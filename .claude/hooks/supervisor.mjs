// Supervisor PreToolUse de SDD Lite: punto de entrada del hook.
//
// Contrato (docs oficiales de hooks): salir con 2 bloquea SIEMPRE y gana sobre el JSON.
// Un fallo al cargar las reglas o al leer la entrada bloquea por precaucion.
// Las reglas viven en supervisor-reglas.mjs para que la suite las evalue en proceso.

let r;
try {
  // Carga dinamica: si falta un modulo, el error cae en el catch y se bloquea.
  const { leerEntrada } = await import("./lib.mjs");
  const { evaluarSupervisor } = await import("./supervisor-reglas.mjs");
  const entrada = await leerEntrada();
  r = evaluarSupervisor(entrada, process.env.CLAUDE_PROJECT_DIR || entrada.cwd || process.cwd());
} catch (error) {
  const texto = `[SDD Lite] Bloqueado por .claude/hooks/supervisor.mjs\nEl supervisor no ha podido evaluar la herramienta: ${error.message}\n`
    + "Se bloquea por precaucion. Revisa .claude/hooks/supervisor-reglas.mjs o arranca la sesion con SDD_SUPERVISOR_LIBRE=1.";
  r = {
    codigo: 2,
    stdout: JSON.stringify({ hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: texto } }),
    stderr: `${texto}\n`,
  };
}
process.stdout.write(r.stdout);
process.stderr.write(r.stderr);
process.exit(r.codigo);
