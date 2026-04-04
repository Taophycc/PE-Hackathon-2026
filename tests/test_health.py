"""
Bronze Tier — Pulse Check.

Tests the /health endpoint that load balancers use to determine whether
the app is alive. If this returns anything other than 200, traffic stops.
"""


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json_status_ok(client):
    response = client.get("/health")
    data = response.get_json()
    assert data == {"status": "ok"}


def test_health_content_type_is_json(client):
    response = client.get("/health")
    assert response.content_type == "application/json"
