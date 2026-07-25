# Architecture

The Vue frontend calls the FastAPI backend through the `/api` path. Caddy provides the single
external entry point in the containerised environment.

The backend uses SQLAlchemy with a SQLite database stored at `data/expense.db`. Database sessions
are created in `app.database.session`; persistence models live in `app.models`.

The initial domain consists of:

- import batches that record the source and size of each import;
- raw transactions that preserve every CSV value and source line before cleaning;
- merchants identified from transaction descriptions;
- expenses, with monetary amounts stored as integer minor units and an explicit processing status;
- hierarchical categories;
- ordered categorisation rules that map description patterns to categories and remain linked to
  transactions they matched.

Transaction processing moves through `imported`, `normalised`, `merchant_identified`,
`categorised`, or `needs_review`.

SQLite foreign-key enforcement is enabled for every application connection. Connections also use
WAL journaling, a 30-second busy timeout, and `synchronous=NORMAL` so reads can continue during
writes and short write contention waits instead of failing immediately.
Alembic owns schema creation and upgrades; containers apply pending migrations before the API
starts.

CSV imports are atomic: malformed input is rejected without retaining a partial batch. Empty rows
are ignored, while header names and all non-empty row values are stored unchanged as JSON.
New uploads store a SHA-256 checksum and reject an exact file duplicate by referring the client to
the existing batch. Import history derives batch outcomes from raw-row errors and linked expense
statuses. Failed raw rows can be retried in place after parser improvements without duplicating the
batch or already-normalised expenses; the original fallback currency is retained for that retry.

Transaction normalisation is a pure service: it accepts a raw row and returns typed canonical
values without database access or input mutation. It standardises supported headers, dates,
descriptions, currencies, and converts decimal major-unit amounts to integer minor units. Ambiguous
US-style dates are intentionally rejected.

The processing coordinator is idempotent. It creates one linked expense for each valid pending raw
row and records normalisation failures on invalid rows. Merchant identification prefers the
longest, highest-confidence canonical-name match. Enabled categorisation rules use
case-insensitive substring matching and are evaluated by descending priority, then rule ID.
Transactions without a confident rule match move to `needs_review`.

`GET /api/review-queue` exposes those transactions in FIFO order with pagination, raw import
provenance, and any merchant or category context already attached.

Review corrections assign the selected category and can persist an enabled matching rule for
future transactions. Reporting endpoints aggregate only categorised transactions. Category totals
and monthly totals remain grouped by currency to avoid combining unlike monetary units.

Imported transaction amounts retain their bank-provided sign. Cash-flow reporting treats negative
non-Income and non-Transfer amounts as positive spending, lets positive refunds reduce that
spending, keeps Income signed, and excludes Transfers. Recurring-expense averages use only negative
spending transactions and are presented as positive outflow amounts. A recurring pattern requires
at least three distinct dates, a stable amount, and consistent weekly, fortnightly, monthly, or
annual intervals. Recurring results and CSV/XLSX exports honor the report date and currency filters.
Spreadsheet exports neutralize untrusted text beginning with formula-control characters before it
reaches CSV or XLSX cells. Download responses disable caching and MIME sniffing.

`GET /api/categories` returns a flat, case-insensitively sorted category list with parent IDs for
review selectors and client-side hierarchy rendering.

The default category taxonomy is seeded idempotently. Existing categories are never renamed,
reparented, or deleted. Containers apply the seed after migrations and before starting the API.

`POST /api/imports/csv` stores the raw batch and returns `202 Accepted` with a queued job.
A single in-process worker uses an independent database session to run normalisation, merchant
matching, and rule evaluation. Persisted job states and timestamps let clients poll batch details;
unexpected failures retain a bounded error message. Queued or interrupted work is re-enqueued when
the API starts, and failed or partially normalised batches can be retried idempotently. Merchant
management endpoints expose canonical merchants and description aliases; aliases are considered
alongside canonical names during identification.

Vue Router gives each workspace view a stable URL and lazy-loads its page bundle. Unknown paths
return to the dashboard. Vite proxies `/api` to the local FastAPI server during development, while
Caddy owns the same route in the containerised environment. Frontend unit and routing tests run
with Vitest as part of the standard project checks.

The operations console now includes Dashboard, Import, Review queue, Transactions, Rules,
Merchants, Categories, and Reports. Management APIs support transaction search and bulk category
assignment, rule editing, merchant merging, and safe category hierarchy changes. Reports include
monthly and category totals, recurring-pattern detection, and CSV/XLSX exports.

Statement import accepts CSV and XLSX directly. Text-based PDFs are supported when extraction
produces a comma- or tab-delimited table; scanned or unstructured PDFs must be converted before
upload to avoid unreliable financial parsing.

The application is currently unauthenticated and intended for trusted local use. The staged
server-session and multi-user authorisation design is documented in
`docs/authentication-strategy.md`.

