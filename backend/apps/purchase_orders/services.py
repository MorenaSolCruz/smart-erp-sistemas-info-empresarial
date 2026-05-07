from datetime import datetime
from decimal import Decimal

from mongoengine.errors import ValidationError

from apps.products.models import Product
from apps.products.services import adjust_stock
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


def get_purchase_order_by_id(order_id):
    return serialize_purchase_order(PurchaseOrder.objects.get(id=order_id))


def create_purchase_order(data):
    supplier = Supplier.objects.get(id=data["supplier_id"])

    normalized_items = []
    total_amount = Decimal("0")

    for item in data["items"]:
        product = None
        if item.get("product_id"):
            product = Product.objects.get(id=item["product_id"])
        elif item.get("product_name"):
            product = Product.objects.get(name__iexact=item["product_name"])
        else:
            raise ValidationError("Cada item debe incluir product_id o product_name.")

        quantity = int(item["quantity"])
        unit_price = Decimal(str(item.get("unit_price") or product.unit_price))

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
    order = PurchaseOrder.objects.get(id=order_id)

    for item in order.items:
        product = Product.objects.get(id=item["product_id"])
        adjust_stock(product, -int(item["quantity"]))

    supplier = Supplier.objects.get(id=data["supplier_id"])
    normalized_items = []
    total_amount = Decimal("0")

    for item in data["items"]:
        if item.get("product_id"):
            product = Product.objects.get(id=item["product_id"])
        else:
            product = Product.objects.get(name__iexact=item["product_name"])

        quantity = int(item["quantity"])
        unit_price = Decimal(str(item.get("unit_price") or product.unit_price))
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
    order = PurchaseOrder.objects.get(id=order_id)
    for item in order.items:
        product = Product.objects.get(id=item["product_id"])
        adjust_stock(product, -int(item["quantity"]))

    order.delete()
    return {"deleted": True, "id": order_id}
