from mongoengine import DateTimeField, DecimalField, Document, IntField, ReferenceField, StringField

from apps.products.models import Product


class WasteRecord(Document):
    meta = {"collection": "waste_records", "ordering": ["-date"]}

    product = ReferenceField(Product, required=True)
    quantity = IntField(required=True, min_value=1)
    reason = StringField(required=True, choices=["caducidad", "producto dañado", "ajuste manual"])
    date = DateTimeField()
    economic_loss = DecimalField(required=True, precision=2, min_value=0)

