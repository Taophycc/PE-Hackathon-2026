"""Run once to create database tables: uv run scripts/init_db.py"""
from dotenv import load_dotenv

load_dotenv()

from app.database import db  # noqa: E402
from app.models.link import Link  # noqa: E402
from peewee import PostgresqlDatabase  # noqa: E402
import os  # noqa: E402

database = PostgresqlDatabase(
    os.environ.get("DATABASE_NAME", "hackathon_db"),
    host=os.environ.get("DATABASE_HOST", "localhost"),
    port=int(os.environ.get("DATABASE_PORT", 5432)),
    user=os.environ.get("DATABASE_USER", "postgres"),
    password=os.environ.get("DATABASE_PASSWORD", "postgres"),
)
db.initialize(database)

db.connect()
db.create_tables([Link], safe=True)
db.close()

print("Tables created successfully.")
