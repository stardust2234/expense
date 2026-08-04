# Authentication strategy

## Current boundary

The backend supports Argon2id password registration and login, verified email addresses, password
recovery, hashed opaque server sessions, CSRF tokens, logout/revocation, account deletion, audit
logging, and atomic initial-owner claiming of the migrated workspace.
Production access must pass through Caddy over HTTPS so the secure session cookie is transmitted.

User, opaque-session, workspace and persistent login-throttle tables are present. All
pre-existing financial records belong to one initial workspace, ownership is non-null, and the
first registered owner atomically claims that workspace. Protected API requests, exports,
inference and worker processing are scoped through the authenticated workspace.

Routing is client-side navigation, not an access-control boundary. Every API endpoint must enforce
authentication and authorisation independently before protected routes are added to the frontend.

## Implemented session model

Use server-managed sessions for every workspace:

- store an application user with an Argon2id password hash;
- issue a cryptographically random, opaque session identifier after login;
- store only a hash of that identifier in SQLite, with creation, last-used, and expiry timestamps;
- send the identifier in a `Secure`, `HttpOnly`, `SameSite=Lax` cookie;
- rotate the session after login, invalidate it on logout, and revoke other sessions after a
  password change;
- require a CSRF token for every state-changing request;
- reuse a valid authenticated CSRF token so one browser tab cannot invalidate another;
- rate-limit login and email actions with both identity-plus-IP and aggregate-IP buckets, without
  storing plaintext email/IP throttle identities or logging
  credentials, cookies, uploaded statement contents, or CSRF tokens.

Do not keep bearer tokens or session identifiers in `localStorage`. The frontend should call
`GET /api/auth/session` when it starts, redirect unauthenticated navigation to `/login`, and preserve
the intended local URL for navigation after a successful login. A `401` response should clear
client session state and return to login; a `403` should remain distinct and show an access-denied
state.

Implemented authentication and account endpoints are:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/session`
- `GET /api/auth/csrf`
- `POST /api/auth/verify-email`
- `POST /api/auth/verification/resend`
- `POST /api/auth/password-reset/request`
- `POST /api/auth/password-reset/confirm`
- `POST /api/auth/password/change`
- `PATCH /api/auth/account/email`
- `DELETE /api/auth/account`
- `GET /api/auth/sessions`
- `DELETE /api/auth/sessions/id/{session_id}`
- `POST /api/auth/sessions/revoke-others`
- `GET /api/auth/account/audit`

Email address changes are staged in `pending_email`. The current login address remains valid until
the new address proves ownership with its single-use token. A production delivery failure clears
the pending address rather than locking the user out. Database uniqueness conflicts are returned as
controlled `409` responses.

## Workspace ownership

Ownership covers import batches/background jobs, raw transactions, expenses, merchants, aliases,
rules, categories, plans, commitments, allowances and recurring opportunities. Global ORM policy
scopes reads, ID lookups, updates and deletes; worker sessions adopt the claimed batch workspace.
Cross-user tests prove that listing and guessed-ID mutation cannot cross the workspace boundary.

Each account directly owns one private workspace through `workspaces.owner_user_id`. The owner
relationship is unique in both directions; there are no workspace roles or shared memberships.

## Later options

OIDC or passkeys can replace password login when stronger identity assurance is needed. Keep the
same application session cookie after the external identity exchange so identity-provider tokens
do not reach browser storage. Add MFA and a tested recovery process before relying on the
application for internet-facing financial data.

## Deployment checklist

- Terminate HTTPS at Caddy and trust forwarded headers only from that proxy.
- Keep signing keys and bootstrap credentials outside source control and rotate them.
- Set restrictive content-security, framing, referrer, and MIME-sniffing headers.
- Encrypt and test restoration of database backups.
- Apply session expiry, idle timeout, revocation, and login throttling.
- Test CSRF, session fixation, logout, cross-user object access, and background-job ownership.
- Only then enable frontend route guards and expose the service beyond a trusted local network.

