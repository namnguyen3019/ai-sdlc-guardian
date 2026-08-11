# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately via GitHub Security Advisories
("Report a vulnerability" on the repository's Security tab). Do not open a
public issue. We aim to acknowledge reports within 72 hours.

## Security model

Guardian's own design assumptions (enforced in code and reviews):

- **Untrusted input.** Diff content is attacker-controlled. It is parsed
  with bounded regexes, never executed, and never interpreted as
  instructions. Prompts sent to Bedrock (Week 2) wrap diff content as data
  and instruct the model to ignore instructions embedded in code or comments;
  model output is validated against a strict schema.
- **Secrets.** No credentials in the repository. AWS access uses IAM roles;
  the GitHub webhook secret and token live in AWS Secrets Manager (Week 3).
- **Webhooks.** GitHub webhook deliveries are verified with HMAC signatures
  before any processing (Week 3).
- **Data minimization.** DynamoDB stores analysis metadata; S3 stores
  sanitized reports with a 90-day artifact expiry; raw repository source is
  not persisted, and logs must never contain source code or secrets.
- **Least privilege.** Each Lambda gets a scoped role (table/bucket/model
  ARNs only). Bedrock access is restricted to the configured model id.

## Supported versions

Pre-1.0: only the latest release receives fixes.
