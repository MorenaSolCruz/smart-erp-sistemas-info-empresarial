from datetime import datetime
from decimal import Decimal

from mongoengine.errors import ValidationError

from apps.products.models import Product
from apps.products.services import adjust_stock, get_product_document_by_name
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
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def list_purchase_orders():
    return [serialize_purchase_order(order) for order in PurchaseOrder.objects.order_by("-created_at")]


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
            raise ValidationError("Hay varios pedidos con ese ID corto. Usa algunos caracteres más del ID.")
        return matches[0]
    return PurchaseOrder.objects.get(id=order_id)


def get_purchase_order_by_id(order_id):
    return serialize_purchase_order(resolve_purchase_order(order_id))


def create_purchase_order(data):
    supplier = Supplier.objects.get(id=data["supplier_id"])
    if not data.get("items"):
        raise ValidationError("El pedido debe incluir al menos una línea de producto.")

    normalized_items = []
    total_amount = Decimal("0")

    for item in data["items"]:
        product = None
        if item.get("product_id"):
            product = Product.objects.get(id=item["product_id"])
        elif item.get("product_name"):
            product = get_product_document_by_name(item["product_name"])
        else:
            raise ValidationError("Cada item debe incluir product_id o product_name.")

        quantity = int(item["quantity"])
        unit_price = Decimal(str(item.get("unit_price") or product.unit_price))
        if quantity <= 0:
            raise ValidationError("La cantidad del pedido debe ser mayor que cero.")
        if unit_price < 0:
            raise ValidationError("El precio unitario no puede ser negativo.")

        adjust_stock(product, quantity)

        normalized_item = {
            "product_id": str(product.id),
            "product_name": product.name,
            "quantity": quantity,
            "unit_price": float(unit_price),
            "line_total": float(unit_price * quantity),
        }
        normalized_items.append(normalized_item)
        total_amount += unit_price * quantity

    order = PurchaseOrder(
        supplier=supplier,
        items=normalized_items,
        total_amount=total_amount,
        status="received",
        created_at=datetime.utcnow(),
    )
    order.save()
    return serialize_purchase_order(order)


def update_purchase_order(order_id, data):
    order = resolve_purchase_order(order_id)
    supplier = Supplier.objects.get(id=data["supplier_id"])
    normalized_items = []
    total_amount = Decimal("0")
    resolved_items = []

    if not data.get("items"):
        raise ValidationError("El pedido debe incluir al menos una línea de producto.")

    for item in data["items"]:
        if item.get("product_id"):
            product = Product.objects.get(id=item["product_id"])
        else:
            product = get_product_document_by_name(item["product_name"])

        quantity = int(item["quantity"])
        unit_price = Decimal(str(item.get("unit_price") or product.unit_price))
        if quantity <= 0:
            raise ValidationError("La cantidad del pedido debe ser mayor que cero.")
        if unit_price < 0:
            raise ValidationError("El precio unitario no puede ser negativo.")
        resolved_items.append((product, quantity, unit_price))

    for item in order.items:
        product = Product.objects.get(id=item["product_id"])
        adjust_stock(product, -int(item["quantity"]))

    for product, quantity, unit_price in resolved_items:
        adjust_stock(product, quantity)

        normalized_item = {
            "product_id": str(product.id),
            "product_name": product.name,
            "quantity": quantity,
            "unit_price": float(unit_price),
            "line_total": float(unit_price * quantity),
        }
        normalized_items.append(normalized_item)
        total_amount += unit_price * quantity

    order.supplier = supplier
    order.items = normalized_items
    order.total_amount = total_amount
    order.status = data.get("status", order.status)
    order.save()
    return serialize_purchase_order(order)


def delete_purchase_order(order_id):
    order = resolve_purchase_order(order_id)
    affected_products = []
    supplier_name = order.supplier.name
    supplier_id = str(order.supplier.id)
    for item in order.items:
        product = Product.objects.get(id=item["product_id"])
        adjust_stock(product, -int(item["quantity"]))
        affected_products.append(
            {
                "product_id": str(product.id),
                "product_name": product.name,
                "stock": product.stock,
                "minimum_stock": product.minimum_stock,
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
        return [serialize_purchase_order(order) for order in orders if order.status in ["pending", "created", "open"]]
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


def cancel_latest_purchase_order():
    latest = order_insights("latest")
    if not latest:
        raise PurchaseOrder.DoesNotExist("Pedido no encontrado.")
    return delete_purchase_order(latest["id"])
