#!/usr/bin/env bash
#
# Check for hardcoded http://localhost URLs in frontend source files.
# These break Cloud Run deployments where the backend is not at localhost.
#
# Legitimate exceptions (excluded):
#   - vite.config.ts (dev proxy config)
#   - overlay userscripts (*.user.js)
#   - OverlayGuidePage (documents userscript setup)
#
# Usage: ./scripts/check-localhost-urls.sh
# Exit codes: 0 = clean, 1 = violations found

set -euo pipefail

# Resolve project root relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_SRC="$PROJECT_ROOT/frontend/src"

if [ ! -d "$FRONTEND_SRC" ]; then
  echo "ERROR: frontend/src/ directory not found at $FRONTEND_SRC"
  exit 1
fi

# Search for hardcoded localhost URLs, excluding known exceptions
violations=$(grep -rn 'http://localhost' "$FRONTEND_SRC" \
  --include='*.ts' \
  --include='*.tsx' \
  --include='*.js' \
  --include='*.jsx' \
  | grep -v 'vite\.config\.' \
  | grep -v '\.user\.' \
  | grep -v 'OverlayGuidePage' \
  | grep -v 'overlay' \
  | grep -v 'userscript' \
  || true)

if [ -n "$violations" ]; then
  echo "ERROR: Found hardcoded http://localhost URLs in frontend source files."
  echo "These will break Cloud Run deployments. Use relative URLs (e.g. /api/...) instead."
  echo ""
  echo "Violations:"
  echo "$violations" | while IFS= read -r line; do
    echo "  $line"
  done
  echo ""
  echo "If a file is a legitimate exception, add it to scripts/check-localhost-urls.sh"
  exit 1
fi

echo "OK: No hardcoded localhost URLs found in frontend source."
exit 0
