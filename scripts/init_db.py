"""Run once to create database tables: uv run python scripts/init_db.py"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.database import db
from app.models.user import User
from app.models.link import Link
from app.models.event import Event

app = create_app()

with app.app_context():
    db.create_tables([User, Link, Event], safe=True)
    print("Tables created: users, urls, events")
