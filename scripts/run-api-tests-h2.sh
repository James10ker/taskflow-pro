#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repeat_count="${1:-${TASKFLOW_API_TEST_REPEAT:-1}}"

if [[ ! "${repeat_count}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: $0 [positive-repeat-count]" >&2
  exit 2
fi

export TASKFLOW_API_TEST_DATABASE_KIND="h2"
export TASKFLOW_TEST_DATABASE_URL='jdbc:h2:mem:taskflow_api_test;MODE=MySQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1'
export TASKFLOW_TEST_DATABASE_USER="sa"
export TASKFLOW_TEST_DATABASE_PASSWORD=""
export TASKFLOW_API_TEST_ARTIFACT_DIR="${TASKFLOW_API_TEST_ARTIFACT_DIR:-${project_root}/.artifacts/api-tests-h2}"

exec "${project_root}/scripts/run-api-tests.sh" "${repeat_count}"
