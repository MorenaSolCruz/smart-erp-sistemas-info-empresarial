from decimal import Decimal
from difflib import get_close_matches
import re
import unicodedata
from mongoengine.errors import ValidationError

from apps.products.models import Product
from apps.products.services import adjust_stock, get_product_document_by_name
from apps.purchase_orders.domain import (
    OPEN_ORDER_STATUSES,
    ORDER_STATUS_CHOICES,
    ExcessiveReceiptQuantityError,
    InvalidOrderItemError,
    PurchaseOrderDomainError,
    build_order_event,
    ensure_open_for_cancellation,
    ensure_open_for_edit,
    ensure_open_for_receipt,
    infer_order_status,
    refresh_order_item,
    utcnow,
    validate_received_quantity,
)
from apps.purchase_orders.models import PurchaseOrder
from apps.suppliers.models import Supplier


def serialize_purchase_order(order):
    return {
        "id": str(order.id),
        "supplier_id": str(order.supplier.id),
        "supplier_name": order.supplier.name,
        "items": order.items,
        "total_amount": float(order.total_amount),
        "status": order.status,
        "history": order.history or [],
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "received_at": order.received_at.isoformat() if order.received_at else None,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
    }


def _status_filter_query(status):
    if status == "pending":
        return {"status__in": ["pending", "partially_received"]}
    return {"status": status}


def list_purchase_orders(status=None):
    orders = PurchaseOrder.objects.order_by("-created_at")
    if status:
        orders = orders.filter(**_status_filter_query(status))
    return [serialize_purchase_order(order) for order in orders]


def resolve_purchase_order(order_id):
    order_id = str(order_id).strip()
    if order_id.isdigit():
        index = int(order_id) - 1
        orders = list(PurchaseOrder.objects.order_by("-created_at"))
        if index < 0 or index >= len(orders):
            raise PurchaseOrder.DoesNotExist("Pedido no encontrado.")
        return orders[index]
    if len(order_id) < 24:
        matches = [order for order in PurchaseOrder.objects if str(order.id).startswith(order_id)]
        if not matches:
            raise PurchaseOrder.DoesNotExist("Pedido no encontrado.")
        if len(matches) > 1:
            raise ValidationError("Hay varios pedidos con ese ID corto. Usa algunos caracteres mas del ID.")
        return matches[0]
    return PurchaseOrder.objects.get(id=order_id)


def get_purchase_order_by_id(order_id):
    return serialize_purchase_order(resolve_purchase_order(order_id))


def _build_order_item(product, quantity, unit_price):
    item = {
        "product_id": str(product.id),
        "product_name": product.name,
        "quantity": int(quantity),
        "received_quantity": 0,
        "cancelled_quantity": 0,
        "unit_price": float(unit_price),
        "reception_history": [],
    }
    return refresh_order_item(item)

def _dedupe_products_by_normalized_name(products):
    result = {}
    for product in products:
        result.setdefault(normalize_key(product.name), product)
    return list(result.values())

def _resolve_product(item):
    product_name = item.get("product_name") or item.get("name")

    if not product_name:
        raise InvalidOrderItemError("Cada linea del pedido debe indicar un producto.")

    input_keys = []

    for key in item.get("product_search_keys", []):
        input_keys.extend(build_product_keys(key))

    input_keys.extend(build_product_keys(product_name))
    input_keys = list(dict.fromkeys(input_keys))

    products = list(Product.objects.all())

    product_map = {}

    for product in products:
        for key in build_product_keys(product.name):
            product_map.setdefault(key, []).append(product)

    exact_matches = []
    for key in input_keys:
        exact_matches.extend(product_map.get(key, []))

    exact_matches = _dedupe_products_by_normalized_name(exact_matches)

    if len(exact_matches) == 1:
        return exact_matches[0]

    if len(exact_matches) > 1:
        names = ", ".join(product.name for product in exact_matches)
        raise InvalidOrderItemError(
            f"He encontrado varios productos compatibles: {names}. Indica el nombre exacto antes de continuar."
        )

    fuzzy_matches = []
    available_keys = list(product_map.keys())

    for key in input_keys:
        matches = get_close_matches(key, available_keys, n=3, cutoff=0.72)
        for matched_key in matches:
            fuzzy_matches.extend(product_map[matched_key])

    fuzzy_matches = _dedupe_products_by_normalized_name(fuzzy_matches)

    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]

    if len(fuzzy_matches) > 1:
        names = ", ".join(product.name for product in fuzzy_matches)
        raise InvalidOrderItemError(
            f"He encontrado varios productos muy parecidos: {names}. Indica cuál quieres usar exactamente."
        )

    raise InvalidOrderItemError(
        f"No existe ningún artículo llamado {product_name} en el inventario."
    )


