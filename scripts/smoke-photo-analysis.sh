#!/usr/bin/env bash
# Smoke-test photo analysis against a running coordinator + Dell worker.
# Usage:
#   export COORDINATOR_URL=https://your-coordinator-route
#   export WEB_API_KEY=your-web-key
#   ./scripts/smoke-photo-analysis.sh path/to/test.jpg

set -euo pipefail

COORDINATOR_URL="${COORDINATOR_URL:-http://localhost:8080}"
WEB_API_KEY="${WEB_API_KEY:-dev-web-key}"
IMAGE_PATH="${1:?Usage: $0 path/to/image.jpg}"

echo "Creating photo analysis job at ${COORDINATOR_URL}..."
CREATE_RESPONSE=$(curl -sS -X POST "${COORDINATOR_URL}/v1/analyze-photo" \
  -H "Authorization: Bearer ${WEB_API_KEY}" \
  -F "file=@${IMAGE_PATH}" \
  -F "location_of_fire=Smoke test location")

JOB_ID=$(echo "${CREATE_RESPONSE}" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "Job ID: ${JOB_ID}"

echo "Polling until completed (max 120s)..."
for _ in $(seq 1 120); do
  JOB=$(curl -sS "${COORDINATOR_URL}/v1/jobs/${JOB_ID}" \
    -H "Authorization: Bearer ${WEB_API_KEY}")
  STATUS=$(echo "${JOB}" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
  echo "  status=${STATUS}"
  if [[ "${STATUS}" == "completed" ]]; then
    echo "${JOB}" | python3 -m json.tool
    echo "Smoke test passed."
    exit 0
  fi
  if [[ "${STATUS}" == "failed" ]]; then
    echo "${JOB}" | python3 -m json.tool
    echo "Smoke test failed: job error." >&2
    exit 1
  fi
  sleep 1
done

echo "Smoke test timed out waiting for worker." >&2
exit 1
