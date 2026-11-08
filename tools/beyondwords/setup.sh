#!/usr/bin/env bash
# Build the Beyondwords helper runtime (hash-pinned deps) and run its doctor.
# Usage: bash tools/beyondwords/setup.sh   (from the repo root)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RT="$ROOT/.beyondwords-runtime"
HERE="$ROOT/tools/beyondwords"
if [ ! -x "$RT/bin/python" ]; then
  python3 -m venv "$RT"
  "$RT/bin/python" -m pip install -q --require-hashes -r "$HERE/optional.lock"
  "$RT/bin/python" -m pip install -q --require-hashes -r "$HERE/mcp.lock"
  "$RT/bin/python" -m pip check
fi
"$RT/bin/python" "$ROOT/.claude/skills/beyondwords/scripts/beyondwords.py" doctor >/dev/null && echo "Beyondwords runtime ready: $RT/bin/python"
