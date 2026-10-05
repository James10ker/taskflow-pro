from __future__ import annotations

from typing import Any

import pytest

from .assertions import assert_error, assert_project_shape
from .client import ApiClient
from .config import ApiTestSettings
from .conftest import ProjectRegistry


def test_admin_creates_project_with_server_owned_identity(
    clients: dict[str, ApiClient],
    settings: ApiTestSettings,
    project_registry: ProjectRegistry,
) -> None:
    created = project_registry.create(
        name="  API project trims its name  ", description="Creation verification"
    )
    assert_project_shape(created)
    assert created["name"] == "API project trims its name"
    assert created["description"] == "Creation verification"
    assert created["status"] == "active"

    me = clients["owner"].get("/auth/me").json()
    assert created["ownerId"] == me["id"]
    assert created["memberIds"] == [me["id"]]

    fetched = clients["owner"].get(f"/projects/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_regular_user_cannot_create_project(
    clients: dict[str, ApiClient],
    project_registry: ProjectRegistry,
) -> None:
    response = clients["member"].post(
        "/projects", json={"name": "Forbidden create", "description": "No write"}
    )

    project_registry.register_response(response, clients["member"])
    assert_error(response, 403, "FORBIDDEN")


def test_project_name_validation_and_boundaries(
    clients: dict[str, ApiClient],
    project_registry: ProjectRegistry,
) -> None:
    for invalid_name in ("   ", "x" * 151):
        response = clients["owner"].post(
            "/projects", json={"name": invalid_name, "description": "Invalid"}
        )
        project_registry.register_response(response, clients["owner"])
        body = assert_error(response, 422, "VALIDATION_ERROR")
        assert "name" in body.get("details", {})

    boundary_project = project_registry.create(name="x" * 150)
    assert len(boundary_project["name"]) == 150


def test_create_rejects_client_supplied_owner_or_members(
    clients: dict[str, ApiClient],
    project_registry: ProjectRegistry,
) -> None:
    outsider_id = clients["outsider"].get("/auth/me").json()["id"]
    response = clients["owner"].post(
        "/projects",
        json={
            "name": "Identity injection",
            "description": "Must not be accepted",
            "ownerId": outsider_id,
            "memberIds": [outsider_id],
        },
    )

    project_registry.register_response(
        response, clients["owner"], clients["outsider"]
    )
    assert_error(response, 400, "INVALID_REQUEST")


