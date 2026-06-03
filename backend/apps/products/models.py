from mongoengine import DateTimeField, DecimalField, Document, IntField, StringField

from apps.products.querysets import product_queryset


class Product(Document):
    # Producto de inventario: guarda los datos base que despues usan pedidos,
    # desechos, estadisticas y el agente conversacional.
    meta = {"collection": "products", "ordering": ["name"]}

    name = StringField(required=True, unique=True, max_length=120)  # Nombre visible y clave para busquedas del agente.
    description = StringField(default="")  # Texto libre para explicar el articulo.
    category = StringField(default="")  # Agrupa productos y permite futuras busquedas por categoria.
    stock = IntField(required=True, min_value=0)  # Unidades disponibles; pedidos y desechos lo modifican.
    minimum_stock = IntField(default=0, min_value=0)  # Umbral usado para avisos y reposicion automatica.
    unit_price = DecimalField(required=True, precision=2, min_value=0)  # Precio para calcular pedidos y perdidas.
    expiration_date = DateTimeField(null=True)  # Fecha usada para generar desechos automaticos por caducidad.
    created_at = DateTimeField()  # Fecha de alta del producto.
    updated_at = DateTimeField()  # Fecha de ultimo cambio en inventario.

    @classmethod
    def objects_safe(cls):
        # Devuelve productos corrigiendo fechas ausentes antes de mostrarlos.
        return product_queryset(cls)

