# Expense Categoriser

A small full-stack application for recording expenses and assigning categories with reusable
matching rules.

## Stack

- Vue 3, Vite, TypeScript, and Tailwind CSS
- FastAPI and SQLAlchemy
- SQLite
- Docker Compose and Caddy

## Local setup

```bash
cp .env.example .env
make setup
make check
```

Run the development servers in separate terminals:

```bash
make database-upgrade
make database-seed
make backend-run
make frontend-run
```

Run the containerised stack at `http://localhost`:

```bash
make up
```

SQLite data is stored under `data/` and excluded from Git.

## Product areas

- Dashboard for monthly spending, income, net position, and category totals
- CSV, XLSX, and text-based PDF statement import
- Low-confidence review queue with correction-to-rule workflow
- Searchable transactions with bulk category editing
- Rule, merchant alias, merchant merge, and category hierarchy management
- Monthly, category, and recurring-expense reports with CSV/XLSX export

## Structure

- `backend/app/models/` – persistence models
- `backend/app/database/` – SQLite engine and session lifecycle
- `backend/app/api/` – FastAPI routes
- `backend/tests/` – backend tests
- `frontend/src/` – Vue application
- `infra/` – Docker Compose, images, and Caddy configuration
- `docs/` – architecture notes and the staged authentication strategy

The current build has no login boundary and is intended for trusted local use. See
[`docs/authentication-strategy.md`](docs/authentication-strategy.md) before exposing it remotely or
adding multiple users.

