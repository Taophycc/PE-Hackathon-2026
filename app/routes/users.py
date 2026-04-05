import csv
import io
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.models.user import User

users_bp = Blueprint("users", __name__)


def _now():
    return datetime.now(timezone.utc)


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
    if not data:
        return jsonify(error="Missing request body"), 400
    if "username" not in data or "email" not in data:
        return jsonify(error="Missing required fields: username, email"), 400

    try:
        user = User.create(
            username=data["username"].strip(),
            email=data["email"].strip(),
            created_at=_now(),
        )
    except IntegrityError:
        return jsonify(error="Username or email already exists"), 409

    return jsonify(user.to_dict()), 201


@users_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        user = User.get_by_id(user_id)
    except User.DoesNotExist:
        return jsonify(error="Not found"), 404

    data = request.get_json(silent=True) or {}
    if "username" in data:
        user.username = data["username"].strip()
    if "email" in data:
        user.email = data["email"].strip()

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

    return jsonify(inserted=inserted), 201
