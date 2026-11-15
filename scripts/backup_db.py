"""Back up the PostgreSQL database to a custom-format pg_dump file.

Uses docker exec against the running database container (no host PostgreSQL
client required). Example:
    python scripts/backup_db.py --output backups/awc.dump
"""

import argparse
import datetime
import pathlib
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="awc-db")
    parser.add_argument("--user", default="awc")
    parser.add_argument("--db", default="ai_writing_coach")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.output:
        output = pathlib.Path(args.output)
    else:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output = pathlib.Path("backups") / f"awc-{stamp}.dump"
    output.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["docker", "exec", args.container, "pg_dump", "-U", args.user, "-d", args.db, "-Fc"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
        return result.returncode
    output.write_bytes(result.stdout)
    print(f"backup written: {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
