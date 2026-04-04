from peewee import CharField, DateTimeField
from playhouse.shortcuts import model_to_dict

from app.database import BaseModel


class User(BaseModel):
    username = CharField(unique=True, max_length=100)
    email = CharField(unique=True, max_length=255)
    created_at = DateTimeField()

    class Meta:
        table_name = "users"

    def to_dict(self):
        return model_to_dict(self)
