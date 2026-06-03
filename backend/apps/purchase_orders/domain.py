from datetime import datetime


OPEN_ORDER_STATUSES = {"pending", "partially_received"}
FINAL_ORDER_STATUSES = {"received", "cancelled", "closed_partial"}
ORDER_STATUS_CHOICES = ["pending", "partially_received", "received", "cancelled", "closed_partial"]

# Los estados se separan en domain.py para que las reglas de negocio no dependan
# de Django REST. Asi se pueden probar con tests unitarios sin pasar por la API.

class PurchaseOrderDomainError(Exception):
    default_message = "No se pudo completar la operacion de pedidos."

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


class OrderNotEditableError(PurchaseOrderDomainError):
    default_message = "Solo se pueden editar pedidos pendientes."


class OrderAlreadyReceivedError(PurchaseOrderDomainError):
    default_message = "Ese pedido ya estaba marcado como recibido."


class OrderCancelledError(PurchaseOrderDomainError):
    default_message = "No puedes operar sobre un pedido cancelado."


class OrderClosedError(PurchaseOrderDomainError):
    default_message = "Ese pedido ya esta cerrado."


class InvalidOrderItemError(PurchaseOrderDomainError):
    default_message = "Una de las lineas del pedido no es valida."


class ExcessiveReceiptQuantityError(PurchaseOrderDomainError):
    default_message = "La cantidad recibida supera la pendiente."


def utcnow():
    return datetime.utcnow()


def build_order_event(event_type, summary, items=None, metadata=None):
    # Crea una entrada de historial legible para cada cambio importante del pedido.
    payload = {
        "event": event_type,
        "summary": summary,
        "timestamp": utcnow().isoformat(),
    }
    if items:
        payload["items"] = items
    if metadata:
        payload["metadata"] = metadata
    return payload


def ensure_open_for_edit(order):
    """Permite editar solo pedidos pendientes.

    Cuando un pedido ya tiene recepciones o cierres, modificarlo directamente
    podria descuadrar stock; por eso se obliga a usar acciones de recepcion o
    cancelacion.
    """
    if order.status != "pending":
        raise OrderNotEditableError(
            "Solo se pueden editar pedidos pendientes. Usa recepcion o cancelacion para continuar."
        )


def ensure_open_for_receipt(order):
    """Valida que un pedido pueda recibir mercancia."""
    if order.status == "received":
        raise OrderAlreadyReceivedError()
    if order.status == "cancelled":
        raise OrderCancelledError("No puedes recibir un pedido cancelado.")
    if order.status == "closed_partial":
        raise OrderClosedError("El pedido ya esta cerrado parcialmente y no admite nuevas recepciones.")


def ensure_open_for_cancellation(order):
    """Valida que aun existan cantidades cancelables en el pedido."""
    if order.status == "received":
        raise PurchaseOrderDomainError("No puedes cancelar un pedido que ya ha sido recibido por completo.")
    if order.status in {"cancelled", "closed_partial"}:
        raise OrderClosedError("Ese pedido ya esta cerrado y no admite cancelacion adicional.")


def refresh_order_item(item):
    # Recalcula cantidades pendientes, importe de linea y estado de cada producto pedido.
    ordered = int(item["quantity"])
    received = int(item.get("received_quantity") or 0)
    cancelled = int(item.get("cancelled_quantity") or 0)
    if received < 0 or cancelled < 0:
        raise InvalidOrderItemError("Las cantidades recibidas o canceladas no pueden ser negativas.")
    if received + cancelled > ordered:
        raise InvalidOrderItemError(
            f"La linea {item.get('product_name', '')} supera la cantidad pedida con sus cantidades recibidas y canceladas."
        )

    pending = ordered - received - cancelled
    item["pending_quantity"] = pending
    item["line_total"] = float(item["unit_price"]) * ordered
    item.setdefault("reception_history", [])
    if received >= ordered:
        item["line_status"] = "received"
    elif cancelled >= ordered and received == 0:
        item["line_status"] = "cancelled"
    elif pending == 0 and received > 0:
        item["line_status"] = "closed_partial"
    elif received > 0:
        item["line_status"] = "partially_received"
    else:
        item["line_status"] = "pending"
    return item


def infer_order_status(items):
    # Deriva el estado general del pedido a partir del estado de sus lineas.
    if not items:
        return "pending"
    pending_exists = any(int(item.get("pending_quantity") or 0) > 0 for item in items)
    received_exists = any(int(item.get("received_quantity") or 0) > 0 for item in items)
    if pending_exists:
        return "partially_received" if received_exists else "pending"
    if all(item.get("line_status") == "received" for item in items):
        return "received"
    if received_exists:
        return "closed_partial"
    return "cancelled"


def validate_received_quantity(order_item, quantity):
    # Protege recepciones parciales: no permite recibir mas de lo pendiente.
    if quantity <= 0:
        raise ExcessiveReceiptQuantityError("La cantidad recibida debe ser mayor que cero.")
    pending_quantity = int(order_item.get("pending_quantity") or 0)
    if quantity > pending_quantity:
        raise ExcessiveReceiptQuantityError(
            f"No puedes recibir {quantity} unidad(es) de {order_item['product_name']} porque solo quedan "
            f"{pending_quantity} pendiente(s)."
        )
