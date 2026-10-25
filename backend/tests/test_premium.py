# Premium early access: reserve, change plan without losing your place,
# queue positions, cancel, demo read-only. Nothing is ever charged.

import uuid

from conftest import bearer, make_token


def status(client, headers):
    response = client.get("/me/premium", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_everyone_is_on_free_and_payments_are_not_live(client, auth):
    s = status(client, auth)
    assert s["current_plan"] == "free" and s["payments_live"] is False
    assert s["reservation"] is None and s["reservations_total"] == 0


def test_reserve_change_and_cancel(client, auth):
    r = client.put(
        "/me/premium/reservation",
        json={"plan": "premium", "billing": "yearly", "payment_method": "edahabia"},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    res = r.json()["reservation"]
    assert (
        res["plan"] == "premium"
        and res["billing"] == "yearly"
        and res["payment_method"] == "edahabia"
    )
    assert res["position"] == 1

    # Someone else reserves after: they are #2, we stay #1 after changing our plan.
    other = bearer(make_token(str(uuid.uuid4())))
    assert (
        client.put("/me/premium/reservation", json={}, headers=other).json()["reservation"][
            "position"
        ]
        == 2
    )
    changed = client.put("/me/premium/reservation", json={"plan": "clubs"}, headers=auth).json()
    assert changed["reservation"]["plan"] == "clubs" and changed["reservation"]["position"] == 1
    assert changed["reservations_total"] == 2

    assert client.delete("/me/premium/reservation", headers=auth).json()["reservation"] is None
    assert status(client, other)["reservation"]["position"] == 1
    assert client.delete("/me/premium/reservation", headers=auth).status_code == 404


def test_validation_and_demo(client, auth):
    assert (
        client.put("/me/premium/reservation", json={"plan": "gold"}, headers=auth).status_code
        == 422
    )
    assert (
        client.put(
            "/me/premium/reservation", json={"payment_method": "visa"}, headers=auth
        ).status_code
        == 422
    )
    demo = bearer(make_token(str(uuid.uuid4()), demo=True))
    assert status(client, demo)["current_plan"] == "free"
    assert client.put("/me/premium/reservation", json={}, headers=demo).status_code == 403
