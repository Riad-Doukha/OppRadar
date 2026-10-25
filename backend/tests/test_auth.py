# JWT verification + the demo/read-only rule.

from conftest import bearer, make_token


def test_health_is_public(client):
    assert client.get("/health").json()["status"] == "ok"


def test_me_requires_a_token(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_rejects_token_signed_with_another_secret(client):
    token = make_token(secret="someone-elses-secret-also-32-bytes!!")
    assert client.get("/me", headers=bearer(token)).status_code == 401


def test_rejects_expired_token(client):
    assert client.get("/me", headers=bearer(make_token(expires_in=-10))).status_code == 401


def test_rejects_garbage_token(client):
    assert client.get("/me", headers=bearer("not-a-jwt")).status_code == 401


def test_first_get_creates_profile_from_signup_metadata(client, auth, user_id):
    me = client.get("/me", headers=auth).json()
    assert me["user_id"] == user_id
    assert me["full_name"] == "Amine Benali"
    assert me["email"] == "amine.benali@ensia.edu.dz"
    assert me["onboarding"]["step"] == 1
    assert me["notifications"]["threshold"] == 70
    assert "about.birth_year" in me["onboarding"]["missing"]


def test_demo_user_can_read_but_not_write(client):
    headers = bearer(make_token(demo=True))
    assert client.get("/me", headers=headers).status_code == 200
    assert client.get("/me", headers=headers).json()["is_demo"] is True
    response = client.patch("/me/onboarding/about", json={"wilaya": "Oran"}, headers=headers)
    assert response.status_code == 403
    assert "demo" in response.json()["detail"]


def test_demo_login_unavailable_without_configuration(client):
    assert client.post("/auth/demo").status_code == 503
