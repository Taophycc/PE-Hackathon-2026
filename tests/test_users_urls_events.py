"""
Tests for /users, /urls, and /events API endpoints.
"""


# ---------------------------------------------------------------------------
# /users
# ---------------------------------------------------------------------------

class TestListUsers:
    def test_empty_db_returns_empty_list(self, client):
        response = client.get("/users")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_returns_created_users(self, client):
        client.post("/users", json={"username": "alice", "email": "alice@example.com"})
        client.post("/users", json={"username": "bob", "email": "bob@example.com"})
        data = client.get("/users").get_json()
        usernames = [u["username"] for u in data]
        assert "alice" in usernames
        assert "bob" in usernames

    def test_pagination_per_page(self, client):
        for i in range(5):
            client.post("/users", json={"username": f"user{i}", "email": f"user{i}@example.com"})
        data = client.get("/users?per_page=3").get_json()
        assert len(data) == 3

    def test_pagination_page_and_per_page(self, client):
        for i in range(5):
            client.post("/users", json={"username": f"puser{i}", "email": f"puser{i}@example.com"})
        page1 = client.get("/users?page=1&per_page=2").get_json()
        page2 = client.get("/users?page=2&per_page=2").get_json()
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0]["id"] != page2[0]["id"]


class TestGetUser:
    def test_get_existing_user(self, client):
        client.post("/users", json={"username": "getme", "email": "getme@example.com"})
        all_users = client.get("/users").get_json()
        user_id = all_users[0]["id"]
        response = client.get(f"/users/{user_id}")
        assert response.status_code == 200
        assert response.get_json()["username"] == "getme"

    def test_get_nonexistent_user_returns_404(self, client):
        response = client.get("/users/99999")
        assert response.status_code == 404
        assert "error" in response.get_json()


class TestCreateUser:
    def test_create_user_returns_201(self, client):
        response = client.post("/users", json={"username": "newuser", "email": "new@example.com"})
        assert response.status_code == 201

    def test_create_user_response_has_expected_fields(self, client):
        response = client.post("/users", json={"username": "fielduser", "email": "field@example.com"})
        data = response.get_json()
        assert "id" in data
        assert data["username"] == "fielduser"
        assert data["email"] == "field@example.com"

    def test_duplicate_username_returns_409(self, client):
        client.post("/users", json={"username": "dupuser", "email": "dup1@example.com"})
        response = client.post("/users", json={"username": "dupuser", "email": "dup2@example.com"})
        assert response.status_code == 409

    def test_missing_username_returns_400(self, client):
        response = client.post("/users", json={"email": "nousername@example.com"})
        assert response.status_code == 400

    def test_missing_email_returns_400(self, client):
        response = client.post("/users", json={"username": "noemail"})
        assert response.status_code == 400

    def test_empty_body_returns_400(self, client):
        response = client.post("/users", json={})
        assert response.status_code == 400


class TestUpdateUser:
    def _create_user(self, client, username="updateme", email="update@example.com"):
        r = client.post("/users", json={"username": username, "email": email})
        return r.get_json()["id"]

    def test_update_username(self, client):
        uid = self._create_user(client)
        response = client.put(f"/users/{uid}", json={"username": "updated"})
        assert response.status_code == 200
        assert response.get_json()["username"] == "updated"

    def test_update_nonexistent_user_returns_404(self, client):
        response = client.put("/users/99999", json={"username": "ghost"})
        assert response.status_code == 404


class TestDeleteUser:
    def test_delete_existing_user_returns_200(self, client):
        r = client.post("/users", json={"username": "deleteme", "email": "deleteme@example.com"})
        uid = r.get_json()["id"]
        response = client.delete(f"/users/{uid}")
        assert response.status_code == 200

    def test_delete_nonexistent_user_returns_404(self, client):
        response = client.delete("/users/99999")
        assert response.status_code == 404

    def test_deleted_user_no_longer_retrievable(self, client):
        r = client.post("/users", json={"username": "gone", "email": "gone@example.com"})
        uid = r.get_json()["id"]
        client.delete(f"/users/{uid}")
        response = client.get(f"/users/{uid}")
        assert response.status_code == 404


