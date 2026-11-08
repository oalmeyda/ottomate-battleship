#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CORE_DIR="$(cd "${REPO_ROOT}/../ottomate-core" && pwd)"

exec "${CORE_DIR}/scripts/vendor.sh" "${REPO_ROOT}"
