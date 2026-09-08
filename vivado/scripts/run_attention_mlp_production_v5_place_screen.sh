#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HAP_PLACE_MODE=screen
exec "$SCRIPT_DIR/run_attention_mlp_production_v5_place.sh" "$@"
