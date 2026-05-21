from datetime import datetime
from decimal import Decimal

from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError

from apps.products.models import Product


def normalize_lookup(value):
    return " ".join(value.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").split())


def singular_tokens(value):
    tokens = normalize_lookup(value).split()
    return [token[:-1] if token.endswith("s") and len(token) > 3 else token for token in tokens]


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
    exact_product = Product.objects(name=name).first()
    if exact_product:
        return exact_product

    matches = list(Product.objects(name__iexact=name).limit(2))
    if not matches:
        query_tokens = singular_tokens(name)
        fuzzy_matches = []
        for product in Product.objects:
            product_tokens = singular_tokens(product.name)
            if all(any(query_token in product_token or product_token in query_token for product_token in product_tokens) for query_token in query_tokens):
                fuzzy_matches.append(product)
                if len(fuzzy_matches) > 1:
                    break
        if not fuzzy_matches:
            raise DoesNotExist("Producto no encontrado.")
        matches = fuzzy_matches
    if len(matches) > 1:
        raise ValidationError("Hay varios productos con nombres muy parecidos. Usa el nombre exacto que aparece al listar productos.")
    return matches[0]


def create_product(data):
    if Product.objects(name__iexact=data["name"]).first():
        raise NotUniqueError("Ya existe un producto con ese nombre.")

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
    previous_name = product.name

    for field in ["name", "description", "category", "stock", "minimum_stock", "expiration_date"]:
        if field in data:
            setattr(product, field, data[field])

    if "unit_price" in data:
        product.unit_price = Decimal(str(data["unit_price"]))

    product.updated_at = datetime.utcnow()
    product.save()

    if "name" in data and data["name"] != previous_name:
        sync_product_name_in_purchase_orders(product)

    return serialize_product(product)


def delete_product(product_id):
    from apps.purchase_orders.models import PurchaseOrder
    from apps.waste.models import WasteRecord

    product = Product.objects.get(id=product_id)

    if PurchaseOrder.objects(items__product_id=str(product.id)).first():
        raise ValidationError("No se puede eliminar el producto porque aparece en pedidos. Puedes actualizarlo o revisar los pedidos asociados.")

    if WasteRecord.objects(product=product).first():
        raise ValidationError("No se puede eliminar el producto porque tiene desechos registrados. Puedes consultar los desechos asociados antes de decidir.")

    product.delete()
    return {"deleted": True, "id": product_id}


def clear_products_inventory():
    count = Product.objects.count()
    Product.objects.delete()
    return {"deleted": True, "deleted_count": count}


def adjust_stock(product, quantity_delta):
    new_stock = product.stock + quantity_delta
    if new_stock < 0:
        raise ValidationError("El stock no puede quedar en negativo.")

    product.stock = new_stock
    product.updated_at = datetime.utcnow()
    product.save()
    return product


def sync_product_name_in_purchase_orders(product):
    from apps.purchase_orders.models import PurchaseOrder

    orders = PurchaseOrder.objects(items__product_id=str(product.id))
    for order in orders:
        changed = False
        for item in order.items:
            if item.get("product_id") == str(product.id) and item.get("product_name") != product.name:
                item["product_name"] = product.name
                changed = True
        if changed:
            order.save()

