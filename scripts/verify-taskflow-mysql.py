#!/usr/bin/env python3
"""Prove that the HTTP API writes to, and cascades inside, isolated MySQL."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pymysql
import requests


OWNER_EMAIL = "api-owner-admin@taskflow.test"


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value:
        raise RuntimeError(f"{name} is required")
    return value


def assert_status(response: requests.Response, expected: int, operation: str) -> None:
    if response.status_code != expected:
        raise RuntimeError(
            f"{operation} returned HTTP {response.status_code}; expected {expected}"
        )


def scalar_count(connection: pymysql.Connection, query: str, value: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(query, (value,))
        result = cursor.fetchone()
    if result is None:
        raise RuntimeError("The database count query returned no row")
    return int(result[0])


def direct_cleanup(
    connection: pymysql.Connection,
    project_id: int,
    task_id: int | None,
    comment_id: int | None,
) -> None:
    with connection.cursor() as cursor:
        if comment_id is not None:
            cursor.execute("DELETE FROM task_comments WHERE id = %s", (comment_id,))
        cursor.execute(
            """
            DELETE FROM task_comments
            WHERE task_id IN (SELECT id FROM tasks WHERE project_id = %s)
            """,
            (project_id,),
        )
        cursor.execute("DELETE FROM activity_logs WHERE project_id = %s", (project_id,))
        if task_id is not None:
            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        cursor.execute("DELETE FROM tasks WHERE project_id = %s", (project_id,))
        cursor.execute("DELETE FROM project_members WHERE project_id = %s", (project_id,))
        cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))


def run(evidence_path: Path) -> None:
    base_url = required_environment("TASKFLOW_API_BASE_URL").rstrip("/")
    api_password = required_environment("TASKFLOW_API_TEST_PASSWORD")
    database_host = required_environment("TASKFLOW_MYSQL_HOST")
    database_port = int(required_environment("TASKFLOW_MYSQL_PORT"))
    database_name = required_environment("TASKFLOW_MYSQL_DATABASE")
    database_user = required_environment("TASKFLOW_MYSQL_USER")
    database_password = required_environment("TASKFLOW_MYSQL_PASSWORD")
    jdbc_url = required_environment("TASKFLOW_TEST_DATABASE_URL")
    if database_name != "taskflow_api_test":
        raise RuntimeError("Direct MySQL proof only permits catalog taskflow_api_test")
    if database_host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Direct MySQL proof only permits a loopback database host")
    jdbc_target = re.fullmatch(
        r"jdbc:mysql://(?:127\.0\.0\.1|localhost):([0-9]+)/taskflow_api_test(?:\?.*)?",
        jdbc_url,
    )
    if jdbc_target is None or int(jdbc_target.group(1)) != database_port:
        raise RuntimeError(
            "Direct MySQL proof settings do not match the guarded loopback JDBC target"
        )

    connection = pymysql.connect(
        host=database_host,
        port=database_port,
        user=database_user,
        password=database_password,
        database=database_name,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )
    session = requests.Session()
    session.trust_env = False
    project_id: int | None = None
    task_id: int | None = None
    comment_id: int | None = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), DATABASE()")
            database_facts = cursor.fetchone()
            cursor.execute(
                """
                SELECT version
                FROM flyway_schema_history
                WHERE success = TRUE
                ORDER BY installed_rank
                """
            )
            flyway_versions = [str(row[0]) for row in cursor.fetchall()]
        if database_facts is None:
            raise RuntimeError("MySQL did not return version and catalog")
        database_version, actual_catalog = map(str, database_facts)
        if not database_version.startswith("8.4.") or actual_catalog != database_name:
            raise RuntimeError("The direct proof is not connected to isolated MySQL 8.4")
        if flyway_versions[:2] != ["1", "2"]:
            raise RuntimeError(
                f"Expected Flyway history to begin with versions 1 and 2, got {flyway_versions!r}"
            )

        login_response = session.post(
            f"{base_url}/auth/login",
            json={"email": OWNER_EMAIL, "password": api_password},
            timeout=(2, 8),
        )
        assert_status(login_response, 200, "owner login")
        login_body = login_response.json()
        token = login_body.get("token", {}).get("accessToken")
        api_owner_id = login_body.get("user", {}).get("id")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Owner login did not return an access token")
        if not isinstance(api_owner_id, str) or not api_owner_id.isdigit():
            raise RuntimeError("Owner login did not return a numeric string ID")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        create_response = session.post(
            f"{base_url}/projects",
            headers=headers,
            json={
                "name": f"MySQL direct proof {uuid4().hex[:12]}",
                "description": "Temporary API-created row for isolated MySQL evidence.",
            },
            timeout=(2, 8),
        )
        assert_status(create_response, 201, "project creation")
        project_body: dict[str, Any] = create_response.json()
        raw_project_id = project_body.get("id")
        if not isinstance(raw_project_id, str) or not raw_project_id.isdigit():
            raise RuntimeError("Project creation did not return a numeric string ID")
        project_id = int(raw_project_id)
        owner_id = int(api_owner_id)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.owner_id, pm.user_id, pm.member_role
                FROM projects p
                JOIN project_members pm ON pm.project_id = p.id
                WHERE p.id = %s
                ORDER BY pm.user_id
                """,
                (project_id,),
            )
            membership_rows = cursor.fetchall()
        expected_membership = ((owner_id, owner_id, "owner"),)
        if membership_rows != expected_membership:
            raise RuntimeError("API-created project/owner membership was not found in MySQL")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (
                    project_id, title, description, status, priority, creator_id
                ) VALUES (%s, %s, %s, 'todo', 'medium', %s)
                """,
                (project_id, "MySQL cascade proof", "Temporary association", owner_id),
            )
            task_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO task_comments (task_id, author_id, body) VALUES (%s, %s, %s)",
                (task_id, owner_id, "Temporary cascade proof"),
            )
            comment_id = int(cursor.lastrowid)
            cursor.execute(
                """
                INSERT INTO activity_logs (
                    project_id, actor_id, action, entity_type, entity_id, description
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    project_id,
                    owner_id,
                    "mysql_proof",
                    "project",
                    project_id,
                    "Temporary cascade proof",
                ),
            )

        delete_response = session.delete(
            f"{base_url}/projects/{project_id}",
            headers=headers,
            timeout=(2, 8),
        )
        assert_status(delete_response, 200, "project deletion")
        if delete_response.json() != {"success": True}:
            raise RuntimeError("Project deletion returned an unexpected response")
        cascade_counts = {
            "projects": scalar_count(
                connection, "SELECT COUNT(*) FROM projects WHERE id = %s", project_id
            ),
            "project_members": scalar_count(
                connection,
                "SELECT COUNT(*) FROM project_members WHERE project_id = %s",
                project_id,
            ),
            "tasks": scalar_count(
                connection, "SELECT COUNT(*) FROM tasks WHERE project_id = %s", project_id
            ),
            "task_comments": scalar_count(
                connection,
                "SELECT COUNT(*) FROM task_comments WHERE id = %s",
                comment_id,
            ),
            "activity_logs": scalar_count(
                connection,
                "SELECT COUNT(*) FROM activity_logs WHERE project_id = %s",
                project_id,
            ),
        }
        if any(cascade_counts.values()):
            raise RuntimeError("Project deletion left associated rows in MySQL")

        evidence = {
            "databaseProduct": "MySQL",
            "databaseVersion": database_version,
            "catalog": actual_catalog,
            "flywayVersions": flyway_versions,
            "apiProjectObserved": True,
            "ownerMembershipObserved": True,
            "apiDeleteSucceeded": True,
            "cascadeCountsAfterDelete": cascade_counts,
        }
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "Direct MySQL proof passed: API project and owner membership observed; "
            "project/member/task/comment/activity rows are all zero after API deletion."
        )
        print(f"MySQL version {database_version}; catalog {actual_catalog}.")
    finally:
        if project_id is not None:
            try:
                direct_cleanup(connection, project_id, task_id, comment_id)
            except Exception as cleanup_error:
                print(
                    f"WARNING: direct cleanup of the temporary proof project failed: "
                    f"{type(cleanup_error).__name__}",
                    file=sys.stderr,
                )
        session.close()
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-file", required=True, type=Path)
    arguments = parser.parse_args()
    run(arguments.evidence_file)


if __name__ == "__main__":
    main()
