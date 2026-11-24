#!/usr/bin/env bash
# usage: apply-overlay.sh <upstream-dir>
set -euo pipefail
UP="$1"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

# 1) our own files over upstream (everything under overlay/ except its README)
if [ -d "$HERE/overlay/app" ]; then
  cp -r "$HERE/overlay/app/." "$UP/app/"
fi

# 2) branding: display name only (package name stays com.winlator, see docs/PLAN.md)
for f in "$UP"/app/src/main/res/values*/strings.xml; do
  sed -i 's|<string name="app_name">Winlator</string>|<string name="app_name">PORTX EMULATOR</string>|' "$f"
done
grep -rn 'app_name' "$UP/app/src/main/res/values/strings.xml"
