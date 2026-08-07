#!/usr/bin/env bash

set -euo pipefail

DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/compose/docker-compose.yml}"
CADDY_HTTP_PORT="${CADDY_HTTP_PORT:-18080}"
CADDY_HTTPS_PORT="${CADDY_HTTPS_PORT:-18443}"
export CADDY_HTTP_PORT
export CADDY_HTTPS_PORT
export CADDY_SITE_ADDRESS="${CADDY_SITE_ADDRESS:-localhost}"
export AUTH0_DOMAIN="${AUTH0_DOMAIN:-example.auth0.com}"
export AUTH0_CLIENT_ID="${AUTH0_CLIENT_ID:-smoke-test-client}"
export AUTH0_AUDIENCE="${AUTH0_AUDIENCE:-https://api.folio.local}"

cleanup() {
  ${DOCKER_COMPOSE} -f "${COMPOSE_FILE}" down >/dev/null 2>&1 || true
}

trap cleanup EXIT

${DOCKER_COMPOSE} -f "${COMPOSE_FILE}" up -d --build

for _ in $(seq 1 30); do
  status="$(curl --silent --output /dev/null --write-out '%{http_code}' -H 'Host: localhost' "http://127.0.0.1:${CADDY_HTTP_PORT}/api/health" || true)"
  if [[ "${status}" == "200" || "${status}" == "308" ]]; then
    if ${DOCKER_COMPOSE} -f "${COMPOSE_FILE}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).read()" >/dev/null; then
      exit 0
    fi
  fi

  if ${DOCKER_COMPOSE} -f "${COMPOSE_FILE}" exec -T caddy wget -q -O - --header='Host: localhost' http://127.0.0.1/api/health >/dev/null 2>&1; then
    exit 0
  fi

  sleep 2
done

curl -i -H 'Host: localhost' "http://127.0.0.1:${CADDY_HTTP_PORT}/api/health" >&2 || true
${DOCKER_COMPOSE} -f "${COMPOSE_FILE}" logs >&2
exit 1

