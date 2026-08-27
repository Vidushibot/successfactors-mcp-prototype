#!/usr/bin/env bash
set -euo pipefail
.venv/bin/python -m sf_mcp_poc.mcp_server &
.venv/bin/python -m sf_mcp_poc.main &
.venv/bin/python -m streamlit run src/sf_mcp_poc/streamlit_app.py --server.address 127.0.0.1 --server.port 8501 &
wait
