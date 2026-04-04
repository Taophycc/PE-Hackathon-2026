from peewee import CharField, DateTimeField, IntegerField, TextField
from playhouse.shortcuts import model_to_dict

from app.database import BaseModel


class Event(BaseModel):
    url_id = IntegerField()
    user_id = IntegerField(null=True)
    event_type = CharField(max_length=50)
    timestamp = DateTimeField()
    details = TextField(null=True)

    class Meta:
        table_name = "events"

    def to_dict(self):
        return model_to_dict(self)
