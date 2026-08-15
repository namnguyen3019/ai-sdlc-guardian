# ADR-003: Week 3 — GitHub automation

Date: 2026-08-12 · Status: accepted

## Decisions

1. **Lambda Function URL, not API Gateway.** One webhook endpoint needs no
   routing, throttling tiers, or per-request pricing. `authType: NONE` is
   deliberate: the HMAC-SHA256 signature (shared webhook secret, verified in
   constant time before any payload parsing) *is* the authentication, which
   is exactly how GitHub webhooks are designed to be consumed. An unsigned
   request does nothing but a 401 and a metric.
2. **Webhook Lambda does the minimum.** Verify → filter (opened/reopened/
   synchronize) → de-duplicate → start Step Functions → 202. All slow work
   (GitHub API, Bedrock) lives in the workflow, keeping the receiver well
   under GitHub's 10-second delivery timeout.
3. **Idempotency via conditional put.** Delivery ids are written to the
   analyses table (`DELIVERY#<id>`, TTL 7 days) with
   `attribute_not_exists(pk)`; a redelivery loses the race and is
   acknowledged with 200 without a second analysis.
4. **Diff travels via S3, not workflow payload.** The fetch task uploads the
   diff to `artifacts/` (90-day expiry) and passes only its key — real PR
   diffs can exceed the 256 KB Step Functions payload limit.
5. **Comment upsert by marker.** The renderer's hidden HTML marker
   identifies the Guardian comment; the publisher updates it in place. One
   comment per PR, ever, regardless of push count.
6. **stdlib HTTP client with injectable transport.** GitHub's API needs four
   endpoints; urllib keeps the runtime dependency surface at pydantic-only
   and the transport injection keeps every test offline. PyGithub was also
   ruled out in ADR-001 for the module-name collision.
7. **Secrets Manager as specified** (one secret: `token` +
   generated `webhook_secret`), cached per container. SSM Parameter Store
   would be marginally cheaper; the spec names Secrets Manager and rotation
   support is worth more here than $0.40/month.

## Consequences

- The Week 3 milestone is met: PR opened → analyzed → report comment, with
  no duplicate comments and no double analyses on redeliveries.
- The webhook endpoint is public but inert without the secret; rotating the
  webhook secret is a Secrets Manager update plus a GitHub settings update.
- First-page-only comment listing (100 comments) is a known limitation; the
  Guardian comment is posted early in a PR's life, so in practice it is
  found. Revisit if a busy PR ever accumulates 100+ comments before Guardian
  posts.
