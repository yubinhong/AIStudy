#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
compose_dir="$repo_dir/infra/compose"
test_dir=$(mktemp -d "${TMPDIR:-/tmp}/study-compose-toggle.XXXXXX")
trap 'rm -rf "$test_dir"' EXIT

cp "$compose_dir/compose.yml" "$compose_dir/compose.local-model.yml" "$test_dir/"
cp "$compose_dir/.env.example" "$test_dir/.env"

compose=(docker compose --project-directory "$test_dir" --env-file "$test_dir/.env")
base_services=$("${compose[@]}" -f "$test_dir/compose.yml" config --services)
if printf '%s\n' "$base_services" | rg -qx 'local-model'; then
  printf '%s\n' 'disabled Compose unexpectedly contains local-model' >&2
  exit 1
fi

enabled_services=$(STUDY_LOCAL_MODEL_ENABLED=true "${compose[@]}" \
  -f "$test_dir/compose.yml" \
  -f "$test_dir/compose.local-model.yml" \
  config --services)
if ! printf '%s\n' "$enabled_services" | rg -qx 'local-model'; then
  printf '%s\n' 'enabled Compose does not contain local-model' >&2
  exit 1
fi

printf '%s\n' 'compose local-model toggle passed'
