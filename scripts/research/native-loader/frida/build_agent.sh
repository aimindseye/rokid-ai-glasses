#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
export npm_config_ignore_scripts=false
npm install --no-audit --no-fund
if ! find node_modules/frida -type f -name frida_binding.node -print -quit | grep -q .; then
  echo "ERROR: frida_binding.node was not installed" >&2
  exit 1
fi
./node_modules/.bin/frida-compile agent.ts -o dist/agent.js -T none
node --check dist/agent.js
shasum -a 256 dist/agent.js
