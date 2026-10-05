from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Account:
    email: str
    role: str


@dataclass(frozen=True)
class ApiTestSettings:
    base_url: str
    password: str
    connect_timeout: float
    read_timeout: float
    owner: Account
    member: Account
    outsider: Account
    outsider_admin: Account
    shared_project_name: str

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout, self.read_timeout)

    @classmethod
    def from_environment(cls) -> "ApiTestSettings":
        base_url = os.getenv(
            "TASKFLOW_API_BASE_URL", "http://127.0.0.1:18080/api"
        ).rstrip("/")
        _validate_target(base_url)

        password = os.getenv("TASKFLOW_API_TEST_PASSWORD")
        if not password:
            raise RuntimeError(
                "TASKFLOW_API_TEST_PASSWORD is required. It must match the isolated "
                "backend's APP_API_TEST_PASSWORD value."
            )

        return cls(
            base_url=base_url,
            password=password,
            connect_timeout=_positive_float("TASKFLOW_API_CONNECT_TIMEOUT", "2"),
            read_timeout=_positive_float("TASKFLOW_API_READ_TIMEOUT", "8"),
            owner=Account("api-owner-admin@taskflow.test", "admin"),
            member=Account("api-member@taskflow.test", "member"),
            outsider=Account("api-outsider@taskflow.test", "member"),
            outsider_admin=Account("api-outsider-admin@taskflow.test", "admin"),
            shared_project_name="API Test Shared Member Project",
        )


def _positive_float(name: str, default: str) -> float:
    raw_value = os.getenv(name, default)
    try:
        value = float(raw_value)
    except ValueError as exception:
        raise RuntimeError(f"{name} must be a number, got {raw_value!r}.") from exception
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return value


def _validate_target(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError(
            "TASKFLOW_API_BASE_URL must be an absolute http(s) URL."
        )
    if parsed.username or parsed.password:
        raise RuntimeError("Credentials must not be embedded in TASKFLOW_API_BASE_URL.")

    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    allow_remote = os.getenv("TASKFLOW_API_TEST_ALLOW_REMOTE", "false").lower()
    if parsed.hostname not in loopback_hosts and allow_remote != "true":
        raise RuntimeError(
            "Refusing to run write-capable API tests against a non-loopback host. "
            "Set TASKFLOW_API_TEST_ALLOW_REMOTE=true only for an explicitly isolated "
            "test environment."
        )
