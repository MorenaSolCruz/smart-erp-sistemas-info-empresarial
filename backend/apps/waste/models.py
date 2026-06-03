from mongoengine import DateTimeField, DecimalField, Document, IntField, ReferenceField, StringField

from apps.products.models import Product


class WasteRecord(Document):
    # Registro de merma/desecho: enlaza producto, cantidad, motivo y perdida economica.
    meta = {"collection": "waste_records", "ordering": ["-date"]}

    product = ReferenceField(Product, required=True)  # Producto afectado por la merma.
    quantity = IntField(required=True, min_value=1)  # Unidades descontadas del inventario.
    reason = StringField(
        required=True,
        choices=["caducidad", "producto dañado", "producto daÃ±ado", "ajuste manual", "deterioro", "obsolescencia"],
    )  # Motivo para estadisticas y analisis de perdidas.
    date = DateTimeField()  # Fecha de registro del desecho.
    economic_loss = DecimalField(required=True, precision=2, min_value=0)  # quantity * precio unitario.