def test_owner_can_list_and_read_shared_project(
    clients: dict[str, ApiClient],
    shared_project: dict[str, Any],
) -> None:
    project_id = shared_project["id"]
    response = clients["owner"].get("/projects")

    assert response.status_code == 200
    projects = response.json()
    assert project_id in {project["id"] for project in projects}
    detail = clients["owner"].get(f"/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json() == shared_project


def test_legal_member_can_list_and_read_shared_project(
    clients: dict[str, ApiClient],
    shared_project: dict[str, Any],
) -> None:
    project_id = shared_project["id"]
    response = clients["member"].get("/projects")

    assert response.status_code == 200
    projects = response.json()
    assert project_id in {project["id"] for project in projects}
    detail = clients["member"].get(f"/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json() == shared_project


def test_nonmember_cannot_list_or_read_shared_project(
    clients: dict[str, ApiClient],
    shared_project: dict[str, Any],
) -> None:
    project_id = shared_project["id"]
    listing = clients["outsider"].get("/projects")

    assert listing.status_code == 200
    assert project_id not in {project["id"] for project in listing.json()}
    assert_error(
        clients["outsider"].get(f"/projects/{project_id}"), 403, "FORBIDDEN"
    )


def test_global_admin_without_membership_has_no_project_access(
    clients: dict[str, ApiClient],
    shared_project: dict[str, Any],
) -> None:
    project_id = shared_project["id"]
    before = clients["owner"].get(f"/projects/{project_id}").json()
    listing = clients["outsider_admin"].get("/projects")

    assert listing.status_code == 200
    assert project_id not in {project["id"] for project in listing.json()}
    assert_error(
        clients["outsider_admin"].get(f"/projects/{project_id}"),
        403,
        "FORBIDDEN",
    )
    assert_error(
        clients["outsider_admin"].put(
            f"/projects/{project_id}",
            json={
                "name": "Global admin attempted update",
                "description": "Must not persist",
                "status": "completed",
            },
        ),
        403,
        "FORBIDDEN",
    )
    assert_error(
        clients["outsider_admin"].delete(f"/projects/{project_id}"),
        403,
        "FORBIDDEN",
    )
    after = clients["owner"].get(f"/projects/{project_id}")
    assert after.status_code == 200
    assert after.json() == before


def test_member_cannot_update_and_project_stays_unchanged(
    clients: dict[str, ApiClient],
    shared_project: dict[str, Any],
) -> None:
    project_id = shared_project["id"]
    before = clients["owner"].get(f"/projects/{project_id}").json()
    response = clients["member"].put(
        f"/projects/{project_id}",
        json={
            "name": "Member attempted update",
            "description": "Must not persist",
            "status": "paused",
        },
    )

    assert_error(response, 403, "FORBIDDEN")
    after = clients["owner"].get(f"/projects/{project_id}")
    assert after.status_code == 200
    assert after.json() == before


def test_member_cannot_delete_and_project_still_exists(
    clients: dict[str, ApiClient],
    shared_project: dict[str, Any],
) -> None:
    project_id = shared_project["id"]
    response = clients["member"].delete(f"/projects/{project_id}")

    assert_error(response, 403, "FORBIDDEN")
    after = clients["owner"].get(f"/projects/{project_id}")
    assert after.status_code == 200
    assert after.json()["id"] == project_id


def test_owner_update_persists_on_subsequent_read(
    clients: dict[str, ApiClient],
    project: dict[str, Any],
) -> None:
    project_id = project["id"]
    response = clients["owner"].put(
        f"/projects/{project_id}",
        json={
            "name": "Updated through real API",
            "description": "The new project description",
            "status": "paused",
        },
    )

    assert response.status_code == 200
    updated = assert_project_shape(response.json())
    assert updated["name"] == "Updated through real API"
    assert updated["description"] == "The new project description"
    assert updated["status"] == "paused"
    fetched = clients["owner"].get(f"/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json() == updated


def test_owner_delete_makes_project_unavailable(
    clients: dict[str, ApiClient],
    project: dict[str, Any],
    project_registry: ProjectRegistry,
) -> None:
    project_id = project["id"]
    response = clients["owner"].delete(f"/projects/{project_id}")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    project_registry.forget(project_id)
    assert_error(
        clients["owner"].get(f"/projects/{project_id}"), 404, "NOT_FOUND"
    )


def test_missing_project_has_consistent_not_found_contract(
    clients: dict[str, ApiClient],
    missing_project_id: str,
) -> None:
    responses = [
        clients["owner"].get(f"/projects/{missing_project_id}"),
        clients["owner"].put(
            f"/projects/{missing_project_id}",
            json={"name": "Missing", "description": "Missing", "status": "active"},
        ),
        clients["owner"].delete(f"/projects/{missing_project_id}"),
    ]

    for response in responses:
        assert_error(response, 404, "NOT_FOUND")


@pytest.mark.parametrize(
    ("method", "path_template", "payload"),
    [
        ("GET", "/projects", None),
        ("POST", "/projects", {"name": "No auth", "description": "Denied"}),
        ("GET", "/projects/{id}", None),
        (
            "PUT",
            "/projects/{id}",
            {"name": "No auth", "description": "Denied", "status": "active"},
        ),
        ("DELETE", "/projects/{id}", None),
    ],
    ids=["list", "create", "detail", "update", "delete"],
)
def test_project_endpoints_require_authentication(
    anonymous_client: ApiClient,
    shared_project: dict[str, Any],
    project_registry: ProjectRegistry,
    method: str,
    path_template: str,
    payload: dict[str, str] | None,
) -> None:
    path = path_template.format(id=shared_project["id"])
    kwargs = {"json": payload} if payload is not None else {}
    response = anonymous_client.request(method, path, **kwargs)

    if method == "POST":
        project_registry.register_response(response, anonymous_client)
    assert_error(response, 401, "UNAUTHORIZED")


def test_invalid_project_id_has_explicit_client_error(
    clients: dict[str, ApiClient],
) -> None:
    assert_error(
        clients["owner"].get("/projects/not-a-number"), 400, "INVALID_REQUEST"
    )


def test_malformed_project_json_has_explicit_client_error(
    clients: dict[str, ApiClient],
    project_registry: ProjectRegistry,
) -> None:
    response = clients["owner"].request(
        "POST",
        "/projects",
        data='{"name": "unfinished"',
        headers={"Content-Type": "application/json"},
    )

    project_registry.register_response(response, clients["owner"])
    assert_error(response, 400, "INVALID_REQUEST")
