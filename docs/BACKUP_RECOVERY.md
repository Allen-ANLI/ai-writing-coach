# Backup & Recovery

**Status:** Slice 11b (2026-11-15). Round-trip verified against the dev
database: 40 tables, identical row counts after restore. Re-verified
2026-11-15 in the takeover session (`verify_backup.py` → PASS, 136 KB dump,
scratch DB created and dropped automatically).

## Scripts

| Script | Purpose |
|---|---|
| `scripts/backup_db.py` | `pg_dump -Fc` via `docker exec` → timestamped file in `backups/` |
| `scripts/restore_db.py` | Restore a dump into a target DB; **refuses the live DB without `--force`** |
| `scripts/verify_backup.py` | Backup → restore into a throwaway scratch DB → compare every table's row count → drop scratch |

## Routine backup

```bash
python scripts/backup_db.py                       # backups/awc-<stamp>.dump
python scripts/backup_db.py --output /secure/awc.dump
```

Schedule daily (cron/Task Scheduler) and retain per policy; copy off-host.
The dump is custom-format, compressed, and includes the pgvector extension
schema (the target cluster must have the vector extension available — the
pgvector image provides it).

## Restore

```bash
# Into a scratch database (safe):
python scripts/restore_db.py --dump backups/awc-<stamp>.dump --target-db awc_restore

# Into the live database (DESTRUCTIVE — requires explicit --force):
python scripts/restore_db.py --dump backups/awc-<stamp>.dump --target-db ai_writing_coach --force
```

`pg_restore --clean --if-exists --no-owner` replaces objects in the target.
Restoring into the live DB overwrites current data — this is an irreversible
operation and requires explicit operator approval (Directive §6).

## Verification

```bash
python scripts/verify_backup.py
# PASS: 40 tables, row counts identical after restore
```

Run after any backup-policy change and periodically as a recovery drill.

## Notes

- Backups contain user data (essays, expressions, billing). Store encrypted
  and access-controlled; they are subject to the same retention/deletion
  policy as the live data (account deletion removes live rows; backups rotate
  out per retention — see ADR-022).
- The scratch verification database is created and dropped by the script
  itself; it never touches user data.
