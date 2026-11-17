// Pruebas del supervisor: `node --test .claude/hooks/`.
import test from "node:test";
import assert from "node:assert/strict";
import { join } from "node:path";
import { evaluarSupervisor } from "./supervisor-reglas.mjs";

const raiz = join(process.cwd(), "proyecto-ficticio");
const escribe = (rel) => evaluarSupervisor(
  { tool_name: "Write", tool_input: { file_path: join(raiz, rel) } }, raiz, {},
).codigo;

test("el supervisor escribe registros en la raiz y dentro de un worktree", () => {
  assert.equal(escribe("docs/changes/a.md"), 0);
  assert.equal(escribe(".claude/worktrees/x/docs/changes/a.md"), 0);
  assert.equal(escribe(".claude/worktrees/x/docs/plans/p/plan.md"), 0);
  assert.equal(escribe(".claude/worktrees/x/docs/security.md"), 0);
  assert.equal(escribe(".claude/worktrees/x/.claude/relevo/r.md"), 0);
});

test("el supervisor sigue sin escribir fuera de los registros, tambien en un worktree", () => {
  assert.equal(escribe("src/a.py"), 2);
  assert.equal(escribe(".claude/worktrees/x/src/a.py"), 2);
  assert.equal(escribe(".claude/worktrees/x/.claude/hooks/guard.mjs"), 2);
  assert.equal(escribe(".claude/worktrees/x/docs/other.md"), 2);
});
