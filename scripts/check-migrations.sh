#!/usr/bin/env bash
set -euo pipefail

migration_dir="$(mktemp -d)"
trap 'rm -rf "$migration_dir"' EXIT

python_command="${MIGRATION_PYTHON:-python3}"
export APP_ENV=test
export DATABASE_URL="sqlite:///$migration_dir/migration-check.db"

cd backend
"$python_command" -m alembic upgrade head
"$python_command" -m alembic check

