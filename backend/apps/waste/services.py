from datetime import datetime
from decimal import Decimal

from mongoengine.errors import ValidationError

from apps.products.models import Product
from apps.products.services import adjust_stock, get_product_document_by_name
from apps.waste.models import WasteRecord


def serialize_waste(record):
    return {
        "id": str(record.id),
        "product_id": str(record.product.id),
        "product_name": record.product.name,
        "quantity": record.quantity,
        "reason": record.reason,
        "date": record.date.isoformat() if record.date else None,
        "economic_loss": float(record.economic_loss),
        "remaining_stock": record.product.stock,
        "minimum_stock": record.product.minimum_stock,
    }


def process_expired_products(reference_time=None):
    reference_time = reference_time or datetime.utcnow()
    created_records = []

    expired_products = Product.objects(expiration_date__ne=None, expiration_date__lte=reference_time, stock__gt=0)
    for product in expired_products:
        quantity = int(product.stock)
        if quantity <= 0:
            continue

        adjust_stock(product, -quantity)
        economic_loss = Decimal(str(product.unit_price)) * quantity

        record = WasteRecord(
            product=product,
            quantity=quantity,
            reason="caducidad",
            date=reference_time,
            economic_loss=economic_loss,
        )
        record.save()
        created_records.append(record)

    return created_records


def list_waste_records():
    process_expired_products()
    return [serialize_waste(record) for record in WasteRecord.objects.order_by("-date")]


def get_waste_record_by_id(record_id):
    return serialize_waste(WasteRecord.objects.get(id=record_id))


def create_waste_record(data):
    if data.get("product_id"):
        product = Product.objects.get(id=data["product_id"])
    elif data.get("product_name"):
        product = get_product_document_by_name(data["product_name"])
    else:
        raise ValidationError("Debes indicar product_id o product_name.")

    quantity = int(data["quantity"])
    if quantity <= 0:
        raise ValidationError("La cantidad del desecho debe ser mayor que cero.")

    adjust_stock(product, -quantity)
    economic_loss = Decimal(str(product.unit_price)) * quantity

    record = WasteRecord(
        product=product,
        quantity=quantity,
        reason=data["reason"],
        date=datetime.utcnow(),
        economic_loss=economic_loss,
    )
    record.save()
    return serialize_waste(record)


def update_waste_record(record_id, data):
    record = WasteRecord.objects.get(id=record_id)

    if data.get("product_id"):
        product = Product.objects.get(id=data["product_id"])
    elif data.get("product_name"):
        product = get_product_document_by_name(data["product_name"])
    else:
        product = record.product

    quantity = int(data["quantity"])
    if quantity <= 0:
        raise ValidationError("La cantidad del desecho debe ser mayor que cero.")

    original_product = record.product
    adjust_stock(original_product, record.quantity)
    adjust_stock(product, -quantity)
    economic_loss = Decimal(str(product.unit_price)) * quantity

    record.product = product
    record.quantity = quantity
    record.reason = data["reason"]
    record.economic_loss = economic_loss
    record.save()
    return serialize_waste(record)


def delete_waste_record(record_id):
    record = WasteRecord.objects.get(id=record_id)
    adjust_stock(record.product, record.quantity)
    record.delete()
    return {"deleted": True, "id": record_id}
