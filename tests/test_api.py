"""
Silver / Gold Tier — Integration Tests.

Tests hit the real API endpoints. After mutating requests (POST, DELETE)
we query the database directly to prove the data landed correctly.
This is the distinction between unit and integration tests:
unit = engine works; integration = car actually drives.
"""
from datetime import datetime, timezone

from app.database import db
from app.models.link import Link


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _connect_db():
    """Re-open the DB connection after a request closes it."""
    db.connect(reuse_if_open=True)


def _close_db():
    if not db.is_closed():
        db.close()


# ---------------------------------------------------------------------------
# POST /shorten
# ---------------------------------------------------------------------------

class TestShorten:
    def test_valid_https_url_returns_201(self, client):
        response = client.post("/shorten", json={"url": "https://example.com"})
        assert response.status_code == 201

    def test_valid_http_url_returns_201(self, client):
        response = client.post("/shorten", json={"url": "http://example.com"})
        assert response.status_code == 201

    def test_response_body_contains_expected_fields(self, client):
        response = client.post("/shorten", json={"url": "https://example.com"})
        data = response.get_json()
        assert "short_code" in data
        assert "original_url" in data
        assert data["original_url"] == "https://example.com"
        assert data["is_active"] is True

    def test_shorten_stores_link_in_database(self, client):
        """Integration check: POST /shorten → verify row exists in DB."""
        response = client.post("/shorten", json={"url": "https://stored.com"})
        assert response.status_code == 201
        short_code = response.get_json()["short_code"]

        _connect_db()
        try:
            link = Link.get(Link.short_code == short_code)
            assert link.original_url == "https://stored.com"
            assert link.is_active is True
            assert link.created_at is not None
            assert link.updated_at is not None
        finally:
            _close_db()

    def test_missing_url_key_returns_400(self, client):
        response = client.post("/shorten", json={"foo": "bar"})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_empty_json_body_returns_400(self, client):
        response = client.post("/shorten", json={})
        assert response.status_code == 400

    def test_no_content_type_returns_400(self, client):
        """get_json(silent=True) returns None without application/json header."""
        response = client.post("/shorten", data='{"url":"https://example.com"}')
        assert response.status_code == 400

    def test_empty_url_string_returns_400(self, client):
        response = client.post("/shorten", json={"url": ""})
        assert response.status_code == 400
        assert response.get_json()["error"] == "URL cannot be empty"

    def test_whitespace_only_url_returns_400(self, client):
        response = client.post("/shorten", json={"url": "   "})
        assert response.status_code == 400
        assert response.get_json()["error"] == "URL cannot be empty"

    def test_url_without_scheme_returns_400(self, client):
        response = client.post("/shorten", json={"url": "example.com"})
        assert response.status_code == 400
        assert "http" in response.get_json()["error"].lower()

    def test_ftp_url_is_rejected(self, client):
        response = client.post("/shorten", json={"url": "ftp://example.com"})
        assert response.status_code == 400

    def test_custom_short_code_is_used(self, client):
        response = client.post(
            "/shorten", json={"url": "https://example.com", "short_code": "mycode"}
        )
        assert response.status_code == 201
        assert response.get_json()["short_code"] == "mycode"

    def test_duplicate_custom_code_returns_409(self, client):
        client.post("/shorten", json={"url": "https://a.com", "short_code": "dup"})
        response = client.post(
            "/shorten", json={"url": "https://b.com", "short_code": "dup"}
        )
        assert response.status_code == 409
        assert response.get_json()["error"] == "Short code already taken"

    def test_whitespace_custom_code_falls_back_to_generated(self, client):
        """A blank short_code should be treated as no custom code."""
        response = client.post(
            "/shorten", json={"url": "https://example.com", "short_code": "   "}
        )
        assert response.status_code == 201
        # The returned code should not be blank
        assert response.get_json()["short_code"].strip() != ""


