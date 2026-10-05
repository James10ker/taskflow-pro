from __future__ import annotations

from typing import Any

import requests


PROJECT_FIELDS = {
    "id",
    "name",
    "description",
    "status",
    "ownerId",
    "memberIds",
    "createdAt",
    "updatedAt",
}


def assert_error(response: requests.Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status
    assert response.headers.get("Content-Type", "").startswith("application/json")
    body = response.json()
    assert body.get("code") == code
    assert isinstance(body.get("message"), str) and body["message"]
    return body


def assert_project_shape(project: Any) -> dict[str, Any]:
    assert isinstance(project, dict)
    assert PROJECT_FIELDS <= project.keys()
    assert isinstance(project["id"], str) and project["id"]
    assert isinstance(project["name"], str) and project["name"]
    assert isinstance(project["description"], str)
    assert project["status"] in {"active", "paused", "completed"}
    assert isinstance(project["ownerId"], str) and project["ownerId"]
    assert isinstance(project["memberIds"], list)
    assert all(isinstance(member_id, str) for member_id in project["memberIds"])
    assert project["ownerId"] in project["memberIds"]
    assert isinstance(project["createdAt"], str) and project["createdAt"]
    assert isinstance(project["updatedAt"], str) and project["updatedAt"]
    return project
