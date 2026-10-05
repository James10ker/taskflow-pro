#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repeat_count="${1:-${TASKFLOW_API_TEST_REPEAT:-1}}"
database_kind="${TASKFLOW_API_TEST_DATABASE_KIND:-}"
python_command="${PYTHON_BIN:-python3}"
maven_command="${MAVEN_BIN:-mvn}"
venv_dir="${TASKFLOW_API_TEST_VENV:-${project_root}/.venv-api-tests}"
artifact_dir="${TASKFLOW_API_TEST_ARTIFACT_DIR:-${project_root}/.artifacts/api-tests-${database_kind:-unknown}}"
api_port="${TASKFLOW_API_TEST_PORT:-18080}"
backend_pid=""
backend_log=""
maven_compiler_args=()

usage() {
  cat >&2 <<'EOF'
Usage: run-api-tests.sh [positive-repeat-count]

Required environment:
  TASKFLOW_API_TEST_DATABASE_KIND  h2 or mysql
  TASKFLOW_TEST_DATABASE_URL
  TASKFLOW_TEST_DATABASE_USER
  TASKFLOW_TEST_DATABASE_PASSWORD  may be empty for H2, but must be set

The caller owns database lifecycle. This runner owns only its virtual
environment, backend process, readiness check, Pytest runs, and artifacts.
EOF
}

if [[ ! "${repeat_count}" =~ ^[1-9][0-9]*$ ]]; then
  usage
  exit 2
fi
if [[ "${database_kind}" != "h2" && "${database_kind}" != "mysql" ]]; then
  echo "TASKFLOW_API_TEST_DATABASE_KIND must be either 'h2' or 'mysql'." >&2
  exit 2
fi
for required_variable in \
  TASKFLOW_TEST_DATABASE_URL \
  TASKFLOW_TEST_DATABASE_USER \
  TASKFLOW_TEST_DATABASE_PASSWORD; do
  if [[ ! -v "${required_variable}" ]]; then
    echo "${required_variable} must be set (the H2 password may be empty)." >&2
    exit 2
  fi
done
if [[ ! "${api_port}" =~ ^[0-9]+$ ]] || (( api_port < 1 || api_port > 65535 )); then
  echo "TASKFLOW_API_TEST_PORT must be an integer from 1 through 65535." >&2
  exit 2
fi

for required_command in "${python_command}" "${maven_command}" java realpath setsid timeout; do
  if ! command -v "${required_command}" >/dev/null 2>&1; then
    echo "Required command is unavailable: ${required_command}" >&2
    exit 2
  fi
done

java_home_from_shell="$(
  java -XshowSettings:properties -version 2>&1 \
    | sed -n 's/^[[:space:]]*java\.home = //p' \
    | head -n 1 \
    | tr -d '\r'
)"
maven_version_output="$("${maven_command}" --version 2>&1)"
maven_java_home="$(
  sed -n 's/^Java version: .* runtime: //p' <<<"${maven_version_output}" \
    | head -n 1 \
    | tr -d '\r'
)"
maven_java_version="$(
  sed -n 's/^Java version: \([^,]*\),.*/\1/p' <<<"${maven_version_output}" \
    | head -n 1 \
    | tr -d '\r'
)"
if [[ -z "${java_home_from_shell}" || -z "${maven_java_home}" || -z "${maven_java_version}" ]]; then
  echo "Could not determine the shell and Maven Java runtimes." >&2
  exit 2
fi
if [[ "$(realpath -m "${java_home_from_shell}")" != "$(realpath -m "${maven_java_home}")" ]]; then
  echo "Maven and the current shell use different Java runtimes." >&2
  echo "shell java.home: ${java_home_from_shell}" >&2
  echo "Maven runtime: ${maven_java_home}" >&2
  exit 2
fi
if [[ ! "${maven_java_version}" =~ ^21([.]|$) ]]; then
  echo "Maven must run on Java 21; detected ${maven_java_version}." >&2
  exit 2
fi

