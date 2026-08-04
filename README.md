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
The Vite server uses a locally generated HTTPS certificate and the Makefile starts the API with
secure authentication cookies.

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
# Set CADDY_SITE_ADDRESS to your DNS name and replace AUTH_THROTTLE_SECRET.
# Example secret generation: openssl rand -hex 32
make up
```

Point the hostname in `CADDY_SITE_ADDRESS` at the server and allow TCP ports 80 and 443 plus UDP
443. Caddy obtains and persists TLS certificates in named Docker volumes. Never commit the real
`.env` file or reuse `AUTH_THROTTLE_SECRET` between deployments. Keep `AUTH_COOKIE_SECURE=true` in
production. Set `ALLOW_REGISTRATION=true` for initial enrolment; set it to `false` if public
self-registration is not intended after accounts have been created.

Authentication throttles resolve the original address only through explicitly trusted proxies.
The Compose default trusts loopback and Docker's private `172.16.0.0/12` network. If the proxy uses
a different private subnet, add only that subnet to `TRUSTED_PROXY_CIDRS`; never use `0.0.0.0/0` or
`::/0`, because that would allow clients to spoof `X-Forwarded-For`.

The first account additionally requires `ADMIN_BOOTSTRAP_SECRET`, entered as the initial owner
setup token on the registration page. Generate a separate random value with `openssl rand -hex
32`. The server checks it inside the atomic first-user transaction and ignores it after an
owner exists. Remove it from `.env` after the first owner has registered. If the
secret is missing before setup, initial registration fails closed.

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
by an `.env` entry. Set `PUBLIC_APP_URL` to the final HTTPS origin, such as
`https://folio.libranode.dev`, so verification and password-reset links use the public hostname.

Configure `MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_PASSWORD` in Render's
environment settings. Generate separate random values for `AUTH_THROTTLE_SECRET` and
`ADMIN_BOOTSTRAP_SECRET`; do not copy development secrets or commit a production `.env` file.

### Email delivery readiness

Verified email is required for workspace access, so validate delivery before enabling public
registration. The SMTP client requires certificate-verified STARTTLS (normally port 587 or a
provider-supported alternative such as 2525); implicit TLS on port 465 is not supported. The
`MAIL_FROM` address or domain must be authorised by the provider, including its required SPF and
DKIM DNS records.

After starting the VPS containers, probe DNS/TCP, STARTTLS, authentication, and SMTP readiness:

```bash
make email-check
```

Then send a real delivery test and confirm it arrives, including checking the spam folder:

```bash
make email-check EMAIL_TO=owner@example.com
```

The command exits non-zero on configuration, connectivity, TLS, authentication, or delivery
failure. The signed-in owner can repeat these checks through `GET
/api/auth/account/email-delivery/readiness` and `POST /api/auth/account/email-delivery/test`; the test
message is sent only to the signed-in owner and the action is recorded in the audit log.
Production APIs expose only a safe 503 response while detailed SMTP failures remain in server logs.

The persistent disk requires a paid instance and restricts the service to one instance, which is
also the supported topology for this SQLite application. Migrations and idempotent category seeding
run when the container starts. Before creating the first account, set `ALLOW_REGISTRATION=true`,
copy the generated `ADMIN_BOOTSTRAP_SECRET` from the Render environment into the registration form,
and then restore `ALLOW_REGISTRATION=false`. Removing the bootstrap secret after the initial
owner is claimed is recommended.

The application uses Argon2id passwords, verified email addresses, password recovery, opaque
server-side sessions, CSRF protection and workspace-scoped financial records. Email changes remain
pending until the replacement address is verified, so a delivery failure cannot invalidate the
working login address. The first registered owner atomically claims the workspace containing
data migrated from the original single-user installation. Every account directly owns one private
workspace, and its audit events are available from the Account page. Review the operational controls in
[`docs/authentication-strategy.md`](docs/authentication-strategy.md) before internet exposure,
especially encrypted backups and tested restoration.

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

