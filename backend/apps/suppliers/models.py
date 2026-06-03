from mongoengine import DateTimeField, Document, ListField, StringField


class Supplier(Document):
    # Proveedor del ERP: contiene datos comerciales y la lista declarativa
    # de productos que puede suministrar.
    meta = {"collection": "suppliers", "ordering": ["name"]}

    name = StringField(required=True, unique=True, max_length=120)  # Nombre comercial usado en pedidos y chat.
    contact_email = StringField(default="")  # Email de contacto que el agente puede consultar.
    tax_id = StringField(default="")  # CIF/NIF o identificador fiscal.
    phone = StringField(default="")  # Telefono de contacto.
    address = StringField(default="")  # Direccion comercial o sede.
    products_supplied = ListField(StringField(), default=list)  # Productos que puede suministrar para reposicion.
    created_at = DateTimeField()  # Fecha de alta.
    updated_at = DateTimeField()  # Fecha de ultimo cambio.

