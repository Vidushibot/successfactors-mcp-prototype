# SAP SuccessFactors Multi-Agent MCP Prototype

> **Demonstration using synthetic SuccessFactors-style data.** This is a read-only educational prototype, not an SAP SuccessFactors system and not production-ready.

The application answers authorized HR questions through a narrow MCP tool boundary. Mock mode requires no SAP or OpenAI credentials. Demo mode adds optional OpenAI Agents SDK orchestration; real mode is reserved for an explicitly configured non-production SuccessFactors tenant.

## Features

- Eleven typed, read-only MCP tools; no arbitrary HTTP, OData, or write surface.
- Four synthetic identities with server-side roles and population scopes.
- Explicit entity and field allow-lists plus deny-by-default response sanitization.
- Ten fictional employees, twelve positions, foundation objects, effective-dated history, vacancies, and intentional data-quality issues.
- Structured SQLite audit trail without full HR payloads or secrets.
- FastAPI chat/audit API and Streamlit evidence-focused interface.
- Deterministic mock chat works without an API key.

## Windows setup (primary path)

```powershell
cd .\successfactors-mcp-prototype
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

Run all services:

```powershell
.\scripts\run_all_windows.ps1
```

Or use three terminals:

```powershell
.\scripts\run_mcp_windows.ps1
.\scripts\run_backend_windows.ps1
.\scripts\run_ui_windows.ps1
```

`run_ui_windows.ps1` starts FastAPI in the background automatically when the backend is not already running, so it can also be used as the simplest one-command mock UI launcher.

- UI: http://127.0.0.1:8501
- API: http://127.0.0.1:8000
- OpenAPI: http://127.0.0.1:8000/docs
- MCP: http://127.0.0.1:8001/mcp

## Unix and VS Code

Run `bash scripts/setup_unix.sh`, then `bash scripts/run_all_unix.sh`. In VS Code select `.venv` as the Python interpreter and open three terminals if preferred.

## Configuration and modes

Copy `.env.example` to `.env`; placeholders contain no secrets.

- `APP_MODE=mock`: synthetic provider and deterministic chat; no external credentials.
- `APP_MODE=demo`: synthetic provider with live Agents SDK orchestration; requires `OPENAI_API_KEY` and `MCP_INTERNAL_TOKEN`.
- `APP_MODE=real`: configured test tenant only. Missing settings fail startup; there is no mock fallback.

`OPENAI_MODEL` centralizes model selection. Dependency ranges target Python 3.11 and current compatible major versions while avoiding unreviewed major upgrades.

### Live Agents SDK demo

Copy `.env.example` to `.env`, then set these values:

```dotenv
APP_MODE=demo
OPENAI_MODEL=gpt-5.4-mini
OPENAI_API_KEY=your-key-from-a-secret-store
MCP_INTERNAL_TOKEN=a-long-random-local-secret
```

Do not commit `.env`. `run_ui_windows.ps1` now starts the MCP server and FastAPI when needed.
The application passes user, session, and correlation identity to MCP through protected HTTP
headers; those fields are absent from model-callable tool schemas. Specialists receive hard-coded
tool allow-lists. The UI trace records agent/tool lifecycle names only, not prompts, arguments,
results, or private reasoning.

Cost controls are configured with `DEMO_MAX_TURNS`, `DEMO_MAX_OUTPUT_TOKENS`, and
`DEMO_DAILY_TOKEN_BUDGET`. Set `OPENAI_INPUT_COST_PER_1M` and
`OPENAI_OUTPUT_COST_PER_1M` to the current rates for the chosen model to display a local estimate.
OpenAI tracing is off by default and, when enabled, sensitive trace content remains disabled.

The normal suite never calls OpenAI. To run the single opt-in live delegation smoke test after all
three services are running in demo mode:

```powershell
$env:RUN_LIVE_AGENT_TESTS="true"
.\.venv\Scripts\python.exe -m pytest -m live -q
```

This test makes one real API request and therefore incurs model usage.

## Verification

```powershell
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest
```

## Real test-tenant authentication setup

1. Register an OAuth client in SuccessFactors API Center.
2. Create a dedicated API user.
3. Assign minimum required RBP query permissions.
4. Limit the target population.
5. Grant query access only to approved entities and fields.
6. Store OAuth material outside source control.
7. Validate the tenant-specific signed OAuth flow against a non-production tenant.
8. Verify both allowed and denied employee scenarios.

Basic Authentication is not supported. The included real token-provider interface intentionally fails until the tenant-specific SAP-documented flow is implemented and validated.

## Docker

After copying `.env.example` to `.env`, run `docker compose up --build`. Docker is optional and the compose file is development-only, not production hardened.

## Troubleshooting and limitations

- If the UI reports the backend unavailable, start FastAPI first.
- If port binding fails, stop the process using 8000, 8001, or 8501.
- The prototype user selector is not production authentication.
- SQLite is not intended for horizontally scaled production audit storage.
- Real OAuth, tenant metadata quirks, and RBP behavior require tenant validation.
- Mock routing deliberately supports the supplied demonstration question patterns; it is not a general natural-language engine.
- Future writes require a separate approved architecture and are not present, even as placeholders.

For the detailed flow and trust boundaries see `ARCHITECTURE.md`; for controls and risks see `SECURITY.md`.
The exact synthetic records and scenario guide are described in `TEST_DATA.md` and exported under `test_data/`.
