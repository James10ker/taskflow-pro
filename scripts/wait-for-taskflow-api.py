#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any
from urllib.parse import urlparse

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wait for Taskflow HTTP and database-backed authentication readiness."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("TASKFLOW_API_BASE_URL", "http://127.0.0.1:18080/api"),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("TASKFLOW_API_WAIT_SECONDS", "90")),
    )
    parser.add_argument("--pid", type=int, help="Fail early if this backend PID exits.")
    return parser.parse_args()


def process_is_alive(pid: int | None) -> bool:
    if pid is None:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def response_json(response: requests.Response) -> dict[str, Any]:
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("response is not a JSON object")
    return body


def target_is_allowed(base_url: str) -> bool:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    return os.getenv("TASKFLOW_API_TEST_ALLOW_REMOTE", "false").lower() == "true"


def main() -> int:
    args = parse_args()
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be greater than zero.", file=sys.stderr)
        return 2

    password = os.getenv("TASKFLOW_API_TEST_PASSWORD") or os.getenv(
        "APP_API_TEST_PASSWORD"
    )
    if not password:
        print(
            "TASKFLOW_API_TEST_PASSWORD (or APP_API_TEST_PASSWORD) is required.",
            file=sys.stderr,
        )
        return 2

    owner_email = os.getenv(
        "TASKFLOW_API_TEST_OWNER_EMAIL", "api-owner-admin@taskflow.test"
    )
    base_url = args.base_url.rstrip("/")
    if not target_is_allowed(base_url):
        print(
            "Refusing to send test credentials to this target. Use a loopback URL or "
            "set TASKFLOW_API_TEST_ALLOW_REMOTE=true for an isolated remote test host.",
            file=sys.stderr,
        )
        return 2
    deadline = time.monotonic() + args.timeout_seconds
    last_failure = "backend has not accepted a request yet"

    session = requests.Session()
    session.trust_env = False
    try:
        while time.monotonic() < deadline:
            if not process_is_alive(args.pid):
                print("Backend process exited before becoming ready.", file=sys.stderr)
                return 1
            try:
                health = session.get(
                    f"{base_url}/health", timeout=(1.0, 2.0), allow_redirects=False
                )
                if health.status_code != 200:
                    last_failure = f"health returned HTTP {health.status_code}"
                    time.sleep(0.5)
                    continue

                login = session.post(
                    f"{base_url}/auth/login",
                    json={"email": owner_email, "password": password},
                    timeout=(1.0, 5.0),
                    allow_redirects=False,
                )
                if login.status_code != 200:
                    last_failure = f"database-backed login returned HTTP {login.status_code}"
                    time.sleep(0.5)
                    continue

                login_body = response_json(login)
                token = login_body.get("token", {}).get("accessToken")
                if not isinstance(token, str) or not token:
                    last_failure = "login response did not contain an access token"
                    time.sleep(0.5)
                    continue

                current_user = session.get(
                    f"{base_url}/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=(1.0, 5.0),
                    allow_redirects=False,
                )
                if current_user.status_code != 200:
                    last_failure = f"authenticated probe returned HTTP {current_user.status_code}"
                    time.sleep(0.5)
                    continue
                if response_json(current_user).get("email") != owner_email:
                    last_failure = "authenticated probe returned the wrong test identity"
                    time.sleep(0.5)
                    continue

                print("Taskflow is ready; database-backed login and /auth/me succeeded.")
                return 0
            except (requests.RequestException, ValueError) as exception:
                last_failure = type(exception).__name__
                time.sleep(0.5)
    finally:
        session.close()

    print(
        f"Taskflow did not become ready within {args.timeout_seconds:g}s "
        f"(last failure: {last_failure}).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
