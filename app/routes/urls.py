from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.cache import cache_delete
from app.models.link import Link, generate_short_code

urls_bp = Blueprint("urls", __name__)


def _now():
    return datetime.now(timezone.utc)


@urls_bp.route("/urls", methods=["GET"])
def list_urls():
    query = Link.select().order_by(Link.id)

    user_id = request.args.get("user_id", type=int)
    is_active = request.args.get("is_active")

    if user_id is not None:
        query = query.where(Link.user_id == user_id)
    if is_active is not None:
        active = is_active.lower() in ("true", "1", "yes")
        query = query.where(Link.is_active == active)

    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)
    if page and per_page:
        query = query.offset((page - 1) * per_page).limit(per_page)
    elif per_page:
        query = query.limit(per_page)

    return jsonify([l.to_dict() for l in query]), 200


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    try:
        link = Link.get_by_id(url_id)
    except Link.DoesNotExist:
        return jsonify(error="Not found"), 404
    return jsonify(link.to_dict()), 200


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    data = request.get_json(silent=True)
    if not data or "original_url" not in data:
        return jsonify(error="Missing required field: original_url"), 400

    original_url = data["original_url"].strip()
    if not original_url.startswith(("http://", "https://")):
        return jsonify(error="URL must start with http:// or https://"), 400

    custom_code = data.get("short_code", "").strip() if data.get("short_code") else ""
    if custom_code:
        if Link.select().where(Link.short_code == custom_code).exists():
            return jsonify(error="Short code already taken"), 409
        short_code = custom_code
    else:
        for _ in range(10):
            short_code = generate_short_code()
            if not Link.select().where(Link.short_code == short_code).exists():
                break
        else:
            return jsonify(error="Could not generate unique short code"), 500

    now = _now()
    link = Link.create(
        short_code=short_code,
        original_url=original_url,
        title=data.get("title", "").strip() or None,
        user_id=data.get("user_id"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    return jsonify(link.to_dict()), 201


@urls_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    try:
        link = Link.get_by_id(url_id)
    except Link.DoesNotExist:
        return jsonify(error="Not found"), 404

    data = request.get_json(silent=True) or {}
    if "title" in data:
        link.title = data["title"]
    if "original_url" in data:
        link.original_url = data["original_url"]
    if "is_active" in data:
        link.is_active = bool(data["is_active"])
        if not link.is_active:
            cache_delete(f"link:{link.short_code}")
    if "short_code" in data:
        link.short_code = data["short_code"]

    link.updated_at = _now()
    link.save()
    return jsonify(link.to_dict()), 200


@urls_bp.route("/urls/<int:url_id>", methods=["DELETE"])
def delete_url(url_id):
    try:
        link = Link.get_by_id(url_id)
    except Link.DoesNotExist:
        return jsonify(error="Not found"), 404

    cache_delete(f"link:{link.short_code}")
    link.delete_instance()
    return jsonify(message="URL deleted"), 200
