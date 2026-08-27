# Repository guidance

- Python package: `src/sf_mcp_poc`; tests: `tests`.
- Setup: `py -3.11 -m venv .venv`; activate it; `pip install -e ".[dev]"`.
- Verify: `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`.
- This application is strictly read-only. Never add create, update, upsert, delete, hire, transfer, or termination tools.
- Never expose arbitrary HTTP, raw URLs, entity names, or OData clauses to models.
- Authorization is server-side and must precede provider access. Always sanitize provider output and audit tool calls.
- Never commit secrets, private keys, `.env`, databases, or real employee data.
- Definition of done: mock flow runs without credentials; authorization, sanitization, audit, lint, typing, and tests pass.
