# Optional Platform Authentication Design

## Goal

Allow the invited deployment at `agentpartner.top` to operate without asking
visitors for a shared platform access token, while keeping authentication
enabled by default for every other deployment.

## Configuration

Add `APP_AUTH_REQUIRED`, parsed as a boolean and defaulting to `true`.

- `APP_AUTH_REQUIRED=true`: preserve current behavior. Production requires a
  non-empty `APP_ACCESS_TOKEN`, and business API routes require that token.
- `APP_AUTH_REQUIRED=false`: production may start without a platform token,
  and business API routes are accessible without authorization headers.

Invalid boolean values fail during settings loading rather than silently
disabling authentication.

## Application Behavior

The production startup gate and `ApiTokenMiddleware` use the same
`auth_required` setting. Health routes remain public in both modes.

No frontend code needs a special anonymous mode. The existing token prompt is
only triggered by an API `401`; when authentication is disabled, normal API
requests succeed and the prompt does not appear. Existing stored tokens are
harmless because the backend ignores platform authentication in anonymous
mode.

## Deployment

Document the switch in `.env.example` and README. Deploy the updated release,
set `APP_AUTH_REQUIRED=false` in
`/etc/agent-partner/agent-partner.env`, and restart the API and workers.

Keep HTTPS, trusted-host checks, request-size limits, import limits, per-IP job
quota, queue capacity, worker concurrency, model egress restrictions, and
artifact cleanup unchanged.

## Recovery

To restore the shared-token gate, set:

```text
APP_AUTH_REQUIRED=true
APP_ACCESS_TOKEN=<shared-token>
```

Then restart the API. No code rollback is required.

## Acceptance Criteria

- Default settings still require authentication.
- Production still refuses to start without a token when authentication is
  required.
- Production starts without a token when authentication is disabled.
- Anonymous business API requests succeed only when the switch is disabled.
- The frontend does not display the token prompt on the deployed site.
- Existing production security and deployment tests pass.

