def register_user(client, phone_number="0241234567", email="user@example.com"):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "phone_number": phone_number,
            "full_name": "Auth Test User",
            "password": "Password1",
            "wants_avok_account": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def login_user(client, phone_number="0241234567", password="Password1"):
    response = client.post(
        "/api/v1/auth/login",
        json={"phone_number": phone_number, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_refresh_rotates_tokens_and_preserves_access(client):
    register_user(client, phone_number="0241234567", email="refresh@example.com")
    login_payload = login_user(client, phone_number="0241234567")

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )

    assert refresh_response.status_code == 200, refresh_response.text
    refreshed = refresh_response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]
    assert refreshed["refresh_token"] != login_payload["refresh_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["phone_number"] == "0241234567"

    reused_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert reused_refresh.status_code == 401


def test_logout_revokes_access_and_refresh_tokens(client):
    register_user(client, phone_number="0247654321", email="logout@example.com")
    login_payload = login_user(client, phone_number="0247654321")

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": login_payload["refresh_token"]},
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert logout_response.status_code == 200, logout_response.text

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert me_response.status_code == 401

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_payload["refresh_token"]},
    )
    assert refresh_response.status_code == 401
