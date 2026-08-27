#!/usr/bin/env bash
set -euo pipefail
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
test -f .env || cp .env.example .env
.venv/bin/python -m pytest
