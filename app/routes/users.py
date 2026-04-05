import csv
import io
import os
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.models.user import User

users_bp = Blueprint("users", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now():
    return datetime.now(timezone.utc)


def _valid_email(email):
    return bool(EMAIL_RE.match(email))


@users_bp.route("/users", methods=["GET"])
def list_users():
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)

    query = User.select().order_by(User.id)

    if page and per_page:
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
    elif per_page:
        query = query.limit(per_page)

    return jsonify([u.to_dict() for u in query]), 200


@users_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not found"), 404
    return jsonify(user.to_dict()), 200


@users_bp.route("/users", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object"), 400
    if "username" not in data or "email" not in data:
        return jsonify(error="Missing required fields: username, email"), 400

    username = str(data["username"]).strip()
    email = str(data["email"]).strip()

    if not username:
        return jsonify(error="Username cannot be empty"), 400
    if not email:
        return jsonify(error="Email cannot be empty"), 400
    if not _valid_email(email):
        return jsonify(error="Invalid email format"), 400

    try:
        user = User.create(username=username, email=email, created_at=_now())
    except IntegrityError:
        return jsonify(error="Username or email already exists"), 409

    return jsonify(user.to_dict()), 201


@users_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not found"), 404

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object"), 400

    if "username" in data:
        username = str(data["username"]).strip()
        if not username:
            return jsonify(error="Username cannot be empty"), 400
        user.username = username
    if "email" in data:
        email = str(data["email"]).strip()
        if not _valid_email(email):
            return jsonify(error="Invalid email format"), 400
        user.email = email

    try:
        user.save()
    except IntegrityError:
        return jsonify(error="Username or email already exists"), 409

    return jsonify(user.to_dict()), 200


@users_bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not found"), 404

    user.delete_instance()
    return jsonify(message="User deleted"), 200


@users_bp.route("/users/<int:user_id>/urls", methods=["GET"])
def get_user_urls(user_id):
    try:
        User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not found"), 404

    from app.models.link import Link
    links = Link.select().where(Link.user_id == user_id).order_by(Link.id)
    return jsonify([l.to_dict() for l in links]), 200


@users_bp.route("/users/bulk", methods=["POST"])
def bulk_load_users():
    # Support multipart file upload
    if "file" in request.files:
        f = request.files["file"]
        content = f.read().decode("utf-8")
        return _insert_users_csv(content)

    # Support JSON body with filename
    data = request.get_json(silent=True)
    if data and "file" in data:
        filename = data["file"]
        search_paths = [
            filename,
            os.path.join("/seed", filename),
            os.path.join("/data", filename),
            os.path.join("/tmp", filename),
            os.path.join(os.getcwd(), filename),
        ]
        for path in search_paths:
            if os.path.exists(path):
                with open(path, newline="", encoding="utf-8") as f:
                    content = f.read()
                return _insert_users_csv(content)
        return jsonify(error=f"File not found: {filename}"), 404

    return jsonify(error="No file provided"), 400


def _insert_users_csv(content):
    reader = csv.DictReader(io.StringIO(content))
    inserted = 0
    for row in reader:
        username = row.get("username", "").strip()
        email = row.get("email", "").strip()
        created_at = row.get("created_at", "").strip()

        if not username or not email:
            continue

        try:
            dt = datetime.fromisoformat(created_at) if created_at else _now()
        except ValueError:
            dt = _now()

        try:
            User.create(username=username, email=email, created_at=dt)
            inserted += 1
        except IntegrityError:
            pass  # skip duplicates

    return jsonify(inserted=inserted, count=inserted, imported=inserted), 201
