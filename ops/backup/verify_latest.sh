#!/usr/bin/env sh
set -eu
: "${BACKUP_DIR:=/backups}"
latest="$(find "$BACKUP_DIR" -type f -name 'triada_*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)"
if [ -z "$latest" ]; then
  echo "No backup found" >&2
  exit 1
fi
pg_restore --list "$latest" >/dev/null
printf 'backup_ok %s\n' "$latest"
