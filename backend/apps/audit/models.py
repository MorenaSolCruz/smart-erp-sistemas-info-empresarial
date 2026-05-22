from mongoengine import DateTimeField, DictField, Document, ListField, StringField


class AuditEntry(Document):
    meta = {"collection": "audit_entries", "ordering": ["-created_at"]}

    action = StringField(required=True)
    entity_type = StringField(default="")
    entity_name = StringField(default="")
    entity_id = StringField(default="")
    summary = StringField(default="")
    status = StringField(default="success")
    related_entities = ListField(DictField(), default=list)
    payload = DictField(default=dict)
    created_at = DateTimeField(required=True)

