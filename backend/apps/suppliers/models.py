from mongoengine import DateTimeField, Document, ListField, StringField


class Supplier(Document):
    meta = {"collection": "suppliers", "ordering": ["name"]}

    name = StringField(required=True, unique=True, max_length=120)
    contact_email = StringField(default="")
    tax_id = StringField(default="")
    phone = StringField(default="")
    address = StringField(default="")
    products_supplied = ListField(StringField(), default=list)
    created_at = DateTimeField()
    updated_at = DateTimeField()

