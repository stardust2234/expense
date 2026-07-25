FROM node:22-alpine AS build

WORKDIR /srv/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

COPY frontend ./

RUN npm run build

FROM caddy:2-alpine

COPY infra/caddy/frontend.Caddyfile /etc/caddy/Caddyfile
COPY --from=build /srv/frontend/dist /srv/frontend

EXPOSE 4173

