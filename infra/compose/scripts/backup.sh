#!/usr/bin/env sh
set -eu

umask 077
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE="$COMPOSE_DIR/compose.yml"
BACKUP_ROOT=${1:-"$COMPOSE_DIR/backups"}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
WRITERS_STOPPED=false
WRITER_SERVICES=""
WRITER_CONTAINERS=""

for service in \
  api \
  web \
  image-analysis-worker \
  material-parse-worker \
  curriculum-analysis-worker \
  data-lifecycle-worker; do
  if docker compose -f "$COMPOSE_FILE" config --services | grep -qx "$service"; then
    WRITER_SERVICES="$WRITER_SERVICES $service"
    container_id=$(docker compose -f "$COMPOSE_FILE" ps -aq "$service")
    if [ -n "$container_id" ]; then
      WRITER_CONTAINERS="$WRITER_CONTAINERS $container_id"
    fi
  fi
done

restart_writers() {
  if [ "$WRITERS_STOPPED" = true ]; then
    # Restart the original containers directly. `docker compose start` tries to
    # satisfy a completed migration dependency and cannot restore these services.
    # shellcheck disable=SC2086
    docker start $WRITER_CONTAINERS >/dev/null
  fi
}
trap restart_writers EXIT INT TERM

mkdir -p "$BACKUP_DIR/minio-data"

# Quiesce every application writer before copying object data. PostgreSQL's
# custom-format dump is transactionally consistent while the database stays up.
# Service names come from the checked Compose configuration above.
# shellcheck disable=SC2086
docker compose -f "$COMPOSE_FILE" stop $WRITER_SERVICES >/dev/null
WRITERS_STOPPED=true

docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  >"$BACKUP_DIR/postgres.dump"

docker compose -f "$COMPOSE_FILE" cp minio:/data/. "$BACKUP_DIR/minio-data" >/dev/null

(
  cd "$BACKUP_DIR"
  if command -v sha256sum >/dev/null 2>&1; then
    find postgres.dump minio-data -type f -print0 | sort -z | xargs -0 sha256sum
  else
    find postgres.dump minio-data -type f -print0 | sort -z | xargs -0 shasum -a 256
  fi
) >"$BACKUP_DIR/SHA256SUMS"

cat >"$BACKUP_DIR/manifest.txt" <<EOF
format=study-backup-v1
created_at_utc=$STAMP
postgres_format=custom
minio_snapshot=quiesced-volume-copy
contains_secrets=false
EOF

restart_writers
WRITERS_STOPPED=false
trap - EXIT INT TERM

printf '%s\n' "backup_complete=$BACKUP_DIR"
