from datetime import datetime

from apps.audit.models import AuditEntry


ACTION_LABELS = {
    # Diccionario de traduccion para que las trazas no muestren nombres tecnicos
    # como "create_product", sino etiquetas entendibles en el panel y en el chat.
    "list_products": "Consulta de productos",
    "create_product": "Alta de producto",
    "add_product_stock": "Entrada de inventario",
    "get_product_stock": "Consulta de stock",
    "update_product": "Actualizacion de producto",
    "delete_product": "Baja de producto",
    "delete_all_products": "Vaciado de inventario",
    "list_suppliers": "Consulta de proveedores",
    "create_supplier": "Alta de proveedor",
    "update_supplier": "Actualizacion de proveedor",
    "delete_supplier": "Baja de proveedor",
    "list_purchase_orders": "Consulta de pedidos",
    "create_purchase_order": "Alta de pedido",
    "receive_purchase_order": "Recepcion de pedido",
    "cancel_purchase_order": "Cancelacion de pedido",
    "update_purchase_order": "Actualizacion de pedido",
    "delete_purchase_order": "Baja de pedido",
    "list_waste": "Consulta de desechos",
    "create_waste": "Registro de desecho",
    "update_waste": "Actualizacion de desecho",
    "delete_waste": "Baja de desecho",
    "show_statistics": "Consulta de estadisticas",
    "configure_auto_replenishment": "Configuracion de reposicion automatica",
}


def record_audit(action, summary, entity_type="", entity_name="", entity_id="", related_entities=None, payload=None, status="success"):
    """Inserta una entrada de auditoria despues de una accion del ERP.

    Se guarda accion, entidad principal y entidades relacionadas para que luego
    el usuario pueda preguntar por trazabilidad, por ejemplo "ultimas acciones
    sobre TecnoSur". El `payload` conserva una foto resumida de los datos que
    participaron en la operacion.
    """
    entry = AuditEntry(
        action=action,
        entity_type=entity_type or "",
        entity_name=entity_name or "",
        entity_id=entity_id or "",
        summary=summary or "",
        status=status,
        related_entities=related_entities or [],
        payload=payload or {},
        created_at=datetime.utcnow(),
    )
    entry.save()
    return entry


def serialize_audit_entry(entry):
    """Convierte una traza de MongoDB en datos sencillos para el chat/panel.

    Esto evita exponer el documento completo y devuelve solo lo que interesa
    para una auditoria: accion, entidad, resumen, estado y fecha.
    """
    return {
        "id": str(entry.id),
        "timestamp": entry.created_at.isoformat() if entry.created_at else None,
        "action": entry.action,
        "action_label": ACTION_LABELS.get(entry.action, entry.action),
        "entity_type": entry.entity_type,
        "entity_name": entry.entity_name,
        "summary": entry.summary,
        "status": entry.status,
    }


def _matches_related_entity(entry, entity_type, entity_name):
    """Comprueba si una traza pertenece a la entidad principal o a una relacionada.

    Ejemplo: un pedido tiene entidad principal `purchase_order`, pero tambien
    puede estar relacionado con un proveedor. Gracias a esto se puede consultar
    historial de proveedor aunque la accion registrada fuera sobre un pedido.
    """
    normalized_name = (entity_name or "").strip().lower()
    if not normalized_name:
        return False

    primary_match = entry.entity_type == entity_type and entry.entity_name.lower() == normalized_name
    if primary_match:
        return True

    for related in entry.related_entities or []:
        if related.get("type") == entity_type and str(related.get("name", "")).lower() == normalized_name:
            return True
    return False


def supplier_audit_history(supplier_name, limit):
    """Recupera las ultimas acciones vinculadas a un proveedor concreto."""
    matching_entries = [
        entry
        for entry in AuditEntry.objects.order_by("-created_at")
        if _matches_related_entity(entry, "supplier", supplier_name)
    ]
    return matching_entries[:limit], len(matching_entries)


def deleted_products_history(limit):
    """Recupera historial de productos eliminados para consultas de trazabilidad."""
    matching_entries = list(AuditEntry.objects(action="delete_product").order_by("-created_at"))
    return matching_entries[:limit], len(matching_entries)