def _normalize_items(raw_items):
    if not raw_items:
        raise InvalidOrderItemError("El pedido debe incluir al menos una linea de producto.")

    normalized_items = []
    total_amount = Decimal("0")
    for item in raw_items:
        product = _resolve_product(item)
        quantity = int(item["quantity"])
        unit_price = Decimal(str(item.get("unit_price") or product.unit_price))
        if quantity <= 0:
            raise InvalidOrderItemError("La cantidad del pedido debe ser mayor que cero.")
        if unit_price < 0:
            raise InvalidOrderItemError("El precio unitario no puede ser negativo.")
        normalized_item = _build_order_item(product, quantity, unit_price)
        normalized_items.append(normalized_item)
        total_amount += unit_price * quantity
    return normalized_items, total_amount

def normalize_key(value):
    value = unicodedata.normalize("NFD", value.strip().lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def singularize_basic(value):
    words = value.split()
    result = []

    for word in words:
        if word.endswith("es") and len(word) > 4:
            result.append(word[:-2])
        elif word.endswith("s") and len(word) > 3:
            result.append(word[:-1])
        else:
            result.append(word)

    return " ".join(result)


def build_product_keys(value):
    normalized = normalize_key(value)
    singular = normalize_key(singularize_basic(normalized))

    return list(dict.fromkeys([normalized, singular]))

def create_purchase_order(data):
    supplier = Supplier.objects.get(id=data["supplier_id"])
    normalized_items, total_amount = _normalize_items(data["items"])
    now = utcnow()
    order = PurchaseOrder(
        supplier=supplier,
        items=normalized_items,
        total_amount=total_amount,
        status="pending",
        history=[build_order_event("created", f"Pedido creado para {supplier.name}.", items=normalized_items)],
        created_at=now,
        updated_at=now,
    )
    order.save()
    return serialize_purchase_order(order)


def update_purchase_order(order_id, data):
    order = resolve_purchase_order(order_id)
    ensure_open_for_edit(order)
    supplier = Supplier.objects.get(id=data["supplier_id"])
    normalized_items, total_amount = _normalize_items(data["items"])
    order.supplier = supplier
    order.items = normalized_items
    order.total_amount = total_amount
    order.updated_at = utcnow()
    order.history.append(build_order_event("updated", f"Pedido actualizado para {supplier.name}.", items=normalized_items))
    order.save()
    return serialize_purchase_order(order)


def _resolve_received_items(order, received_items):
    if not received_items:
        return [
            {
                "product_id": item["product_id"],
                "quantity": int(item.get("pending_quantity") or 0),
            }
            for item in order.items
            if int(item.get("pending_quantity") or 0) > 0
        ]
    return received_items


def _find_order_item(order, received_item):
    received_product_id = received_item.get("product_id")
    received_product_name = received_item.get("product_name")
    for item in order.items:
        if received_product_id and item["product_id"] == received_product_id:
            return item
        if received_product_name and item["product_name"] == get_product_document_by_name(received_product_name).name:
            return item
    raise ValidationError("Una de las líneas recibidas no pertenece al pedido indicado.")


def receive_purchase_order(order_id, received_items=None):
    order = PurchaseOrder.objects.get(id=order_id)
    ensure_open_for_receipt(order)

    resolved_received_items = _resolve_received_items(order, received_items)
    if not resolved_received_items:
        raise PurchaseOrderDomainError("No quedan unidades pendientes por recibir en este pedido.")

    movement_log = []
    for received_item in resolved_received_items:
        order_item = _find_order_item(order, received_item)
        quantity = int(received_item["quantity"])
        validate_received_quantity(order_item, quantity)

        product = Product.objects.get(id=order_item["product_id"])
        adjust_stock(product, quantity)
        order_item["received_quantity"] = int(order_item.get("received_quantity") or 0) + quantity
        order_item.setdefault("reception_history", []).append(
            {"quantity": quantity, "received_at": utcnow().isoformat()}
        )
        refresh_order_item(order_item)
        movement_log.append({"product_name": order_item["product_name"], "quantity": quantity})

    order.status = infer_order_status(order.items)
    now = utcnow()
    order.updated_at = now
    if order.status == "received":
        order.received_at = now
    order.history.append(
        build_order_event(
            "received" if order.status == "received" else "partial_receipt",
            "Recepción de mercancía aplicada al pedido.",
            items=movement_log,
            metadata={"status": order.status},
        )
    )
    order.save()
    return serialize_purchase_order(order)


def receive_latest_purchase_order_for_supplier(supplier_id, received_items=None):
    supplier = Supplier.objects.get(id=supplier_id)
    order = PurchaseOrder.objects(supplier=supplier, status__in=list(OPEN_ORDER_STATUSES)).order_by("-created_at").first()
    if not order:
        raise PurchaseOrderDomainError(f"No hay pedidos pendientes de recibir para el proveedor {supplier.name}.")
    return receive_purchase_order(str(order.id), received_items=received_items)


def cancel_purchase_order(order_id, reason=""):
    order = PurchaseOrder.objects.get(id=order_id)
    ensure_open_for_cancellation(order)

    cancelled_lines = []
    for item in order.items:
        pending_quantity = int(item.get("pending_quantity") or 0)
        if pending_quantity <= 0:
            continue
        item["cancelled_quantity"] = int(item.get("cancelled_quantity") or 0) + pending_quantity
        refresh_order_item(item)
        cancelled_lines.append({"product_name": item["product_name"], "quantity": pending_quantity})

    if not cancelled_lines:
        raise PurchaseOrderDomainError("No quedan lineas pendientes por cancelar en este pedido.")

    order.status = infer_order_status(order.items)
    now = utcnow()
    order.updated_at = now
    order.cancelled_at = now
    order.history.append(
        build_order_event(
            "cancelled",
            "Pedido cancelado." if not reason else f"Pedido cancelado. Motivo: {reason}",
            items=cancelled_lines,
            metadata={"reason": reason or ""},
        )
    )
    order.save()
    return serialize_purchase_order(order)


def delete_purchase_order(order_id):
    order = resolve_purchase_order(order_id)
    affected_products = []
    supplier_name = order.supplier.name
    supplier_id = str(order.supplier.id)
    if order.status in {"received", "partially_received"}:
        for item in order.items:
            received_quantity = int(item.get("received_quantity") or 0)
            if received_quantity <= 0:
                continue
            product = Product.objects.get(id=item["product_id"])
            adjust_stock(product, -received_quantity)
            affected_products.append(
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "stock": product.stock,
                    "minimum_stock": product.minimum_stock,
                    "removed_quantity": received_quantity,
                }
            )

    order.delete()
    return {
        "deleted": True,
        "id": order_id,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "affected_products": affected_products,
    }


