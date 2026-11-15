import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/** Create/migrate the isolated E2E database before any test runs. */
export default function globalSetup(): void {
  const repoRoot = path.resolve(__dirname, "../..");
  const backendDir = path.join(repoRoot, "backend");
  // Same interpreter resolution as playwright.config.ts: project venv on the
  // dev machine, runner Python in CI.
  const venvWindows = path.join(backendDir, ".venv", "Scripts", "python.exe");
  const venvPosix = path.join(backendDir, ".venv", "bin", "python");
  const python = fs.existsSync(venvWindows)
    ? venvWindows
    : fs.existsSync(venvPosix)
      ? venvPosix
      : "python";
  const script = path.join(repoRoot, "scripts", "prepare_e2e_db.py");
  execFileSync(python, [script], { stdio: "inherit", timeout: 240_000 });
}
