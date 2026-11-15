"""Verify backup/recovery end to end (Slice 11b).

Backs up the live dev database, restores it into a throwaway scratch database
(created and dropped by this script — never user data), and compares row
counts for every table. Exits non-zero on any mismatch.

    python scripts/verify_backup.py
"""

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRATCH_DB = "awc_restore_verify"


def _docker_exec(command: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "-i", "awc-db", *command], input=stdin, capture_output=True, check=False
    )


def _counts(db: str) -> dict[str, int]:
    result = _docker_exec(
        [
            "psql", "-U", "awc", "-d", db, "-t", "-A", "-c",
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode())
    tables = [line for line in result.stdout.decode().splitlines() if line]
    counts: dict[str, int] = {}
    for table in tables:
        counted = _docker_exec(
            ["psql", "-U", "awc", "-d", db, "-t", "-A", "-c", f'SELECT COUNT(*) FROM "{table}"']
        )
        counts[table] = int(counted.stdout.decode().strip())
    return counts


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        dump = pathlib.Path(tmp) / "verify.dump"
        backed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "backup_db.py"), "--output", str(dump)],
            capture_output=True,
        )
        if backed.returncode != 0:
            print(backed.stderr.decode(), file=sys.stderr)
            return 1
        print(backed.stdout.decode().strip())

        restored = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "restore_db.py"),
                "--dump", str(dump), "--target-db", SCRATCH_DB,
            ],
            capture_output=True,
        )
        if restored.returncode != 0:
            print(restored.stderr.decode(), file=sys.stderr)
            return 1
        print(restored.stdout.decode().strip())

    try:
        source = _counts("ai_writing_coach")
        target = _counts(SCRATCH_DB)
        if source != target:
            print("MISMATCH between source and restored counts:")
            for table in sorted(set(source) | set(target)):
                if source.get(table) != target.get(table):
                    print(f"  {table}: source={source.get(table)} restored={target.get(table)}")
            return 1
        print(f"PASS: {len(source)} tables, row counts identical after restore")
        return 0
    finally:
        dropped = _docker_exec(
            ["psql", "-U", "awc", "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"']
        )
        if dropped.returncode != 0:
            print(dropped.stderr.decode(), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
