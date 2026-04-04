"""
Model-layer unit tests.

Tests model CRUD operations and constraints directly against the database,
bypassing HTTP. This catches schema-level bugs (unique constraints, NOT NULL)
independently of the route layer.
"""
from datetime import datetime, timezone

import pytest

from app.models.event import Event
from app.models.link import Link
from app.models.user import User


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class TestUserModel:
    def test_create_user(self, app):
        user = User.create(username="alice", email="alice@example.com", created_at=_now())
        assert user.id is not None

    def test_to_dict_contains_expected_keys(self, app):
        user = User.create(username="bob", email="bob@example.com", created_at=_now())
        d = user.to_dict()
        assert d["username"] == "bob"
        assert d["email"] == "bob@example.com"
        assert "id" in d

    def test_duplicate_username_raises(self, app):
        User.create(username="carol", email="carol1@example.com", created_at=_now())
        with pytest.raises(Exception):
            User.create(username="carol", email="carol2@example.com", created_at=_now())

    def test_duplicate_email_raises(self, app):
        User.create(username="dave1", email="shared@example.com", created_at=_now())
        with pytest.raises(Exception):
            User.create(username="dave2", email="shared@example.com", created_at=_now())


# ---------------------------------------------------------------------------
# Link
# ---------------------------------------------------------------------------

class TestLinkModel:
    def test_create_link(self, app):
        link = Link.create(
            short_code="abc001",
            original_url="https://example.com",
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        assert link.id is not None

    def test_to_dict_contains_expected_keys(self, app):
        link = Link.create(
            short_code="abc002",
            original_url="https://example.com",
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        d = link.to_dict()
        assert d["short_code"] == "abc002"
        assert d["original_url"] == "https://example.com"
        assert d["is_active"] is True
        assert "id" in d

    def test_duplicate_short_code_raises(self, app):
        Link.create(
            short_code="dupcode",
            original_url="https://a.com",
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        with pytest.raises(Exception):
            Link.create(
                short_code="dupcode",
                original_url="https://b.com",
                is_active=True,
                created_at=_now(),
                updated_at=_now(),
            )

    def test_is_active_defaults_to_true(self, app):
        link = Link.create(
            short_code="active1",
            original_url="https://example.com",
            created_at=_now(),
            updated_at=_now(),
        )
        assert link.is_active is True

    def test_title_is_optional(self, app):
        link = Link.create(
            short_code="notitle",
            original_url="https://example.com",
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        assert link.title is None

    def test_user_id_is_optional(self, app):
        link = Link.create(
            short_code="nouserid",
            original_url="https://example.com",
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        assert link.user_id is None


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class TestEventModel:
    def test_create_event(self, app):
        event = Event.create(url_id=1, event_type="click", timestamp=_now())
        assert event.id is not None

    def test_to_dict_contains_expected_keys(self, app):
        event = Event.create(
            url_id=1,
            event_type="redirect",
            timestamp=_now(),
            details="user agent: curl",
        )
        d = event.to_dict()
        assert d["event_type"] == "redirect"
        assert d["details"] == "user agent: curl"
        assert "id" in d

    def test_user_id_is_optional(self, app):
        event = Event.create(url_id=1, event_type="view", timestamp=_now())
        assert event.user_id is None

    def test_details_is_optional(self, app):
        event = Event.create(url_id=1, event_type="view", timestamp=_now())
        assert event.details is None
