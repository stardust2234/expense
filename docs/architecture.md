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
the existing batch. Different files with overlapping date ranges are deduplicated after
normalisation using date, canonical description, signed amount, and currency. Matching is
occurrence-aware, so two genuinely identical same-day payments remain two payments when both
statements contain them. Skipped raw rows retain a link to the earlier Expense and are reported as
duplicates rather than failures. Import history derives batch outcomes from raw-row errors,
duplicate links, and linked expense statuses. Failed raw rows can be retried in place after parser
improvements without duplicating the batch or already-normalised expenses; the original fallback
currency is retained for that retry.

Transaction normalisation is a pure service: it accepts a raw row and returns typed canonical
values without database access or input mutation. It standardises supported headers, dates,
descriptions, currencies, and converts decimal major-unit amounts to integer minor units. Slash
dates default to UK day/month order; known Revolut Started/Completed Date fields use that export's
month/day order.

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

`POST /api/imports/file` stores a supported statement and returns `202 Accepted` with a queued job.
A single in-process worker uses an independent database session to run normalisation, merchant
matching, and rule evaluation. Persisted job states, claim tokens, and expiring leases prevent two
processes from claiming the same live job. Startup recovery re-enqueues queued work and only
reclaims processing work after its lease expires. Unexpected failures retain a bounded error
message, and failed or partially normalised batches can be retried idempotently. Merchant
management endpoints expose canonical merchants and description aliases; aliases are considered
alongside canonical names during identification.

Vue Router gives each workspace view a stable URL and lazy-loads its page bundle. Unknown paths
return to the dashboard. Vite proxies `/api` to the local FastAPI server during development, while
Caddy owns the same route in the containerised environment. Frontend unit and routing tests run
with Vitest as part of the standard project checks.

The operations console includes Dashboard, Import, Plan, Review queue, Transactions, Rules,
Merchants, Categories, and Reports. Management APIs support transaction search and bulk category
assignment, rule editing, merchant merging, safe category hierarchy changes, payment-cycle
planning, and recurring-opportunity assessment. Reports include payment-period, monthly, category,
and recurring-pattern analysis with CSV/XLSX exports.

Statement import accepts CSV and XLSX directly. Text-based PDFs are supported when extraction
produces a comma- or tab-delimited table; scanned or unstructured PDFs must be converted before
upload to avoid unreliable financial parsing.

Auth0 Universal Login owns registration, login, email verification, recovery and identity sessions.
FastAPI validates RS256 access tokens against the configured issuer, audience and JWKS. The immutable
Auth0 `sub` maps to a local user, and each user directly owns one workspace through the unique
`workspaces.owner_user_id` relationship; there are no workspace roles or shared memberships. Every
financial API and background worker still applies the local workspace authorization boundary.
Operational details are documented in `docs/authentication-strategy.md`.

Safe-spending planning is stored separately from imported bank data. Categories provide a default
spending priority and individual expenses may override it. Payment cycles hold the expected income
window and balance snapshot; commitments represent unpaid bills; cycle allowances represent food,
transport, irregular-cost, emergency, or custom reserves. Deleting a payment cycle cascades to its
commitments and allowances but only detaches its imported expenses.

The default taxonomy seeds an explicit priority for every supplied category. Protected housing and
core bills, essential daily costs, adjustable costs, optional spending, irregular essentials, and
non-spending transfers are distinct. Category APIs and the Categories page expose these defaults;
the idempotent seed never overwrites a later user edit. Savings and investment movements are treated
as transfers in cash-flow reports rather than consumption.

Payment-cycle CRUD is exposed at `/api/payment-cycles`; commitments are listed and created beneath
their cycle and updated or deleted at `/api/commitments/{id}`. Cycles in the same currency cannot
overlap. A commitment must use its cycle's currency and have a due date inside that cycle, and cycle
dates cannot be changed in a way that excludes an existing commitment.

Allowances and reserves are listed and created at
`/api/payment-cycles/{id}/allowances` and managed at `/api/allowances/{id}`. A category can feed at
most one allowance in a cycle, preventing the same spending from reducing multiple reserves.
Category-linked allowances deduct net outflows already spent in that cycle; category-less reserves
retain their full value. Creating or changing a payment cycle automatically associates unassigned
same-currency expenses in its half-open date window, so imported spending can consume the relevant
category allowance without manual transaction linking.

`GET /api/payment-cycles/{id}/forecast` is an as-of-date projection backed by a pure calculation
service. Calendar cycles remain reporting boundaries, while the forecast rolls a passed monthly
income date forward and includes commitments and allowances due before that genuinely next income.
It subtracts pending commitments and remaining allowances from the current balance. When no current
snapshot exists it derives the usable balance from the opening balance and signed transactions to
date. It never presents a negative discretionary amount,
and reports any shortfall separately. It also returns safe daily and weekly amounts, remaining
days, essential-cost coverage, allowance consumption, and immediate risks. All monetary values
remain integer minor units.

Payment-period reporting groups signed cash flow by calendar payment cycle while retaining the
separate benefit date recorded for that month. It preserves income, transfer, and refund semantics and breaks spending down by effective
priority, using a transaction override before its category default.

Recurring-cost opportunities build on stable cadence detection. The application annualises each
pattern to a comparable monthly cost but does not invent an alternative price. Users can persist a
researched replacement cost, one-off switching cost, difficulty, and decision; monthly and
first-year savings are then calculated and ranked. Rejected opportunities remain visible as an
explicit decision rather than repeatedly being suggested.

The homepage is intentionally a decision-only view: usable balance, next expected income, unpaid
bills, safe weekly spending, essential allowances remaining, projected period-end balance,
immediate risks, and up to three assessed savings opportunities. Payment-cycle setup, balance
updates, commitments, and allowances live on `/plan`; transaction detail and longer-term analysis
remain on their dedicated secondary pages.

The Plan page can preview a plan inferred from the latest six months of categorised evidence.
Recurring income and commitments must be recent, category allowances net refunds against spending,
and users select individual proposals before confirmation writes anything.

