#!/usr/bin/env bash
set -euo pipefail

npm --prefix frontend run check
npm --prefix frontend run build
python -m compileall backend
python -m unittest backend.test_smoke_endpoints
