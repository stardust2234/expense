# Auth0 authentication and workspace isolation

## Trust boundary

Auth0 owns registration, login, password recovery, email verification, MFA and identity sessions.
The Vue application uses Auth0 Universal Login and requests an access token for the configured API
audience. The FastAPI application accepts only RS256 bearer access tokens whose signature, issuer,
audience and lifetime validate against the tenant's JWKS endpoint.

Auth0 authentication does not replace application authorization. The API maps the immutable token
`sub` claim to `users.auth0_subject`. Each local user owns exactly one workspace through the unique
`workspaces.owner_user_id` relationship, and all financial queries, mutations, imports, workers,
inference and exports remain scoped to that workspace.

## Required Auth0 configuration

Create an Auth0 Single Page Application and an Auth0 API. Configure the API identifier to exactly
match `AUTH0_AUDIENCE` and keep its signing algorithm as RS256. Configure the SPA with the exact
application origins in Allowed Callback URLs, Allowed Logout URLs and Allowed Web Origins.

Add a post-login Action that emits verified identity details into namespaced access-token claims:

```javascript
exports.onExecutePostLogin = async (event, api) => {
  if (!event.user.email_verified) return;
  api.accessToken.setCustomClaim("https://folio.app/email", event.user.email);
  api.accessToken.setCustomClaim(
    "https://folio.app/name",
    event.user.name || event.user.email,
  );
};
```

The claim names must match `AUTH0_EMAIL_CLAIM` and `AUTH0_NAME_CLAIM`. The API refuses to provision
a workspace without the trusted email claim. Existing local owners are linked once by matching
that claim to their unique email; all later requests use `sub`, so changing an Auth0 email cannot
move a user between workspaces.

## Client and token handling

The frontend loads public tenant configuration from `GET /api/auth/config`, redirects through
Universal Login and obtains tokens with the Auth0 Vue SDK. Tokens use the SDK's in-memory cache and
are attached as `Authorization: Bearer` headers. No token is stored in application local storage or
in an application cookie. `GET /api/auth/me` returns only the local workspace profile and trial
state.

The configured Auth0 origin is the only additional CSP `connect-src`. Caddy terminates application
HTTPS; Auth0 terminates identity flows. Local password, verification email, reset-token, session,
CSRF, throttle and SMTP tables/endpoints no longer exist.

## Operational checklist

- Use separate Auth0 tenants/applications for development and production.
- Enter Auth0 values through deployment secrets; never commit tenant credentials.
- Require verified emails in the Auth0 connection or Action before emitting the email claim.
- Enable Auth0 brute-force and suspicious-IP protections; add MFA appropriate to the deployment.
- Keep callback, logout and web-origin allowlists exact, with no wildcard production origins.
- Test expired, wrong-issuer, wrong-audience and unsigned tokens as well as cross-workspace IDs.
- Encrypt and test restoration of the SQLite database and protect Auth0 tenant administrators.
- Do not run multiple API instances against one SQLite file.

Account deletion or other Auth0 tenant administration requires a separately protected backend use
of the Auth0 Management API. Management API credentials must never be exposed to the SPA.

