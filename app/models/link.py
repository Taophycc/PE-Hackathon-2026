import random
import string

from peewee import BooleanField, CharField, DateTimeField, IntegerField
from playhouse.shortcuts import model_to_dict

from app.database import BaseModel


def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


class Link(BaseModel):
    user_id = IntegerField(null=True)
    short_code = CharField(unique=True, max_length=20)
    original_url = CharField(max_length=2048)
    title = CharField(max_length=255, null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField()
    updated_at = DateTimeField()

    class Meta:
        table_name = "urls"

    def to_dict(self):
        return model_to_dict(self)
