"""Restore a pg_dump custom-format backup into a target database.

SAFETY: refuses to restore into the live default database unless --force is
given. The target database is created if missing. Example:
    python scripts/restore_db.py --dump backups/awc.dump --target-db awc_restore
"""

import argparse
import pathlib
import subprocess
import sys

LIVE_DB = "ai_writing_coach"


def _docker_exec(container: str, command: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "-i", container, *command],
        input=stdin,
        capture_output=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="awc-db")
    parser.add_argument("--user", default="awc")
    parser.add_argument("--dump", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--force", action="store_true", help="allow restoring into the live DB")
    args = parser.parse_args()

    dump = pathlib.Path(args.dump)
    if not dump.exists():
        print(f"dump not found: {dump}", file=sys.stderr)
        return 1
    if args.target_db == LIVE_DB and not args.force:
        print(
            f"refusing to restore into the live database '{LIVE_DB}' without --force",
            file=sys.stderr,
        )
        return 1

    created = _docker_exec(
        args.container,
        ["psql", "-U", args.user, "-d", "postgres", "-c", f'CREATE DATABASE "{args.target_db}"'],
    )
    if created.returncode != 0 and "already exists" not in created.stderr.decode():
        sys.stderr.write(created.stderr.decode("utf-8", errors="replace"))
        return created.returncode

    restored = _docker_exec(
        args.container,
        ["pg_restore", "-U", args.user, "-d", args.target_db, "--clean", "--if-exists", "--no-owner"],
        stdin=dump.read_bytes(),
    )
    if restored.returncode != 0:
        sys.stderr.write(restored.stderr.decode("utf-8", errors="replace"))
        return restored.returncode
    print(f"restored {dump} into {args.target_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
