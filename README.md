# Project Starter

This repository is a reusable full-stack starter meant to be cloned directly in Gitea when you create a new private project.

It includes:

- `frontend/`: Vue 3 + Vite + TypeScript + Tailwind CSS
- `backend/`: FastAPI + PostgreSQL integration
- `infra/`: Docker, Docker Compose, and Caddy
- `.gitea/`: workflows, hooks, pull-request template, and Gitea-specific automation helpers

## Quick Start

1. Copy `.env.example` to `.env`
2. Run `make setup`
3. Start the stack with `make up`
4. Open `http://localhost`
5. Run checks with `make check`

## Default Stack

- Frontend: Vue 3, Vite, TypeScript, Tailwind CSS
- Backend/API: FastAPI
- Database: PostgreSQL
- Deployment baseline: Docker, Docker Compose, Caddy reverse proxy

## Governance

- `make bootstrap-protection ORG=your-org REPO=your-repo`

Set `RENOVATE_ENDPOINT` to your Gitea API base URL when using the branch-protection helper.

## Structure

- `frontend/` frontend application
- `backend/` backend API and tests
- `infra/` deployment assets
- `.gitea/` workflows, hooks, pull-request template, and Gitea-specific automation helpers
- `scripts/` root automation helpers for setup
- `docs/` project notes
- `data/` local persistent files
