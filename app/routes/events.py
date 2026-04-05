import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.models.event import Event

events_bp = Blueprint("events", __name__)


def _now():
    return datetime.now(timezone.utc)


@events_bp.route("/events", methods=["GET"])
def list_events():
    query = Event.select().order_by(Event.id)

    url_id = request.args.get("url_id", type=int)
    user_id = request.args.get("user_id", type=int)
    event_type = request.args.get("event_type")

    if url_id is not None:
        query = query.where(Event.url_id == url_id)
    if user_id is not None:
        query = query.where(Event.user_id == user_id)
    if event_type:
        query = query.where(Event.event_type == event_type)

    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)
    if page and per_page:
        query = query.offset((page - 1) * per_page).limit(per_page)
    elif per_page:
        query = query.limit(per_page)

    return jsonify([_event_dict(e) for e in query]), 200


@events_bp.route("/events", methods=["POST"])
def create_event():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object"), 400
    if "url_id" not in data or "event_type" not in data:
        return jsonify(error="Missing required fields: url_id, event_type"), 400

    try:
        url_id = int(data["url_id"])
    except (TypeError, ValueError):
        return jsonify(error="url_id must be an integer"), 400

    event_type = str(data["event_type"]).strip()
    if not event_type:
        return jsonify(error="event_type cannot be empty"), 400

    details = data.get("details")
    if details is not None:
        if isinstance(details, str):
            try:
                json.loads(details)
            except (ValueError, TypeError):
                return jsonify(error="details must be a valid JSON object"), 400
        elif not isinstance(details, dict):
            return jsonify(error="details must be a JSON object"), 400
        else:
            details = json.dumps(details)

    event = Event.create(
        url_id=url_id,
        user_id=data.get("user_id"),
        event_type=event_type,
        timestamp=_now(),
        details=details,
    )
    return jsonify(_event_dict(event)), 201


def _event_dict(event):
    d = {
        "id": event.id,
        "url_id": event.url_id,
        "user_id": event.user_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "details": None,
    }
    if event.details:
        try:
            d["details"] = json.loads(event.details)
        except (ValueError, TypeError):
            d["details"] = event.details
    return d
