#!/usr/bin/env bash
set -euo pipefail

compose_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$compose_dir"

enabled=$(docker compose -f compose.yml config --environment \
  | sed -n 's/^STUDY_LOCAL_MODEL_ENABLED=//p' \
  | tail -n 1)

compose_files=(-f compose.yml)
case "$enabled" in
  true)
    compose_files+=(-f compose.local-model.yml)
    ;;
  false)
    ;;
  *)
    printf 'STUDY_LOCAL_MODEL_ENABLED must be exactly true or false (got %s)\n' "$enabled" >&2
    exit 2
    ;;
esac

exec docker compose "${compose_files[@]}" "$@"
