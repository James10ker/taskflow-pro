#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repeat_count="${1:-${TASKFLOW_API_TEST_REPEAT:-3}}"
python_command="${PYTHON_BIN:-python3}"
container_name="taskflow-w3-mysql-$(date +%Y%m%d%H%M%S)-$$"
database_name="taskflow_api_test"
database_user="taskflow_api_test"
container_created="false"
docker_command=()
mysql_wait_seconds="${TASKFLOW_MYSQL_WAIT_SECONDS:-120}"

if [[ ! "${repeat_count}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Usage: $0 [positive-repeat-count]" >&2
  exit 2
fi
if [[ ! "${mysql_wait_seconds}" =~ ^[1-9][0-9]*$ ]]; then
  echo "TASKFLOW_MYSQL_WAIT_SECONDS must be a positive integer." >&2
  exit 2
fi
if ! command -v "${python_command}" >/dev/null 2>&1; then
  echo "Required command is unavailable: ${python_command}" >&2
  exit 2
fi

if [[ -n "${DOCKER_BIN:-}" ]]; then
  if [[ ! -x "${DOCKER_BIN}" ]] && ! command -v "${DOCKER_BIN}" >/dev/null 2>&1; then
    echo "DOCKER_BIN is not executable: ${DOCKER_BIN}" >&2
    exit 2
  fi
  docker_command=("${DOCKER_BIN}")
elif command -v docker >/dev/null 2>&1 && docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  docker_command=(docker)
elif [[ -x '/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' ]] \
    && '/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe' \
      version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  docker_command=('/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe')
else
  echo "No working Docker daemon was found." >&2
  echo "Enable Docker Desktop WSL integration or set DOCKER_BIN to an authorized Docker CLI." >&2
  exit 2
fi

cleanup_container() {
  if [[ "${container_created}" != "true" ]]; then
    return
  fi
  if "${docker_command[@]}" inspect "${container_name}" >/dev/null 2>&1; then
    if ! "${docker_command[@]}" rm --force "${container_name}" >/dev/null 2>&1; then
      echo "The owned MySQL container could not be removed: ${container_name}" >&2
      return 1
    fi
  fi
  container_created="false"
}

on_exit() {
  local exit_status=$?
  local cleanup_status=0
  trap - EXIT
  cleanup_container || cleanup_status=$?
  if (( exit_status == 0 && cleanup_status != 0 )); then
    exit_status="${cleanup_status}"
  fi
  exit "${exit_status}"
}

trap on_exit EXIT
trap 'exit 130' INT TERM

database_password="$("${python_command}" -c 'import secrets; print(secrets.token_urlsafe(32))')"
root_password="$("${python_command}" -c 'import secrets; print(secrets.token_urlsafe(32))')"

echo "Starting an isolated MySQL 8.4 container with no persistent volume..."
"${docker_command[@]}" run --detach --rm \
  --name "${container_name}" \
  --tmpfs /var/lib/mysql \
  --publish 127.0.0.1::3306 \
  --env "MYSQL_DATABASE=${database_name}" \
  --env "MYSQL_USER=${database_user}" \
  --env "MYSQL_PASSWORD=${database_password}" \
  --env "MYSQL_ROOT_PASSWORD=${root_password}" \
  mysql:8.4 >/dev/null
container_created="true"

deadline=$((SECONDS + mysql_wait_seconds))
until "${docker_command[@]}" exec \
    --env "MYSQL_PWD=${database_password}" \
    "${container_name}" \
    mysqladmin ping --host=127.0.0.1 --user="${database_user}" --silent \
    >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "MySQL did not become ready before the timeout." >&2
    "${docker_command[@]}" logs --tail 120 "${container_name}" >&2 || true
    exit 1
  fi
  sleep 1
done

published_address="$(
  "${docker_command[@]}" port "${container_name}" 3306/tcp \
    | tr -d '\r' \
    | tail -n 1
)"
mysql_port="${published_address##*:}"
if [[ ! "${mysql_port}" =~ ^[0-9]+$ ]]; then
  echo "Could not determine the isolated MySQL host port." >&2
  exit 1
fi

server_facts="$(
  "${docker_command[@]}" exec \
    --env "MYSQL_PWD=${database_password}" \
    "${container_name}" \
    mysql --batch --skip-column-names \
      --host=127.0.0.1 --user="${database_user}" "${database_name}" \
      --execute='SELECT VERSION(), DATABASE()' \
    | tr -d '\r'
)"
server_version="${server_facts%%$'\t'*}"
server_catalog="${server_facts#*$'\t'}"
if [[ ! "${server_version}" =~ ^8[.]4([.]|$) ]] || [[ "${server_catalog}" != "${database_name}" ]]; then
  echo "Expected MySQL 8.4 and catalog ${database_name}; received a different target." >&2
  exit 1
fi
echo "MySQL ${server_version}; isolated catalog ${server_catalog}; host port ${mysql_port}."

export TASKFLOW_API_TEST_DATABASE_KIND="mysql"
export TASKFLOW_TEST_DATABASE_URL="jdbc:mysql://127.0.0.1:${mysql_port}/${database_name}?useUnicode=true&characterEncoding=utf8&serverTimezone=UTC&allowPublicKeyRetrieval=true&useSSL=false"
export TASKFLOW_TEST_DATABASE_USER="${database_user}"
export TASKFLOW_TEST_DATABASE_PASSWORD="${database_password}"
export TASKFLOW_MYSQL_HOST="127.0.0.1"
export TASKFLOW_MYSQL_PORT="${mysql_port}"
export TASKFLOW_MYSQL_DATABASE="${database_name}"
export TASKFLOW_MYSQL_USER="${database_user}"
export TASKFLOW_MYSQL_PASSWORD="${database_password}"
export TASKFLOW_API_TEST_RUN_MYSQL_PROOF="true"
export TASKFLOW_API_TEST_ARTIFACT_DIR="${TASKFLOW_API_TEST_ARTIFACT_DIR:-${project_root}/.artifacts/api-tests-mysql}"

"${project_root}/scripts/run-api-tests.sh" "${repeat_count}"

echo "Removing the owned temporary MySQL container ${container_name}."
