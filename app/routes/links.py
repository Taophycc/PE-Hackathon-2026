from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect, request

from app.models.link import Link, generate_short_code

links_bp = Blueprint("links", __name__)


@links_bp.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify(error="Missing 'url' in request body"), 400

    original_url = data["url"].strip()
    if not original_url:
        return jsonify(error="URL cannot be empty"), 400
    if not original_url.startswith(("http://", "https://")):
        return jsonify(error="URL must start with http:// or https://"), 400

    custom_code = data.get("short_code", "").strip()
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

    now = datetime.now(timezone.utc)
    link = Link.create(
        short_code=short_code,
        original_url=original_url,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    return jsonify(link.to_dict()), 201


@links_bp.route("/<short_code>", methods=["GET"])
def redirect_link(short_code):
    try:
        link = Link.get(Link.short_code == short_code)
    except Link.DoesNotExist:
        return jsonify(error="Short link not found"), 404

    if not link.is_active:
        return jsonify(error="This link has been deactivated"), 410

    return redirect(link.original_url, code=302)


@links_bp.route("/links", methods=["GET"])
def list_links():
    links = Link.select().where(Link.is_active == True)  # noqa: E712
    return jsonify([l.to_dict() for l in links]), 200


@links_bp.route("/links/<short_code>", methods=["DELETE"])
def deactivate_link(short_code):
    try:
        link = Link.get(Link.short_code == short_code)
    except Link.DoesNotExist:
        return jsonify(error="Short link not found"), 404

    link.is_active = False
    link.updated_at = datetime.now(timezone.utc)
    link.save()
    return jsonify(message="Link deactivated"), 200