class TestBulkLoadUsers:
    def test_bulk_no_file_returns_400(self, client):
        response = client.post("/users/bulk", json={})
        assert response.status_code == 400

    def test_bulk_missing_file_returns_404(self, client):
        response = client.post("/users/bulk", json={"file": "nonexistent_file_xyz.csv"})
        assert response.status_code == 404

    def test_bulk_multipart_upload(self, client):
        import io
        csv_content = b"username,email,created_at\nbulkuser1,bulk1@example.com,\nbulkuser2,bulk2@example.com,\n"
        response = client.post(
            "/users/bulk",
            data={"file": (io.BytesIO(csv_content), "users.csv")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 201
        assert response.get_json()["inserted"] == 2


# ---------------------------------------------------------------------------
# /urls
# ---------------------------------------------------------------------------

class TestListUrls:
    def test_empty_db_returns_empty_list(self, client):
        response = client.get("/urls")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_returns_created_urls(self, client):
        client.post("/urls", json={"original_url": "https://example.com"})
        data = client.get("/urls").get_json()
        assert len(data) >= 1

    def test_filter_by_is_active_true(self, client):
        r = client.post("/urls", json={"original_url": "https://active.com"})
        url_id = r.get_json()["id"]
        client.put(f"/urls/{url_id}", json={"is_active": False})

        active = client.get("/urls?is_active=true").get_json()
        inactive = client.get("/urls?is_active=false").get_json()
        active_ids = [u["id"] for u in active]
        inactive_ids = [u["id"] for u in inactive]
        assert url_id not in active_ids
        assert url_id in inactive_ids

    def test_filter_by_user_id(self, client):
        client.post("/urls", json={"original_url": "https://user1.com", "user_id": 42})
        client.post("/urls", json={"original_url": "https://user2.com", "user_id": 99})
        data = client.get("/urls?user_id=42").get_json()
        assert all(u["user_id"] == 42 for u in data)


class TestGetUrl:
    def test_get_existing_url(self, client):
        r = client.post("/urls", json={"original_url": "https://getme.com"})
        url_id = r.get_json()["id"]
        response = client.get(f"/urls/{url_id}")
        assert response.status_code == 200
        assert response.get_json()["original_url"] == "https://getme.com"

    def test_get_nonexistent_url_returns_404(self, client):
        response = client.get("/urls/99999")
        assert response.status_code == 404


class TestCreateUrl:
    def test_create_url_returns_201(self, client):
        response = client.post("/urls", json={"original_url": "https://example.com"})
        assert response.status_code == 201

    def test_response_includes_short_code(self, client):
        response = client.post("/urls", json={"original_url": "https://example.com"})
        data = response.get_json()
        assert "short_code" in data
        assert len(data["short_code"]) > 0

    def test_create_with_title(self, client):
        response = client.post("/urls", json={"original_url": "https://titled.com", "title": "My Title"})
        assert response.status_code == 201
        assert response.get_json()["title"] == "My Title"

    def test_missing_original_url_returns_400(self, client):
        response = client.post("/urls", json={"title": "no url"})
        assert response.status_code == 400

    def test_invalid_url_scheme_returns_400(self, client):
        response = client.post("/urls", json={"original_url": "ftp://example.com"})
        assert response.status_code == 400

    def test_duplicate_custom_short_code_returns_409(self, client):
        client.post("/urls", json={"original_url": "https://a.com", "short_code": "dupcode"})
        response = client.post("/urls", json={"original_url": "https://b.com", "short_code": "dupcode"})
        assert response.status_code == 409


class TestUpdateUrl:
    def test_update_title(self, client):
        r = client.post("/urls", json={"original_url": "https://updateme.com"})
        url_id = r.get_json()["id"]
        response = client.put(f"/urls/{url_id}", json={"title": "New Title"})
        assert response.status_code == 200
        assert response.get_json()["title"] == "New Title"

    def test_deactivate_url(self, client):
        r = client.post("/urls", json={"original_url": "https://deactivate.com"})
        url_id = r.get_json()["id"]
        response = client.put(f"/urls/{url_id}", json={"is_active": False})
        assert response.status_code == 200
        assert response.get_json()["is_active"] is False

    def test_update_nonexistent_url_returns_404(self, client):
        response = client.put("/urls/99999", json={"title": "ghost"})
        assert response.status_code == 404


class TestDeleteUrl:
    def test_delete_existing_url_returns_200(self, client):
        r = client.post("/urls", json={"original_url": "https://deleteme.com"})
        url_id = r.get_json()["id"]
        response = client.delete(f"/urls/{url_id}")
        assert response.status_code == 200

    def test_delete_nonexistent_url_returns_404(self, client):
        response = client.delete("/urls/99999")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /events
# ---------------------------------------------------------------------------

class TestListEvents:
    def test_empty_db_returns_empty_list(self, client):
        response = client.get("/events")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_returns_created_events(self, client):
        client.post("/events", json={"url_id": 1, "event_type": "click"})
        data = client.get("/events").get_json()
        assert len(data) >= 1

    def test_filter_by_event_type(self, client):
        client.post("/events", json={"url_id": 1, "event_type": "click"})
        client.post("/events", json={"url_id": 1, "event_type": "view"})
        data = client.get("/events?event_type=click").get_json()
        assert all(e["event_type"] == "click" for e in data)

    def test_filter_by_url_id(self, client):
        client.post("/events", json={"url_id": 10, "event_type": "click"})
        client.post("/events", json={"url_id": 20, "event_type": "click"})
        data = client.get("/events?url_id=10").get_json()
        assert all(e["url_id"] == 10 for e in data)

    def test_filter_by_user_id(self, client):
        client.post("/events", json={"url_id": 1, "user_id": 5, "event_type": "click"})
        client.post("/events", json={"url_id": 1, "user_id": 6, "event_type": "click"})
        data = client.get("/events?user_id=5").get_json()
        assert all(e["user_id"] == 5 for e in data)


class TestCreateEvent:
    def test_create_event_returns_201(self, client):
        response = client.post("/events", json={"url_id": 1, "event_type": "click"})
        assert response.status_code == 201

    def test_response_has_expected_fields(self, client):
        response = client.post("/events", json={"url_id": 1, "event_type": "click", "user_id": 2})
        data = response.get_json()
        assert data["event_type"] == "click"
        assert data["url_id"] == 1
        assert data["user_id"] == 2
        assert "timestamp" in data

    def test_create_event_with_dict_details(self, client):
        response = client.post("/events", json={
            "url_id": 1,
            "event_type": "click",
            "details": {"referrer": "https://google.com"}
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data["details"]["referrer"] == "https://google.com"

    def test_missing_url_id_returns_400(self, client):
        response = client.post("/events", json={"event_type": "click"})
        assert response.status_code == 400

    def test_missing_event_type_returns_400(self, client):
        response = client.post("/events", json={"url_id": 1})
        assert response.status_code == 400

    def test_empty_body_returns_400(self, client):
        response = client.post("/events", json={})
        assert response.status_code == 400
