from dotenv import load_dotenv
from flask import Flask, jsonify

from app.database import init_db
from app.errors import register_error_handlers
from app.routes import register_routes


def create_app():
    load_dotenv()

    app = Flask(__name__)

    init_db(app)

    from app import models  # noqa: F401 - registers models with Peewee
    from app.models.user import User
    from app.models.link import Link
    from app.models.event import Event
    from app.database import db as _db

    with app.app_context():
        _db.connect(reuse_if_open=True)
        _db.create_tables([User, Link, Event], safe=True)
        _db.close()

    register_routes(app)
    register_error_handlers(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app
