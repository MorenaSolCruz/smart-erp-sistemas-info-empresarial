from mongoengine import DateTimeField, DictField, Document, ListField, StringField


class AuditEntry(Document):
    # Traza de auditoria: registra acciones ejecutadas por el agente y entidades afectadas.
    meta = {"collection": "audit_entries", "ordering": ["-created_at"]}

    action = StringField(required=True)  # Accion interna ejecutada, por ejemplo create_product.
    entity_type = StringField(default="")  # Tipo principal afectado: product, supplier, purchase_order...
    entity_name = StringField(default="")  # Nombre legible para buscar la traza por chat.
    entity_id = StringField(default="")  # ID tecnico cuando existe.
    summary = StringField(default="")  # Resumen humano de lo ocurrido.
    status = StringField(default="success")  # Estado de la accion auditada.
    related_entities = ListField(DictField(), default=list)  # Entidades relacionadas, como proveedor de un pedido.
    payload = DictField(default=dict)  # Datos resumidos de la operacion para contexto.
    created_at = DateTimeField(required=True)  # Fecha exacta de la traza.

