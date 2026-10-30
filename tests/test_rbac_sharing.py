
from io import BytesIO

from fastapi.testclient import TestClient

from app.models.user import User


def create_user(client: TestClient, username: str, email: str):
    register_response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "TestPassword123!",
        },
    )

    assert register_response.status_code in (200, 201), register_response.text

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "TestPassword123!",
        },
    )

    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]

    return {
        "username": username,
        "headers": {"Authorization": f"Bearer {token}"},
        "token": token,
    }


def set_user_role(client: TestClient, username: str, role: str):
    session_factory = client.app.state.TestingSessionLocal

    with session_factory() as db:
        user = db.query(User).filter(User.username == username).first()

        assert user is not None, f"User '{username}' was not found"

        user.role = role
        db.commit()


def upload_document(client: TestClient, headers: dict):
    response = client.post(
        "/documents/upload",
        headers=headers,
        files={
            "file": (
                "test_document.txt",
                BytesIO(b"Test document content"),
                "text/plain",
            )
        },
    )

    assert response.status_code in (200, 201), response.text

    return response.json()


def test_viewer_cannot_upload_document(client: TestClient):
    user = create_user(client, "viewer_upload", "viewer_upload@example.com")
    set_user_role(client, "viewer_upload", "viewer")

    response = client.post(
        "/documents/upload",
        headers=user["headers"],
        files={
            "file": (
                "viewer_document.txt",
                BytesIO(b"Viewer document"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 403


def test_viewer_cannot_delete_document(client: TestClient):
    user = create_user(client, "viewer_delete", "viewer_delete@example.com")

    document = upload_document(client, user["headers"])
    document_id = document["id"]

    set_user_role(client, "viewer_delete", "viewer")

    response = client.delete(
        f"/documents/{document_id}",
        headers=user["headers"],
    )

    assert response.status_code == 403


def test_admin_can_change_user_role(client: TestClient):
    admin = create_user(client, "test_admin", "test_admin@example.com")
    target = create_user(client, "role_target", "role_target@example.com")

    set_user_role(client, "test_admin", "admin")

    response = client.patch(
        f"/admin/users/{get_user_id(client, 'role_target')}/role",
        headers=admin["headers"],
        json={"role": "manager"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "manager"


def test_regular_user_cannot_change_user_role(client: TestClient):
    regular_user = create_user(
        client,
        "regular_role_user",
        "regular_role_user@example.com",
    )
    target = create_user(
        client,
        "regular_role_target",
        "regular_role_target@example.com",
    )

    target_id = get_user_id(client, "regular_role_target")

    response = client.patch(
        f"/admin/users/{target_id}/role",
        headers=regular_user["headers"],
        json={"role": "admin"},
    )

    assert response.status_code == 403


def test_owner_can_share_document_and_recipient_can_download(
    client: TestClient,
):
    owner = create_user(
        client,
        "share_owner",
        "share_owner@example.com",
    )
    recipient = create_user(
        client,
        "share_recipient",
        "share_recipient@example.com",
    )

    document = upload_document(client, owner["headers"])
    document_id = document["id"]

    share_response = client.post(
        f"/sharing/{document_id}",
        headers=owner["headers"],
        json={
            "username": "share_recipient",
            "permission": "viewer",
        },
    )

    assert share_response.status_code in (200, 201), share_response.text

    recipient_login = client.post(
        "/auth/login",
        json={
            "username": "share_recipient",
            "password": "TestPassword123!",
        },
    )

    assert recipient_login.status_code == 200, recipient_login.text

    recipient_headers = {
        "Authorization": (
            f"Bearer {recipient_login.json()['access_token']}"
        )
    }

    download_response = client.get(
        f"/sharing/{document_id}/download",
        headers=recipient_headers,
    )

    assert download_response.status_code == 200, (
    f"Status: {download_response.status_code}, "
    f"Response: {download_response.text}"
)
    assert download_response.content == b"Test document content"

    recipient_id = get_user_id(client, "share_recipient")

    revoke_response = client.delete(
        f"/sharing/{document_id}/{recipient_id}",
        headers=owner["headers"],
    )

    assert revoke_response.status_code in (200, 204), (
    f"Status: {revoke_response.status_code}, "
    f"Response: {revoke_response.text}"
)

    download_after_revoke = client.get(
        f"/sharing/{document_id}/download",
        headers=recipient_headers,
    )

    assert download_after_revoke.status_code == 404


def test_user_cannot_share_another_users_document(client: TestClient):
    owner = create_user(
        client,
        "document_owner",
        "document_owner@example.com",
    )
    other_user = create_user(
        client,
        "other_document_user",
        "other_document_user@example.com",
    )
    recipient = create_user(
        client,
        "other_document_recipient",
        "other_document_recipient@example.com",
    )

    document = upload_document(client, owner["headers"])
    document_id = document["id"]

    response = client.post(
        f"/sharing/{document_id}",
        headers=other_user["headers"],
        json={
            "username": "other_document_recipient",
            "permission": "viewer",
        },
    )

    assert response.status_code == 403


def test_viewer_cannot_share_documents(client: TestClient):
    owner = create_user(
        client,
        "viewer_share_owner",
        "viewer_share_owner@example.com",
    )
    recipient = create_user(
        client,
        "viewer_share_recipient",
        "viewer_share_recipient@example.com",
    )

    document = upload_document(client, owner["headers"])
    document_id = document["id"]

    set_user_role(client, "viewer_share_owner", "viewer")

    response = client.post(
        f"/sharing/{document_id}",
        headers=owner["headers"],
        json={
            "username": "viewer_share_recipient",
            "permission": "viewer",
        },
    )

    assert response.status_code == 403


def get_user_id(client: TestClient, username: str) -> int:
    session_factory = client.app.state.TestingSessionLocal

    with session_factory() as db:
        user = db.query(User).filter(User.username == username).first()

        assert user is not None, f"User '{username}' was not found"

        return user.id


def test_user_cannot_download_unshared_document(client: TestClient):
    owner = create_user(
        client,
        "unshared_owner",
        "unshared_owner@example.com",
    )
    other_user = create_user(
        client,
        "unshared_other",
        "unshared_other@example.com",
    )

    document = upload_document(client, owner["headers"])

    response = client.get(
        f"/sharing/{document['id']}/download",
        headers=other_user["headers"],
    )

    assert response.status_code == 404


def test_user_cannot_revoke_another_users_share(client: TestClient):
    owner = create_user(
        client,
        "revoke_owner",
        "revoke_owner@example.com",
    )
    recipient = create_user(
        client,
        "revoke_recipient",
        "revoke_recipient@example.com",
    )
    other_user = create_user(
        client,
        "revoke_other",
        "revoke_other@example.com",
    )

    document = upload_document(client, owner["headers"])

    share_response = client.post(
        f"/sharing/{document['id']}",
        headers=owner["headers"],
        json={
            "username": "revoke_recipient",
            "permission": "viewer",
        },
    )

    assert share_response.status_code == 201, share_response.text

    recipient_id = get_user_id(client, "revoke_recipient")

    response = client.delete(
        f"/sharing/{document['id']}/{recipient_id}",
        headers=other_user["headers"],
    )

    assert response.status_code == 403


def test_owner_can_download_own_document(client: TestClient):
    owner = create_user(
        client,
        "own_download",
        "own_download@example.com",
    )

    document = upload_document(client, owner["headers"])

    response = client.get(
        f"/sharing/{document['id']}/download",
        headers=owner["headers"],
    )

    assert response.status_code == 200
    assert response.content == b"Test document content"


def test_invalid_sharing_permission_is_rejected(client: TestClient):
    owner = create_user(
        client,
        "invalid_permission_owner",
        "invalid_permission_owner@example.com",
    )
    recipient = create_user(
        client,
        "invalid_permission_recipient",
        "invalid_permission_recipient@example.com",
    )

    document = upload_document(client, owner["headers"])

    response = client.post(
        f"/sharing/{document['id']}",
        headers=owner["headers"],
        json={
            "username": "invalid_permission_recipient",
            "permission": "admin",
        },
    )

    assert response.status_code == 422, response.text
