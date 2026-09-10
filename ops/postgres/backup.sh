#!/usr/bin/env sh
set -eu
: "${PGHOST:=postgres}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=triada}"
: "${PGUSER:=triada}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${BACKUP_DIR:=/backups}"
: "${RETENTION_DAYS:=14}"
mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="$BACKUP_DIR/triada_${ts}.dump"
pg_dump --format=custom --no-owner --no-privileges --file="$out"
find "$BACKUP_DIR" -type f -name 'triada_*.dump' -mtime +"$RETENTION_DAYS" -delete
printf '%s\n' "$out"
