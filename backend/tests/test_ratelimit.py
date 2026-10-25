# Public endpoints are rate-limited per IP: the limit answers 429 with
# Retry-After, and other endpoints keep their own budget.

from app import ratelimit


def test_public_list_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(ratelimit, "_hits", ratelimit.defaultdict(ratelimit.deque))
    for _ in range(120):
        assert client.get("/opportunities").status_code == 200
    r = client.get("/opportunities")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert client.get("/health").status_code == 200  # not limited


def test_demo_login_is_rate_limited(client):
    codes = [client.post("/auth/demo").status_code for _ in range(11)]
    assert 429 not in codes[:10] and codes[10] == 429