# A standard JDK 21 follows the pom without command-line compiler overrides.
# The old javac-less runtime workaround remains available only by explicit opt-in.
if command -v javac >/dev/null 2>&1 \
    && [[ "$(javac -version 2>&1)" =~ ^javac[[:space:]]21([.]|$) ]] \
    && [[ "$(
      javac -J-XshowSettings:properties -version 2>&1 \
        | sed -n 's/^[[:space:]]*java\.home = //p' \
        | head -n 1 \
        | tr -d '\r'
    )" != "" ]] \
    && javac --release 21 -version >/dev/null 2>&1; then
  javac_java_home="$(
    javac -J-XshowSettings:properties -version 2>&1 \
      | sed -n 's/^[[:space:]]*java\.home = //p' \
      | head -n 1 \
      | tr -d '\r'
  )"
  if [[ "$(realpath -m "${javac_java_home}")" != "$(realpath -m "${java_home_from_shell}")" ]]; then
    echo "java and javac use different Java homes." >&2
    exit 2
  fi
elif [[ "${TASKFLOW_ALLOW_JRE_COMPILER_FALLBACK:-false}" == "true" ]]; then
  echo "WARNING: using the explicitly enabled javac-less runtime compatibility flags." >&2
  maven_compiler_args=(
    -Dmaven.compiler.release=
    -Dmaven.compiler.source=21
    -Dmaven.compiler.target=21
  )
else
  echo "A complete JDK 21 with 'javac --release 21' support is required." >&2
  echo "Set TASKFLOW_ALLOW_JRE_COMPILER_FALLBACK=true only for the documented legacy local runtime." >&2
  exit 2
fi

cleanup_backend() {
  if [[ -z "${backend_pid}" ]]; then
    return
  fi

  if kill -0 -- "-${backend_pid}" 2>/dev/null; then
    kill -TERM -- "-${backend_pid}" 2>/dev/null || true
    for _ in {1..50}; do
      if ! kill -0 -- "-${backend_pid}" 2>/dev/null; then
        break
      fi
      sleep 0.2
    done
  fi
  if kill -0 -- "-${backend_pid}" 2>/dev/null; then
    kill -KILL -- "-${backend_pid}" 2>/dev/null || true
  fi
  wait "${backend_pid}" 2>/dev/null || true
  if kill -0 -- "-${backend_pid}" 2>/dev/null; then
    echo "The owned backend process group could not be stopped: ${backend_pid}" >&2
    return 1
  fi
}

on_exit() {
  local exit_status=$?
  local cleanup_status=0
  trap - EXIT
  cleanup_backend || cleanup_status=$?
  if (( exit_status == 0 && cleanup_status != 0 )); then
    exit_status="${cleanup_status}"
  fi
  if (( exit_status != 0 )) && [[ -n "${backend_log}" ]]; then
    echo "API test flow failed; backend diagnostics: ${backend_log}" >&2
  fi
  exit "${exit_status}"
}

trap on_exit EXIT
trap 'exit 130' INT TERM

if [[ ! -x "${venv_dir}/bin/python" ]]; then
  "${python_command}" -m venv "${venv_dir}"
fi
if ! "${venv_dir}/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "The API-test virtual environment has no pip. Install venv/ensurepip and recreate: ${venv_dir}" >&2
  exit 2
fi
"${venv_dir}/bin/python" -m pip install \
  --disable-pip-version-check \
  --quiet \
  --requirement "${project_root}/tests/api/requirements.txt"

if [[ -z "${APP_API_TEST_PASSWORD:-}" ]]; then
  APP_API_TEST_PASSWORD="$("${venv_dir}/bin/python" -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi
if [[ -n "${TASKFLOW_API_TEST_PASSWORD:-}" && "${TASKFLOW_API_TEST_PASSWORD}" != "${APP_API_TEST_PASSWORD}" ]]; then
  echo "APP_API_TEST_PASSWORD and TASKFLOW_API_TEST_PASSWORD must match." >&2
  exit 2
fi
TASKFLOW_API_TEST_PASSWORD="${APP_API_TEST_PASSWORD}"

if [[ -z "${APP_JWT_SECRET:-}" ]]; then
  APP_JWT_SECRET="$("${venv_dir}/bin/python" -c 'import base64, secrets; print(base64.b64encode(secrets.token_bytes(48)).decode())')"
fi

if ! "${venv_dir}/bin/python" - "${api_port}" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", port))
    except OSError:
        raise SystemExit(1)
PY
then
  echo "127.0.0.1:${api_port} is already in use; refusing to stop or reuse that service." >&2
  exit 2
