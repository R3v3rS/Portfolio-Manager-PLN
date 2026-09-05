#!/usr/bin/env bash
set -euo pipefail

npm --prefix frontend run check
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
python -m compileall backend
python -m pytest -q
