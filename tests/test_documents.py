def create_user(client, username, email):
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "SecureTest123!",
        },
    )

    assert response.status_code == 201

    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "SecureTest123!",
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


def upload_test_document(client, headers, filename="test.pdf"):
    return client.post(
        "/documents/upload",
        headers=headers,
        files={
            "file": (
                filename,
                b"%PDF-1.4 test document",
                "application/pdf",
            )
        },
    )


def test_upload_document(client):
    headers = create_user(
        client,
        "uploaduser",
        "uploaduser@example.com",
    )

    response = upload_test_document(client, headers)

    assert response.status_code == 201
    assert response.json()["original_filename"] == "test.pdf"
    assert response.json()["owner_id"] > 0


def test_list_documents(client):
    headers = create_user(
        client,
        "listuser",
        "listuser@example.com",
    )

    upload_test_document(client, headers)

    response = client.get("/documents/", headers=headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1


def test_download_document(client):
    headers = create_user(
        client,
        "downloaduser",
        "downloaduser@example.com",
    )

    upload_response = upload_test_document(client, headers)
    document_id = upload_response.json()["id"]

    response = client.get(
        f"/documents/{document_id}/download",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 test document"


def test_delete_document(client):
    headers = create_user(
        client,
        "deleteuser",
        "deleteuser@example.com",
    )

    upload_response = upload_test_document(client, headers)
    document_id = upload_response.json()["id"]

    response = client.delete(
        f"/documents/{document_id}",
        headers=headers,
    )

    assert response.status_code == 204

    response = client.get(
        f"/documents/{document_id}",
        headers=headers,
    )

    assert response.status_code == 404


def test_user_cannot_access_another_users_document(client):
    first_user_headers = create_user(
        client,
        "firstuser",
        "firstuser@example.com",
    )

    second_user_headers = create_user(
        client,
        "seconduser",
        "seconduser@example.com",
    )

    upload_response = upload_test_document(
        client,
        first_user_headers,
    )

    document_id = upload_response.json()["id"]

    response = client.get(
        f"/documents/{document_id}",
        headers=second_user_headers,
    )

    assert response.status_code == 404


def test_upload_rejects_unsupported_file(client):
    headers = create_user(
        client,
        "filetypeuser",
        "filetypeuser@example.com",
    )

    response = client.post(
        "/documents/upload",
        headers=headers,
        files={
            "file": (
                "malware.exe",
                b"test content",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 415


def test_upload_requires_authentication(client):
    response = upload_test_document(client, {})

    assert response.status_code == 401


def test_upload_rejects_oversized_file(client):
    headers = create_user(
        client,
        "oversizeduser",
        "oversizeduser@example.com",
    )

    response = client.post(
        "/documents/upload",
        headers=headers,
        files={
            "file": (
                "large.pdf",
                b"%PDF-1.4 " + b"A" * (10 * 1024 * 1024 + 1),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413


def test_upload_rejects_mismatched_file_content(client):
    headers = create_user(
        client,
        "mismatchuser",
        "mismatchuser@example.com",
    )

    response = client.post(
        "/documents/upload",
        headers=headers,
        files={
            "file": (
                "fake.pdf",
                b"This is plain text, not a PDF file",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 415


def test_upload_rejects_empty_file(client):
    headers = create_user(
        client,
        "emptyfileuser",
        "emptyfileuser@example.com",
    )

    response = client.post(
        "/documents/upload",
        headers=headers,
        files={
            "file": (
                "empty.pdf",
                b"",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
