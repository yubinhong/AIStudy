#!/usr/bin/env sh
set -eu

BACKUP_DIR=${1:?usage: verify-restore.sh /path/to/backup}
POSTGRES_IMAGE=${POSTGRES_IMAGE:-postgres:16.10}
CONTAINER="study-restore-verify-$$"
VERIFY_PASSWORD="restore-verify-$$"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

test -f "$BACKUP_DIR/manifest.txt"
test -f "$BACKUP_DIR/postgres.dump"
test -f "$BACKUP_DIR/SHA256SUMS"
test -d "$BACKUP_DIR/minio-data"
grep -qx 'format=study-backup-v1' "$BACKUP_DIR/manifest.txt"

(
  cd "$BACKUP_DIR"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -c SHA256SUMS >/dev/null
  else
    shasum -a 256 -c SHA256SUMS >/dev/null
  fi
)

docker run -d --name "$CONTAINER" \
  -e POSTGRES_PASSWORD="$VERIFY_PASSWORD" \
  -e POSTGRES_DB=study_restore_verify \
  "$POSTGRES_IMAGE" >/dev/null

attempt=0
until docker exec "$CONTAINER" pg_isready -U postgres -d study_restore_verify >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    printf '%s\n' 'restore_verify_failed=postgres_not_ready' >&2
    exit 1
  fi
  sleep 1
done

docker exec -i "$CONTAINER" pg_restore \
  -U postgres -d study_restore_verify --no-owner --no-acl --exit-on-error \
  <"$BACKUP_DIR/postgres.dump" >/dev/null

TABLE_COUNT=$(docker exec "$CONTAINER" psql -U postgres -d study_restore_verify -Atc \
  "select count(*) from information_schema.tables where table_schema='public'")
if [ "$TABLE_COUNT" -lt 1 ]; then
  printf '%s\n' 'restore_verify_failed=no_public_tables' >&2
  exit 1
fi

MINIO_FILE_COUNT=$(find "$BACKUP_DIR/minio-data" -type f | wc -l | tr -d ' ')
printf '%s\n' 'restore_verify_complete=true'
printf '%s\n' "postgres_public_tables=$TABLE_COUNT"
printf '%s\n' "minio_snapshot_files=$MINIO_FILE_COUNT"
