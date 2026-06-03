from mongoengine import DateTimeField, DecimalField, DictField, Document, ListField, ReferenceField, StringField

from apps.purchase_orders.domain import ORDER_STATUS_CHOICES
from apps.suppliers.models import Supplier


class PurchaseOrder(Document):
    # Pedido a proveedor: guarda proveedor, lineas, total, estado e historial
    # para poder recibir, cancelar y auditar cambios.
    meta = {"collection": "purchase_orders", "ordering": ["-created_at"]}

    supplier = ReferenceField(Supplier, required=True)  # Proveedor al que se solicita la mercancia.
    items = ListField(DictField(), required=True)  # Lineas con producto, cantidades, precios y estado por linea.
    total_amount = DecimalField(required=True, precision=2, min_value=0)  # Suma calculada de todas las lineas.
    status = StringField(default="pending", choices=ORDER_STATUS_CHOICES)  # Estado global derivado de las lineas.
    history = ListField(DictField(), default=list)  # Eventos para auditar creacion, recepcion y cancelacion.
    created_at = DateTimeField()  # Fecha de creacion del pedido.
    updated_at = DateTimeField()  # Fecha de ultimo cambio.
    received_at = DateTimeField(null=True)  # Fecha cuando se recibe por completo.
    cancelled_at = DateTimeField(null=True)  # Fecha cuando se cancela/cierra.
