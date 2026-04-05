"""
Silver Tier — Error Handling.

Verifies that the app returns clean, structured JSON errors instead of
HTML stack traces. A user should see {"error": "..."}, never a Python
traceback.
"""
from unittest.mock import patch


def test_404_unknown_route_returns_json(client):
    """Any unregistered path should yield a JSON 404, not an HTML page."""
    response = client.get("/this/route/does/not/exist")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert data["error"] == "Not found"


def test_405_wrong_method_returns_json(client):
    """/health only supports GET; POST should return a JSON 405."""
    response = client.post("/health")
    assert response.status_code == 405
    data = response.get_json()
    assert "error" in data
    assert data["error"] == "Method not allowed"


def test_500_internal_error_returns_json(client, app):
    """Unhandled exceptions must surface as a JSON 500, never a traceback.

    TESTING=True makes Flask re-raise exceptions by default (useful for
    debugging tests). We explicitly disable PROPAGATE_EXCEPTIONS for this
    test so Flask routes the exception through the registered 500 handler,
    which is exactly the production behaviour we want to verify.
    """
    app.config["PROPAGATE_EXCEPTIONS"] = False
    with patch("app.routes.links.Link.select", side_effect=RuntimeError("db exploded")):
        response = client.get("/links")
    assert response.status_code == 500
    data = response.get_json()
    assert "error" in data
    assert data["error"] == "Internal server error"
