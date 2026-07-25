# Authentication strategy

## Current boundary

The application does not currently authenticate users. Treat it as a single-user local application:
do not expose the Vite development server or API directly to the public internet. Production access
should pass through Caddy over HTTPS.

Routing is client-side navigation, not an access-control boundary. Every API endpoint must enforce
authentication and authorisation independently before protected routes are added to the frontend.

## Recommended first implementation

Use server-managed sessions for the initial single-user deployment:

- store an application user with an Argon2id password hash;
- issue a cryptographically random, opaque session identifier after login;
- store only a hash of that identifier in SQLite, with creation, last-used, and expiry timestamps;
- send the identifier in a `Secure`, `HttpOnly`, `SameSite=Lax` cookie;
- rotate the session after login and invalidate it on logout or password change;
- require a CSRF token for every state-changing request;
- rate-limit login attempts and record security-relevant events without logging credentials,
  cookies, uploaded statement contents, or CSRF tokens.

Do not keep bearer tokens or session identifiers in `localStorage`. The frontend should call
`GET /api/auth/session` when it starts, redirect unauthenticated navigation to `/login`, and preserve
the intended local URL for navigation after a successful login. A `401` response should clear
client session state and return to login; a `403` should remain distinct and show an access-denied
state.

Suggested endpoints are:

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/session`
- `GET /api/auth/csrf`

## Multi-user authorisation

Before adding a second user, add ownership to all user data, including import batches, raw
transactions, expenses, merchants, aliases, rules, categories, and background jobs. Every query,
mutation, export, retry, and worker task must be scoped by the authenticated user ID. Add indexes
and foreign keys for that ownership and tests proving one user cannot read, change, export, or infer
another user's records by guessing IDs.

Shared categories or household access should be introduced as an explicit workspace/membership
model rather than by weakening ownership filters.

## Later options

OIDC or passkeys can replace password login when remote or multi-device access is needed. Keep the
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

