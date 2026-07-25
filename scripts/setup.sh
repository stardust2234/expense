#!/usr/bin/env bash
set -euo pipefail

ci_mode=false
install_hooks=true

for arg in "$@"; do
  case "$arg" in
    --ci)
      ci_mode=true
      install_hooks=false
      ;;
    --skip-hooks)
      install_hooks=false
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e "./backend[dev]"
python -m pip check

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to install the frontend dependencies." >&2
  exit 1
fi

if [[ "$ci_mode" == "true" && -f frontend/package-lock.json ]]; then
  (cd frontend && npm ci)
else
  (cd frontend && npm install)
fi

(cd frontend && npm ls --all >/dev/null)

if [[ "$install_hooks" == "true" ]]; then
  git config core.hooksPath .gitea/hooks
  chmod +x .gitea/hooks/pre-commit .gitea/hooks/pre-push
fi

echo "Environment ready. Activate it with: source .venv/bin/activate"
echo "Frontend dependencies installed in frontend/"

if [[ "$install_hooks" == "true" ]]; then
  echo "Local hooks installed from .gitea/hooks"
else
  echo "Local hook installation skipped"
fi

