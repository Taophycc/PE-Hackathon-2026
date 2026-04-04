import random
import string

from peewee import BooleanField, CharField, DateTimeField
from playhouse.shortcuts import model_to_dict

from app.database import BaseModel


def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


class Link(BaseModel):
    short_code = CharField(unique=True, max_length=20)
    original_url = CharField(max_length=2048)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(constraints=[])

    class Meta:
        table_name = "links"

    def to_dict(self):
        return model_to_dict(self)
