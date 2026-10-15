#!/usr/bin/env bash
#
# Builds the t-mon image and verifies that the dashboard container comes up
# healthy.
#
# Usage:
#   ci-services.sh [t-mon-dir]
#
set -euo pipefail

MON_DIR="${1:-.}"

MON_IMAGE="t-mon:ci"
MON_CONTAINER="ci-t-mon"

# The dashboard reads client_secrets.json at import time; the real file is
# gitignored and therefore absent from a clean checkout, so fall back to the
# example the tests also use.
if [[ ! -f "${MON_DIR}/client_secrets.json" ]]; then
  cp "${MON_DIR}/client_secrets_example.json" "${MON_DIR}/client_secrets.json"
fi

cache_args=()
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
  cache_args=(
    --cache-from "type=gha,scope=t-mon"
    --cache-to "type=gha,mode=max,scope=t-mon"
  )
fi

echo "::group::Building t-mon from ${MON_DIR}"
docker buildx build \
  --load \
  --tag "${MON_IMAGE}" \
  "${cache_args[@]}" \
  "${MON_DIR}"
echo "::endgroup::"

container_running() {
  docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null | grep -qx true
}

cleanup() {
  docker rm -f "${MON_CONTAINER}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker rm -f "${MON_CONTAINER}" >/dev/null 2>&1 || true
docker run -d --name "${MON_CONTAINER}" "${MON_IMAGE}" >/dev/null

url="http://localhost:8050/"
probe="import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('${url}', timeout=5).status == 200 else 1)"
for _ in $(seq 1 40); do
  if docker exec "${MON_CONTAINER}" python -c "${probe}" >/dev/null 2>&1; then
    echo "OK: t-mon is healthy (HTTP 200 at ${url})"
    exit 0
  fi
  if ! container_running "${MON_CONTAINER}"; then
    break
  fi
  sleep 3
done
echo "::error::t-mon health check failed (no HTTP 200 at ${url})"
docker logs "${MON_CONTAINER}" 2>&1 | tail -n 50 || true
exit 1
