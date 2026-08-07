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

For local development, set `APP_ENV=development` and `CADDY_SITE_ADDRESS=:80` in `.env`.
The Vite server uses a locally generated HTTPS certificate. Add its exact origin to the Auth0
application's callback, logout and web-origin allowlists.

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

The first frontend start creates a private development CA under `data/dev-tls/`. Trust
`data/dev-tls/folio-dev-ca.pem` in every operating system or browser that opens the application.
For LAN access, include a specific address when generating the certificate if it is not detected:

```bash
make dev-certificate DEV_HOST=192.168.10.84
make frontend-run
```

Then use `https://192.168.10.84:5173`. Never use the HTTP URL for registration or login. The CA
private key and generated certificates stay under ignored runtime data and must not be committed.

## Container deployment

The default Compose deployment expects a public HTTPS hostname, runs the API in production mode,
applies migrations, seeds the initial workspace category hierarchy idempotently, and serves the
compiled frontend through Caddy:

```bash
cp .env.example .env
# Set CADDY_SITE_ADDRESS and the AUTH0_DOMAIN, AUTH0_CLIENT_ID and AUTH0_AUDIENCE values.
make up
```

Point the hostname in `CADDY_SITE_ADDRESS` at the server and allow TCP ports 80 and 443 plus UDP
443. Caddy obtains and persists TLS certificates in named Docker volumes. Never commit the real
`.env` file. Auth0 controls public enrolment, identity recovery and identity-level abuse controls.

SQLite data, WAL files, and imported transaction records are stored under the host's `data/`
directory, which is excluded from Git. Uploaded statement contents are stored as database rows;
the source files are not retained as a separate upload directory.

### Inferred financial plans

`GET /api/plan-inference/preview?target_month=2026-08-01&currency=GBP`
builds a read-only suggestion from categorised transaction evidence. It returns separately
clustered recurring income sources, UK banking-day-adjusted payment dates, recurring commitments,
variable essential allowances, confidence scores, proposal states, an impact summary, and the
transaction IDs supporting every suggestion.

`POST /api/plan-inference/confirm` recomputes that evidence and creates only the proposal IDs
selected by the client. Previewing never writes plan data, and confirmation rejects unknown or
stale proposal IDs. At least two recurring categorised transactions are required for an income
source. The Plan page exposes this preview-and-confirm workflow directly, asks for balances only
after preview, and requires changed proposals to be selected explicitly. Inference uses the latest
six months of evidence, ignores recurring patterns no longer seen recently, separates stable payer
and amount clusters, and handles refunds without hiding recurring commitments.

Before upgrading containers, stop the application and back up the database:

```bash
make down
cp data/expense.db "data/expense-$(date +%Y%m%d-%H%M%S).db"
make up
```

Do not run multiple API containers against this SQLite database. Imports use a tracked
single-process background worker, and interrupted queued or processing jobs are resumed when the
API starts.

### Render deployment from Git

Create a Docker web service from the GitHub mirror of this repository. Leave Render's **Root
Directory** empty, set **Dockerfile Path** to `./infra/docker/render.Dockerfile`, and set **Docker
Build Context Directory** to `.`. Configure `/api/health` as the health-check path.

Add a Render persistent disk of at least 1 GB mounted at `/data`, then configure
`DATABASE_URL=sqlite:////data/expense.db`. The disk is Render infrastructure and is not represented
by an `.env` entry. Configure `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, and `AUTH0_AUDIENCE` in Render's
environment settings; do not commit production tenant configuration.

The persistent disk requires a paid instance and restricts the service to one instance, which is
also the supported topology for this SQLite application. Migrations and idempotent category seeding
run when the container starts.

Create an Auth0 Single Page Application and API, with its API identifier equal to
`AUTH0_AUDIENCE`. Add the deployed origin to Allowed Callback URLs, Allowed Logout URLs and Allowed
Web Origins. A post-login Action must add verified email and display name to the configured
namespaced access-token claims. The first authenticated identity atomically claims the legacy
workspace; subsequent identities receive isolated workspaces. See
[`docs/authentication-strategy.md`](docs/authentication-strategy.md) for the Action and deployment
checklist.

## Product areas

- Dashboard for usable balance, next income, bills, safe weekly spending, immediate risks, and
  realistic cost-reduction opportunities
- Payment-cycle planning with editable commitments and essential allowances
- CSV, XLSX, and text-based PDF statement import
- Low-confidence review queue with correction-to-rule workflow
- Searchable transactions with bulk category editing
- Rule, merchant alias, merchant merge, and category hierarchy management
- Payment-period, priority-distribution, category, recurring-expense, and opportunity reports with
  Plotly charts
  and CSV/XLSX export

## Structure

- `backend/app/models/` – persistence models
- `backend/app/database/` – SQLite engine and session lifecycle
- `backend/app/api/` – FastAPI routes
- `backend/tests/` – backend tests
- `frontend/src/` – Vue application
- `infra/` – Docker Compose, images, and Caddy configuration
- `docs/` – architecture notes and the staged authentication strategy

