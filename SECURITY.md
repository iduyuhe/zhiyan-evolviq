# Security Policy

## Supported Versions

| Version | Status |
|---------|--------|
| v20 (latest) | ✅ Security fixes supported |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub Issues.**

Report privately via one of the following:

- Email a maintainer directly (replace with the real security contact before publishing)
- Or use GitHub's private vulnerability reporting if enabled

Include in your report:

- `[SECURITY]` in the subject
- Description of the vulnerability and impact scope
- Step-by-step reproduction
- Suggested fix (if any)

Maintainers will acknowledge within **72 hours**, and coordinate public disclosure (typically within **90 days** after a fix is shipped).

## Security Design Highlights

- **Authorization guardrails**: Each Agent has an independent `AuthBoundary`; high-risk actions require human approval.
- **Multi-tenant isolation**: Data is row-level isolated by `tenant_id`; invalid keys return `401`.
- **Graceful degradation**: Failed external dependencies fall back locally — internal errors are never leaked to callers.
- **Secret handling**: `LLM_API_KEY` and similar credentials live only in environment variables, never in the database or repo.
- **Audit trail**: Every action is logged with `session_id` / `actor` / `tenant_id` for compliance回溯.
