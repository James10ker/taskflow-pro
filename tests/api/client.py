from __future__ import annotations

from typing import Any

import requests

from .config import ApiTestSettings


class ApiClient:
    """Small requests-based client that deliberately leaves 4xx responses inspectable."""

    def __init__(
        self,
        settings: ApiTestSettings,
        *,
        token: str | None = None,
    ) -> None:
        self._base_url = settings.base_url
        self._timeout = settings.timeout
        self._token = token
        self._session = requests.Session()
        self._session.trust_env = False
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "taskflow-api-tests/1.0",
            }
        )

    def close(self) -> None:
        self._session.close()

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}))
        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"
        return self._session.request(
            method,
            f"{self._base_url}/{path.lstrip('/')}",
            headers=headers,
            timeout=self._timeout,
            allow_redirects=False,
            **kwargs,
        )

    def get(self, path: str) -> requests.Response:
        return self.request("GET", path)

    def post(self, path: str, *, json: Any) -> requests.Response:
        return self.request("POST", path, json=json)

    def put(self, path: str, *, json: Any) -> requests.Response:
        return self.request("PUT", path, json=json)

    def delete(self, path: str) -> requests.Response:
        return self.request("DELETE", path)


def login(
    client: ApiClient,
    *,
    email: str,
    password: str,
) -> tuple[str, dict[str, Any]]:
    response = client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, (
        f"Login setup failed for {email}: HTTP {response.status_code}"
    )
    body = response.json()
    token = body.get("token", {}).get("accessToken")
    user = body.get("user")
    assert isinstance(token, str) and token, "Login response has no access token."
    assert isinstance(user, dict), "Login response has no user object."
    return token, user
