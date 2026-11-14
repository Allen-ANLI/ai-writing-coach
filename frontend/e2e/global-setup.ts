import { execFileSync } from "node:child_process";
import path from "node:path";

/** Create/migrate the isolated E2E database before any test runs. */
export default function globalSetup(): void {
  const repoRoot = path.resolve(__dirname, "../..");
  const python = path.join(repoRoot, "backend", ".venv", "Scripts", "python.exe");
  const script = path.join(repoRoot, "scripts", "prepare_e2e_db.py");
  execFileSync(python, [script], { stdio: "inherit", timeout: 240_000 });
}
