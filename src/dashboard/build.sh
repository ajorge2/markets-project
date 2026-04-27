#!/usr/bin/env bash
# Vercel build step: substitute __API_BASE__ with the real backend URL,
# producing dist/index.html as the deployed artifact.
set -euo pipefail

if [ -z "${API_BASE:-}" ]; then
  echo "ERROR: API_BASE env var is required (e.g. https://markets-api.northflank.app)" >&2
  exit 1
fi

cd "$(dirname "$0")"
mkdir -p dist
sed "s|__API_BASE__|${API_BASE}|g" index.html > dist/index.html
echo "Built dist/index.html with API_BASE=${API_BASE}"
