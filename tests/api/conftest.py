from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from .client import ApiClient, login
from .config import ApiTestSettings


@pytest.fixture(scope="session")
def settings() -> ApiTestSettings:
    return ApiTestSettings.from_environment()


@pytest.fixture(scope="session")
def anonymous_client(settings: ApiTestSettings) -> Iterator[ApiClient]:
    client = ApiClient(settings)
    yield client
    client.close()


@pytest.fixture(scope="session")
def tokens(
    settings: ApiTestSettings,
    anonymous_client: ApiClient,
) -> dict[str, str]:
    accounts = {
        "owner": settings.owner,
        "member": settings.member,
        "outsider": settings.outsider,
        "outsider_admin": settings.outsider_admin,
    }
    result: dict[str, str] = {}
    for key, account in accounts.items():
        token, user = login(
            anonymous_client,
            email=account.email,
            password=settings.password,
        )
        assert user.get("email") == account.email
        assert user.get("role") == account.role
        result[key] = token
    return result


@pytest.fixture(scope="session")
def clients(
    settings: ApiTestSettings,
    tokens: dict[str, str],
) -> Iterator[dict[str, ApiClient]]:
    result = {key: ApiClient(settings, token=token) for key, token in tokens.items()}
    yield result
    for client in result.values():
        client.close()


@pytest.fixture
def client_factory(
    settings: ApiTestSettings,
) -> Iterator[Callable[[str | None], ApiClient]]:
    opened: list[ApiClient] = []

    def create(token: str | None) -> ApiClient:
        client = ApiClient(settings, token=token)
        opened.append(client)
        return client

    yield create
    for client in opened:
        client.close()


@pytest.fixture(scope="session")
def shared_project(
    settings: ApiTestSettings,
    clients: dict[str, ApiClient],
) -> dict[str, Any]:
    response = clients["owner"].get("/projects")
    assert response.status_code == 200
    projects = response.json()
    assert isinstance(projects, list)
    matches = [
        project
        for project in projects
        if project.get("name") == settings.shared_project_name
    ]
    assert len(matches) == 1, (
        "The api-test profile must prepare exactly one shared owner/member project."
    )
    return matches[0]


@dataclass
class ProjectRegistry:
    owner_client: ApiClient
    cleanup_candidates: tuple[ApiClient, ...]
    created: list[tuple[str, tuple[ApiClient, ...]]] = field(default_factory=list)

    def register_response(
        self,
        response,
        *preferred_clients: ApiClient,
    ) -> None:
        """Register any accidentally successful create before making assertions."""
        if not 200 <= response.status_code < 300:
            return
        try:
            project_id = response.json().get("id")
        except (AttributeError, ValueError):
            return
        if not isinstance(project_id, str) or not project_id:
            return
        candidates = tuple(
            dict.fromkeys((*preferred_clients, *self.cleanup_candidates))
        )
        self.created.append((project_id, candidates))

    def create(
        self,
        *,
        name: str | None = None,
        description: str = "Created by the black-box API test suite.",
    ) -> dict[str, Any]:
        project_name = name or f"API test project {uuid4().hex[:12]}"
        response = self.owner_client.post(
            "/projects",
            json={"name": project_name, "description": description},
        )
        self.register_response(response, self.owner_client)
        assert response.status_code == 201
        project = response.json()
        project_id = project.get("id")
        assert isinstance(project_id, str) and project_id
        return project

    def forget(self, project_id: str) -> None:
        self.created = [entry for entry in self.created if entry[0] != project_id]

    def cleanup(self) -> None:
        failures: list[tuple[str, list[int]]] = []
        for project_id, candidates in reversed(self.created):
            statuses: list[int] = []
            for client in candidates:
                response = client.delete(f"/projects/{project_id}")
                statuses.append(response.status_code)
                if response.status_code in {200, 404}:
                    break
            else:
                failures.append((project_id, statuses))
        self.created.clear()
        if failures:
            pytest.fail(f"Project cleanup failed (id, attempted statuses): {failures}")


@pytest.fixture
def project_registry(
    clients: dict[str, ApiClient],
) -> Iterator[ProjectRegistry]:
    registry = ProjectRegistry(
        clients["owner"],
        tuple(clients.values()),
    )
    yield registry
    registry.cleanup()


@pytest.fixture
def project(project_registry: ProjectRegistry) -> dict[str, Any]:
    return project_registry.create()


@pytest.fixture
def missing_project_id(
    clients: dict[str, ApiClient],
    project_registry: ProjectRegistry,
) -> str:
    created = project_registry.create()
    project_id = created["id"]
    response = clients["owner"].delete(f"/projects/{project_id}")
    assert response.status_code == 200
    assert response.json() == {"success": True}
    project_registry.forget(project_id)
    return project_id
