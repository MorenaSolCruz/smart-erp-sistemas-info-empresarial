from mongoengine import DateTimeField, DecimalField, Document, IntField, StringField

from apps.products.querysets import product_queryset


class Product(Document):
    meta = {"collection": "products", "ordering": ["name"]}

    name = StringField(required=True, unique=True, max_length=120)
    description = StringField(default="")
    category = StringField(default="")
    stock = IntField(required=True, min_value=0)
    minimum_stock = IntField(default=0, min_value=0)
    unit_price = DecimalField(required=True, precision=2, min_value=0)
    expiration_date = DateTimeField(null=True)
    created_at = DateTimeField()
    updated_at = DateTimeField()

    @classmethod
    def objects_safe(cls):
        return product_queryset(cls)