# ---------------------------------------------------------------------------
# GET /<short_code>  — redirect
# ---------------------------------------------------------------------------

class TestRedirect:
    def test_active_link_redirects_302(self, client):
        client.post("/shorten", json={"url": "https://example.com", "short_code": "redir1"})
        response = client.get("/redir1")
        assert response.status_code == 302

    def test_redirect_location_matches_original_url(self, client):
        client.post(
            "/shorten",
            json={"url": "https://redirect-target.com", "short_code": "redir2"},
        )
        response = client.get("/redir2")
        assert "redirect-target.com" in response.headers["Location"]

    def test_nonexistent_code_returns_404(self, client):
        response = client.get("/totallymadeupcode999")
        assert response.status_code == 404
        assert response.get_json()["error"] == "Short link not found"

    def test_inactive_link_returns_410(self, client):
        """A deactivated link must return 410 Gone, not redirect."""
        client.post("/shorten", json={"url": "https://gone.com", "short_code": "gone1"})
        client.delete("/links/gone1")
        response = client.get("/gone1")
        assert response.status_code == 410
        assert response.get_json()["error"] == "This link has been deactivated"

    def test_links_static_route_not_captured_as_short_code(self, client):
        """Flask must resolve /links as the list route, not as a short_code lookup."""
        response = client.get("/links")
        assert response.status_code == 200
        assert isinstance(response.get_json(), list)


# ---------------------------------------------------------------------------
# GET /links
# ---------------------------------------------------------------------------

class TestListLinks:
    def test_empty_db_returns_empty_list(self, client):
        response = client.get("/links")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_returns_only_active_links(self, client):
        client.post("/shorten", json={"url": "https://a.com", "short_code": "active1"})
        client.post("/shorten", json={"url": "https://b.com", "short_code": "inactive1"})
        client.delete("/links/inactive1")

        data = client.get("/links").get_json()
        codes = [l["short_code"] for l in data]
        assert "active1" in codes
        assert "inactive1" not in codes

    def test_all_inactive_returns_empty_list(self, client):
        client.post("/shorten", json={"url": "https://a.com", "short_code": "del1"})
        client.post("/shorten", json={"url": "https://b.com", "short_code": "del2"})
        client.delete("/links/del1")
        client.delete("/links/del2")

        response = client.get("/links")
        assert response.get_json() == []

    def test_response_is_a_list(self, client):
        response = client.get("/links")
        assert isinstance(response.get_json(), list)


# ---------------------------------------------------------------------------
# DELETE /links/<short_code>
# ---------------------------------------------------------------------------

class TestDeactivate:
    def test_deactivate_existing_link_returns_200(self, client):
        client.post("/shorten", json={"url": "https://example.com", "short_code": "tokill"})
        response = client.delete("/links/tokill")
        assert response.status_code == 200
        assert response.get_json()["message"] == "Link deactivated"

    def test_deactivate_sets_is_active_false_in_db(self, client):
        """Integration check: DELETE /links/<code> → verify is_active=False in DB."""
        client.post("/shorten", json={"url": "https://example.com", "short_code": "dbcheck"})
        client.delete("/links/dbcheck")

        _connect_db()
        try:
            link = Link.get(Link.short_code == "dbcheck")
            assert link.is_active is False
            assert link.updated_at is not None
        finally:
            _close_db()

    def test_deactivate_nonexistent_link_returns_404(self, client):
        response = client.delete("/links/doesnotexist")
        assert response.status_code == 404
        assert response.get_json()["error"] == "Short link not found"

    def test_double_deactivate_is_idempotent(self, client):
        """
        Known behaviour: deactivating an already-inactive link returns 200
        (not 404), because the route finds the row regardless of is_active
        status. This test documents and asserts that behaviour explicitly.
        """
        client.post("/shorten", json={"url": "https://example.com", "short_code": "idem"})
        first = client.delete("/links/idem")
        second = client.delete("/links/idem")
        assert first.status_code == 200
        assert second.status_code == 200
