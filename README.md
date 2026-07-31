# Expense Tracker

A local-first spending planner that imports bank transactions, categorises them with reusable
merchant rules, and answers the practical question: how much can I safely spend before my next
income payment?

## Stack

- Vue 3, Vite, TypeScript, Plotly, and Tailwind CSS
- FastAPI and SQLAlchemy
- Persistent SQLite with Alembic migrations
- Docker Compose and Caddy

## Local setup

```bash
cp .env.example .env
make setup
make check
```

For local development, set `APP_ENV=development` in `.env`.

`make check` runs backend formatting and lint checks, all tests, a clean SQLite migration
upgrade/drift check, frontend type checking, and a production frontend build. Dependency audits
require registry access and can be run separately:

```bash
make dependency-audit
```

Run the development servers in separate terminals:

```bash
make database-upgrade
make database-seed
make backend-run
make frontend-run
```

## Container deployment

The default Compose deployment listens on `http://localhost:8080`, runs the API in production
mode, applies migrations, seeds the category hierarchy idempotently, and serves the compiled
frontend through Caddy:

```bash
cp .env.example .env
make up
```

To access the application from another device on a trusted LAN, use
`http://<host-ip>:8080`. Change `CADDY_HTTP_PORT` if that port is occupied. Set
`CADDY_BIND_ADDRESS=127.0.0.1` to prevent connections from other devices.

SQLite data, WAL files, and imported transaction records are stored under the host's `data/`
directory, which is excluded from Git. Uploaded statement contents are stored as database rows;
the source files are not retained as a separate upload directory.

### Inferred financial plans

`GET /api/plan-inference/preview?target_month=2026-08-01&currency=GBP`
builds a read-only suggestion from categorised transaction evidence. It returns the inferred
income payment, recurring commitments, variable essential allowances, confidence scores, and
the transaction IDs supporting every suggestion.

`POST /api/plan-inference/confirm` recomputes that evidence and creates only the proposal IDs
selected by the client. Previewing never writes plan data, and confirmation rejects unknown or
stale proposal IDs. At least two monthly categorised income transactions are required.
The Plan page exposes this preview-and-confirm workflow directly. Inference uses the latest six
months of evidence, ignores recurring patterns no longer seen recently, and nets refunds into
variable allowance estimates.

Before upgrading containers, stop the application and back up the database:

```bash
make down
cp data/expense.db "data/expense-$(date +%Y%m%d-%H%M%S).db"
make up
```

Do not run multiple API containers against this SQLite database. Imports use a tracked
single-process background worker, and interrupted queued or processing jobs are resumed when the
API starts.

The application currently has no authentication boundary. Expose it only on a trusted machine or
LAN behind an access-controlled reverse proxy. See
[`docs/authentication-strategy.md`](docs/authentication-strategy.md) before internet exposure or
multi-user use.

## Product areas

- Dashboard for usable balance, next income, bills, safe weekly spending, immediate risks, and
  realistic cost-reduction opportunities
- Payment-cycle planning with editable commitments and essential allowances
- CSV, XLSX, and text-based PDF statement import
- Low-confidence review queue with correction-to-rule workflow
- Searchable transactions with bulk category editing
- Rule, merchant alias, merchant merge, and category hierarchy management
- Payment-period, monthly, category, recurring-expense, and opportunity reports with Plotly charts
  and CSV/XLSX export

## Structure

- `backend/app/models/` – persistence models
- `backend/app/database/` – SQLite engine and session lifecycle
- `backend/app/api/` – FastAPI routes
- `backend/tests/` – backend tests
- `frontend/src/` – Vue application
- `infra/` – Docker Compose, images, and Caddy configuration
- `docs/` – architecture notes and the staged authentication strategy

