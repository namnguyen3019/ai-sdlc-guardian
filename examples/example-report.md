<!-- ai-sdlc-guardian-report -->
## 🛡️ AI-SDLC Guardian

**Overall Risk: 62/100 — 🟠 HIGH**

| Dimension | Score | Weight |
|---|---:|---:|
| Security | 100/100 | 33% |
| Testing | 25/100 | 28% |
| Change Impact | 80/100 | 22% |
| Complexity | 25/100 | 17% |
| Ai Risk | 0/100 | 0% |

### Key findings (8)

**1. [CRITICAL] SQL_INJECTION_RISK** — `src/payment/payment_service.py:81`

SQL appears to be built from string interpolation or concatenation, which allows user-controlled input to reach the query text.

*Recommendation:* Use parameterized queries / prepared statements instead of interpolating values into SQL.

*Evidence:* `query = f"SELECT * FROM payments WHERE user_id = {user_id}"`

*Confidence: 85% · Source: deterministic*

**2. [CRITICAL] HARDCODED_SECRET** — `src/payment/payment_service.py:85`

A credential-like value appears to be hardcoded in source.

*Recommendation:* Move secrets to a secrets manager or environment variable and rotate any value that was committed.

*Evidence:* `api_key = "sk_live_51HxTestSecretKey12345"`

*Confidence: 70% · Source: deterministic*

**3. [HIGH] TLS_VERIFICATION_DISABLED** — `src/payment/payment_service.py:87`

TLS certificate verification is disabled.

*Recommendation:* Keep certificate verification enabled; pin or provision the correct CA bundle instead of disabling verification.

*Evidence:* `headers={"X-Key": api_key}, verify=False)`

*Confidence: 90% · Source: deterministic*

**4. [HIGH] AUTH_CHANGE_WITHOUT_TESTS** — `src/auth/login.py`

Authentication behavior was modified but no tests were added or updated.

*Recommendation:* Add authentication/authorization integration tests covering the modified paths.

*Confidence: 90% · Source: deterministic*

**5. [HIGH] CRITICAL_MODULE_MODIFIED** — `src/payment/payment_service.py`

A critical module (auth, payment, or data layer) was modified.

*Recommendation:* Route this PR to an owner of the affected module and verify rollback is possible.

*Confidence: 80% · Source: deterministic*

**6. [HIGH] CRITICAL_MODULE_MODIFIED** — `src/auth/login.py`

A critical module (auth, payment, or data layer) was modified.

*Recommendation:* Route this PR to an owner of the affected module and verify rollback is possible.

*Confidence: 80% · Source: deterministic*

**7. [HIGH] EXCEPTION_HANDLING_REMOVED** — `src/payment/payment_service.py:87`

Exception handling was removed without an added replacement in this file.

*Recommendation:* Confirm errors are still handled or intentionally propagated; document the new failure behavior.

*Confidence: 75% · Source: deterministic*

**8. [HIGH] PAYMENT_CODE_MODIFIED** — `src/payment/payment_service.py`

Payment-related code was modified.

*Recommendation:* Require a second reviewer for payment flows and verify idempotency and audit logging.

*Confidence: 70% · Source: deterministic*


<details>
<summary>All other findings (6)</summary>

**1. [MEDIUM] DEPENDENCY_MANIFEST_CHANGED** — `requirements.txt`

A dependency manifest was changed; new or upgraded third-party code will run with this service's privileges.

*Recommendation:* Review changelogs/advisories for each changed dependency and prefer pinned versions.

*Confidence: 85% · Source: deterministic*

**2. [MEDIUM] AUTH_CODE_MODIFIED** — `src/auth/login.py`

Authentication/authorization-related code was modified.

*Recommendation:* Request a security-focused review and verify authentication and authorization test coverage.

*Confidence: 70% · Source: deterministic*

**3. [MEDIUM] UNPINNED_DEPENDENCY_VERSION** — `requirements.txt:3`

A dependency version is unpinned or unbounded, so future installs may pull untested versions.

*Recommendation:* Pin an exact version or a bounded range and rely on a lockfile.

*Evidence:* `left-pad-py>=1.0`

*Confidence: 60% · Source: deterministic*

**4. [MEDIUM] NEW_DEPENDENCY_ADDED** — `requirements.txt:3`

Dependency entry 'left-pad-py' appears to be newly added.

*Recommendation:* Vet the package (maintenance, popularity, known CVEs) before adopting it.

*Evidence:* `left-pad-py>=1.0`

*Confidence: 55% · Source: deterministic*

**5. [MEDIUM] NEW_DEPENDENCY_ADDED** — `requirements.txt:4`

Dependency entry 'totally-new-lib' appears to be newly added.

*Recommendation:* Vet the package (maintenance, popularity, known CVEs) before adopting it.

*Evidence:* `totally-new-lib==0.0.1`

*Confidence: 55% · Source: deterministic*

**6. [LOW] DEEP_NESTING** — `src/payment/payment_service.py:87`

Added code is nested five or more levels deep.

*Recommendation:* Extract helper functions or use early returns to flatten control flow.

*Confidence: 60% · Source: deterministic*

</details>

### Why this score

- **Security** (100/100 × 33% = 33.3 points): 2 CRITICAL, 2 HIGH, 1 MEDIUM finding(s); most severe: SQL_INJECTION_RISK in src/payment/payment_service.py:81.
- **Testing** (25/100 × 28% = 6.9 points): 1 HIGH finding(s); most severe: AUTH_CHANGE_WITHOUT_TESTS in src/auth/login.py.
- **Change Impact** (80/100 × 22% = 17.8 points): 2 HIGH, 4 MEDIUM finding(s); most severe: CRITICAL_MODULE_MODIFIED in src/payment/payment_service.py.
- **Complexity** (25/100 × 17% = 4.2 points): 1 HIGH, 1 LOW finding(s); most severe: EXCEPTION_HANDLING_REMOVED in src/payment/payment_service.py:87.
- **Ai Risk** (0/100 × 0% = 0.0 points): AI analysis was not run; its weight was redistributed.

### Merge recommendation: **REVIEW REQUIRED**

---
*Analysis `48d77b89-911d-49f1-ad50-371a324635af` · engine v0.1.0 · 3 files, +10/-8 · 1 ms*
