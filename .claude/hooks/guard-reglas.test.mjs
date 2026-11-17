// Pruebas de la guardia: `node --test .claude/hooks/` (las ejecuta tambien `npm run test:hooks`).
import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { evaluar } from "./guard-reglas.mjs";

const git = (cwd, ...args) => execFileSync("git", args, { cwd, stdio: "ignore" });
const repo = realpathSync(mkdtempSync(join(tmpdir(), "guard-repo-")));
const fuera = realpathSync(mkdtempSync(join(tmpdir(), "guard-fuera-")));
git(repo, "init", "-q", "-b", "main");
git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init");

const sinBarras = (p) => p.split(String.fromCharCode(92)).join("/");
// Ruta al estilo de Git Bash en Windows: C:\x\y -> /c/x/y.
const estiloMsys = (p) => sinBarras(p).replace(/^([A-Za-z]):/, (_, d) => `/${d.toLowerCase()}`);
const decide = (command, cwd = fuera) => evaluar({ tool_input: { command }, cwd }, repo);

test("git -C con ruta absoluta desde fuera del repo, en una rama de trabajo, se permite", () => {
  git(repo, "switch", "-q", "-c", "trabajo");
  assert.equal(decide(`git -C "${sinBarras(repo)}" commit -m x`).codigo, 0);
  assert.equal(decide(`cd "${sinBarras(repo)}" && git commit -m x`).codigo, 0);
  assert.equal(decide(`cd "${sinBarras(repo)}"; git commit -m x`).codigo, 0);
});

test("git -C con ruta de Git Bash (/c/...) se permite en rama de trabajo", () => {
  git(repo, "switch", "-q", "trabajo");
  assert.equal(decide(`git -C "${estiloMsys(repo)}" commit -m x`).codigo, 0);
  assert.equal(decide(`cd "${estiloMsys(repo)}" && git commit -m x`).codigo, 0);
});

test("git -C sobre main sigue bloqueado", () => {
  git(repo, "switch", "-q", "main");
  for (const ruta of [sinBarras(repo), estiloMsys(repo)]) {
    const r = decide(`git -C "${ruta}" commit -m x`);
    assert.equal(r.codigo, 2);
    assert.match(r.stderr, /rama protegida main/);
  }
});

test("una ruta que no es un repositorio sigue bloqueando por rama desconocida", () => {
  const r = decide(`git -C "${estiloMsys(fuera)}/no-existe" commit -m x`);
  assert.equal(r.codigo, 2);
  assert.match(r.stderr, /No se ha podido determinar la rama actual/);
});
