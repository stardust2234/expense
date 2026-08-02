FROM node:22-alpine AS frontend-build

WORKDIR /srv/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

COPY frontend ./
RUN npm run build

FROM caddy:2-alpine AS caddy-binary

FROM python:3.12-slim

WORKDIR /srv/backend

COPY backend/pyproject.toml backend/README.md backend/alembic.ini ./
COPY backend/app ./app
COPY backend/alembic ./alembic

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && python -m pip check

COPY --from=caddy-binary /usr/bin/caddy /usr/bin/caddy
COPY --from=frontend-build /srv/frontend/dist /srv/frontend
COPY infra/caddy/render.Caddyfile /etc/caddy/Caddyfile
COPY scripts/render-start.sh /usr/local/bin/render-start

RUN chmod 0755 /usr/local/bin/render-start \
    && mkdir -p /data

EXPOSE 10000

CMD ["render-start"]

