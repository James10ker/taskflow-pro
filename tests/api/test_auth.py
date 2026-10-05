from __future__ import annotations

import pytest

from .assertions import assert_error
from .client import ApiClient
from .config import ApiTestSettings


def test_login_with_valid_credentials(
    anonymous_client: ApiClient,
    settings: ApiTestSettings,
) -> None:
    response = anonymous_client.post(
        "/auth/login",
        json={"email": settings.owner.email, "password": settings.password},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["token"]["accessToken"], str)
    assert body["token"]["accessToken"]
    assert body["user"]["email"] == settings.owner.email
    assert body["user"]["role"] == "admin"
    assert "password" not in body["user"]
    assert "passwordHash" not in body["user"]


def test_login_rejects_wrong_password(
    anonymous_client: ApiClient,
    settings: ApiTestSettings,
) -> None:
    response = anonymous_client.post(
        "/auth/login",
        json={"email": settings.owner.email, "password": f"{settings.password}x"},
    )

    assert_error(response, 401, "UNAUTHORIZED")


@pytest.mark.parametrize(
    ("payload", "invalid_fields"),
    [
        ({"password": "placeholder"}, {"email"}),
        ({"email": "not-an-email", "password": "placeholder"}, {"email"}),
        ({"email": "api-owner-admin@taskflow.test", "password": ""}, {"password"}),
    ],
    ids=["missing-email", "malformed-email", "blank-password"],
)
def test_login_rejects_invalid_payload(
    anonymous_client: ApiClient,
    payload: dict[str, str],
    invalid_fields: set[str],
) -> None:
    response = anonymous_client.post("/auth/login", json=payload)

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert invalid_fields <= body.get("details", {}).keys()


def test_valid_token_loads_current_user(
    clients: dict[str, ApiClient],
    settings: ApiTestSettings,
) -> None:
    response = clients["member"].get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == settings.member.email
    assert body["role"] == "member"
    assert "password" not in body
    assert "passwordHash" not in body


@pytest.mark.parametrize("token", [None, "not-a-valid-jwt"], ids=["missing", "invalid"])
def test_me_requires_valid_token(
    client_factory,
    token: str | None,
) -> None:
    response = client_factory(token).get("/auth/me")

    assert_error(response, 401, "UNAUTHORIZED")
