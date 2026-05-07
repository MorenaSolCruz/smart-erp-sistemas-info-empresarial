from datetime import datetime
from decimal import Decimal

from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError

from apps.products.models import Product


def serialize_product(product):
    return {
        "id": str(product.id),
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "stock": product.stock,
        "minimum_stock": product.minimum_stock,
        "unit_price": float(product.unit_price),
        "expiration_date": product.expiration_date.isoformat() if product.expiration_date else None,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
    }


def list_products():
    return [serialize_product(product) for product in Product.objects.order_by("name")]


def get_product_by_id(product_id):
    product = Product.objects.get(id=product_id)
    return serialize_product(product)


def get_product_document_by_name(name):
    return Product.objects.get(name__iexact=name)


def create_product(data):
    now = datetime.utcnow()
    product = Product(
        name=data["name"],
        description=data.get("description", ""),
        category=data.get("category", ""),
        stock=data["stock"],
        minimum_stock=data.get("minimum_stock", 0),
        unit_price=Decimal(str(data["unit_price"])),
        expiration_date=data.get("expiration_date"),
        created_at=now,
        updated_at=now,
    )
    product.save()
    return serialize_product(product)


def update_product(product_id, data):
    product = Product.objects.get(id=product_id)

    for field in ["name", "description", "category", "stock", "minimum_stock", "expiration_date"]:
        if field in data:
            setattr(product, field, data[field])

    if "unit_price" in data:
        product.unit_price = Decimal(str(data["unit_price"]))

    product.updated_at = datetime.utcnow()
    product.save()
    return serialize_product(product)


def delete_product(product_id):
    product = Product.objects.get(id=product_id)
    product.delete()
    return {"deleted": True, "id": product_id}


def adjust_stock(product, quantity_delta):
    new_stock = product.stock + quantity_delta
    if new_stock < 0:
        raise ValidationError("El stock no puede quedar en negativo.")

    product.stock = new_stock
    product.updated_at = datetime.utcnow()
    product.save()
    return product