def order_insights(kind):
    orders = list(PurchaseOrder.objects.order_by("-created_at"))
    if kind == "pending":
        return [serialize_purchase_order(order) for order in orders if order.status in ["pending", "created", "open", "partially_received"]]
    if kind == "top_supplier":
        totals = {}
        for order in orders:
            name = order.supplier.name
            if name not in totals:
                totals[name] = {"supplier_name": name, "orders_count": 0, "total_amount": 0.0}
            totals[name]["orders_count"] += 1
            totals[name]["total_amount"] += float(order.total_amount)
        return sorted(totals.values(), key=lambda row: row["orders_count"], reverse=True)[:1]
    if kind == "latest":
        return serialize_purchase_order(orders[0]) if orders else None
    return [serialize_purchase_order(order) for order in orders]


def mark_purchase_order_completed(order_id):
    order = resolve_purchase_order(order_id)
    order.status = "completed"
    order.save()
    return serialize_purchase_order(order)


def append_items_to_purchase_order(order_id, raw_items):
    order = resolve_purchase_order(order_id)
    ensure_open_for_edit(order)
    normalized_items, added_total_amount = _normalize_items(raw_items)
    order.items.extend(normalized_items)
    order.total_amount = Decimal(str(order.total_amount)) + added_total_amount
    order.updated_at = utcnow()
    order.history.append(
        build_order_event(
            "updated",
            f"Pedido actualizado para {order.supplier.name}.",
            items=normalized_items,
            metadata={"mode": "append"},
        )
    )
    order.save()
    return serialize_purchase_order(order)


def cancel_latest_purchase_order():
    latest = order_insights("latest")
    if not latest:
        raise PurchaseOrder.DoesNotExist("Pedido no encontrado.")
    return delete_purchase_order(latest["id"])
