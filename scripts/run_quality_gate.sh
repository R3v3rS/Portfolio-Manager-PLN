#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" - <<'PY'
import sys

if not ((3, 11) <= sys.version_info[:2] < (3, 13)):
    raise SystemExit(
        "Backend wymaga Pythona 3.11 lub 3.12 (pandas 2.2.0 nie wspiera "
        f"tego interpretera: {sys.version.split()[0]}). Ustaw np. "
        "PYTHON_BIN=python3.12."
    )
PY

npm --prefix frontend run check
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
"$PYTHON_BIN" -m compileall backend
"$PYTHON_BIN" -m pytest -q
