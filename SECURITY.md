# Security

## Threat model and classification

Employee, employment, job, position, and organizational assignments are confidential HR data. Compensation, banking, government identifiers, health/disability, contacts, dependents, home contact details, birth date, gender, and marital status are prohibited.

Threats include horizontal privilege escalation, prompt injection, raw-query injection, excess-field responses, secret leakage, employee-existence disclosure, compromised upstream text, excessive enumeration, unsafe logs, and accidental write enablement.

## Controls

- Demonstration identity is resolved server-side; prompts never define roles or scopes.
- Tool and employee-population authorization occurs before provider access.
- Entity/field registries, typed inputs, strict limits, deterministic query construction, and output sanitization are deny-by-default.
- Unauthorized and unavailable records receive an opaque response.
- No Basic Auth, write tools, arbitrary HTTP tool, raw URL, or raw OData clauses exist.
- Secrets are loaded from environment/configuration and redacted from logs.
- Audit records contain no full employee payloads, hidden prompts, tokens, or chain-of-thought.
- All services bind to localhost by default.

## Prompt injection

User text and retrieved text are untrusted. Agents are instructed to reject identity changes, restricted fields, secrets, raw queries, and hidden prompts. Deterministic authorization remains authoritative even if an agent fails to follow instructions. Tool data is never appended to instructions.

## Authentication and secrets

The synthetic selector is unsuitable for production. Real deployment requires SSO, signed sessions, CSRF protection, enterprise authorization mapping, managed secret storage, TLS, and a documented tenant-specific OAuth flow. Private keys and `.env` are ignored by Git.

## Retention

Do not persist full employee responses by default. Keep audit metadata only for the minimum period required by an approved policy, restrict audit access, and support deletion/legal-hold requirements.

## Known prototype risks and backlog

- Synthetic header-based identity is spoofable outside a local demonstration.
- SQLite lacks enterprise concurrency, immutability, and centralized monitoring.
- The real OAuth provider deliberately remains unconfigured until validated with SAP documentation and a test tenant.
- Add gateway authentication, rate limiting, SIEM integration, keyed identifier hashing, encrypted storage, egress allow-listing, dependency scanning, penetration testing, DPIA/privacy review, and formal RBP reconciliation before production.
