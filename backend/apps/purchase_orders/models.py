from mongoengine import DateTimeField, DecimalField, DictField, Document, ListField, ReferenceField, StringField

from apps.purchase_orders.domain import ORDER_STATUS_CHOICES
from apps.suppliers.models import Supplier


class PurchaseOrder(Document):
    meta = {"collection": "purchase_orders", "ordering": ["-created_at"]}

    supplier = ReferenceField(Supplier, required=True)
    items = ListField(DictField(), required=True)
    total_amount = DecimalField(required=True, precision=2, min_value=0)
    status = StringField(default="pending", choices=ORDER_STATUS_CHOICES)
    history = ListField(DictField(), default=list)
    created_at = DateTimeField()
    updated_at = DateTimeField()
    received_at = DateTimeField(null=True)
    cancelled_at = DateTimeField(null=True)