fi

export APP_API_TEST_PASSWORD TASKFLOW_API_TEST_PASSWORD APP_JWT_SECRET
export SPRING_PROFILES_ACTIVE="api-test"
export SPRING_DATASOURCE_URL="${TASKFLOW_TEST_DATABASE_URL}"
export SPRING_DATASOURCE_USERNAME="${TASKFLOW_TEST_DATABASE_USER}"
export SPRING_DATASOURCE_PASSWORD="${TASKFLOW_TEST_DATABASE_PASSWORD}"
export SERVER_PORT="${api_port}"
expected_api_base_url="http://127.0.0.1:${api_port}/api"
if [[ -n "${TASKFLOW_API_BASE_URL:-}" && "${TASKFLOW_API_BASE_URL}" != "${expected_api_base_url}" ]]; then
  echo "TASKFLOW_API_BASE_URL must target the backend started by this runner: ${expected_api_base_url}" >&2
  exit 2
fi
export TASKFLOW_API_BASE_URL="${expected_api_base_url}"

case "${database_kind}" in
  h2)
    export SPRING_DATASOURCE_DRIVER_CLASS_NAME="org.h2.Driver"
    datasource_log_pattern='jdbc:h2:mem:taskflow_api_test'
    ;;
  mysql)
    export SPRING_DATASOURCE_DRIVER_CLASS_NAME="com.mysql.cj.jdbc.Driver"
    datasource_log_pattern='jdbc:mysql:.*taskflow_api_test'
    ;;
esac

mkdir -p "${artifact_dir}"
backend_log="${artifact_dir}/backend-${database_kind}.log"
: >"${backend_log}"

echo "Compiling the backend test runtime..."
timeout --signal=TERM --kill-after=10s "${TASKFLOW_MAVEN_COMPILE_TIMEOUT_SECONDS:-300}" \
  "${maven_command}" -B -q -f "${project_root}/backend/pom.xml" \
  "${maven_compiler_args[@]}" -DskipTests test-compile

echo "Starting the ${database_kind} API-test backend on 127.0.0.1:${api_port}..."
setsid "${maven_command}" -B -q -f "${project_root}/backend/pom.xml" \
  "${maven_compiler_args[@]}" spring-boot:test-run >"${backend_log}" 2>&1 &
backend_pid=$!

"${venv_dir}/bin/python" "${project_root}/scripts/wait-for-taskflow-api.py" \
  --pid "${backend_pid}" \
  --timeout-seconds "${TASKFLOW_API_WAIT_SECONDS:-120}"

if ! grep -Eq "${datasource_log_pattern}" "${backend_log}"; then
  echo "Backend log does not prove the expected ${database_kind} datasource." >&2
  exit 1
fi

for ((run_number = 1; run_number <= repeat_count; run_number++)); do
  report_path="${artifact_dir}/pytest-${database_kind}-run-${run_number}.xml"
  echo "Running API suite ${run_number}/${repeat_count} against ${database_kind}..."
  (
    cd "${project_root}"
    timeout --signal=TERM --kill-after=10s "${TASKFLOW_PYTEST_TIMEOUT_SECONDS:-180}" \
      "${venv_dir}/bin/python" -m pytest tests/api \
      --junitxml="${report_path}"
  )
done

if [[ "${TASKFLOW_API_TEST_RUN_MYSQL_PROOF:-false}" == "true" ]]; then
  if [[ "${database_kind}" != "mysql" ]]; then
    echo "TASKFLOW_API_TEST_RUN_MYSQL_PROOF=true requires the mysql database kind." >&2
    exit 2
  fi
  echo "Verifying API writes and project cascades directly in MySQL..."
  timeout --signal=TERM --kill-after=10s "${TASKFLOW_MYSQL_PROOF_TIMEOUT_SECONDS:-120}" \
    "${venv_dir}/bin/python" "${project_root}/scripts/verify-taskflow-mysql.py" \
    --evidence-file "${artifact_dir}/mysql-direct-proof.json" \
    >"${artifact_dir}/mysql-direct-proof.log" 2>&1
  cat "${artifact_dir}/mysql-direct-proof.log"
fi

echo "All ${repeat_count} API suite run(s) passed against ${database_kind}."
echo "Reports and backend log: ${artifact_dir}"
