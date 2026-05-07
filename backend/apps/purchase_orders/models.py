from mongoengine import DateTimeField, DecimalField, DictField, Document, ListField, ReferenceField, StringField

from apps.suppliers.models import Supplier


class PurchaseOrder(Document):
    meta = {"collection": "purchase_orders", "ordering": ["-created_at"]}

    supplier = ReferenceField(Supplier, required=True)
    items = ListField(DictField(), required=True)
    total_amount = DecimalField(required=True, precision=2, min_value=0)
    status = StringField(default="received")
    created_at = DateTimeField()

