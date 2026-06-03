from datetime import datetime
from decimal import Decimal

from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError

from apps.products.models import Product


def normalize_lookup(value):
    """Normaliza texto para busquedas flexibles de productos.

    Quita diferencias de mayusculas, tildes y espacios para que el agente pueda
    encontrar "sensor termico" aunque el usuario escriba "Sensor Térmico".
    """
    return " ".join(value.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").split())


def singular_tokens(value):
    """Reduce plurales simples para mejorar coincidencias de nombres."""
    tokens = normalize_lookup(value).split()
    return [token[:-1] if token.endswith("s") and len(token) > 3 else token for token in tokens]


def _format_product_options(products):
    return ", ".join(product.name for product in products)


def _matches_product_tokens(query_name, product_name):
    query_tokens = singular_tokens(query_name)
    product_tokens = singular_tokens(product_name)
    if not query_tokens:
        return False
    return all(
        any(
            query_token == product_token
            or (len(query_token) >= 3 and product_token.startswith(query_token))
            or (len(product_token) >= 4 and query_token.startswith(product_token))
            for product_token in product_tokens
        )
        for query_token in query_tokens
    )


def _contains_dangerous_name_overlap(query_name, product_name):
    normalized_query = normalize_lookup(query_name)
    normalized_product = normalize_lookup(product_name)
    return (
        normalized_query != normalized_product
        and (
            normalized_product.startswith(normalized_query)
            or normalized_query.startswith(normalized_product)
        )
    )


def _resolve_product_candidates(name):
    # Busca productos por nombre exacto y por coincidencia flexible.
    # Si hay ambiguedad, fuerza al usuario/agente a indicar el nombre exacto.
    products = list(Product.objects.order_by("name"))
    normalized_name = normalize_lookup(name)

    exact_matches = [product for product in products if normalize_lookup(product.name) == normalized_name]
    if exact_matches:
        overlapping_matches = [
            product for product in products if _contains_dangerous_name_overlap(name, product.name)
        ]
        if overlapping_matches:
            candidates = sorted(exact_matches + overlapping_matches, key=lambda product: product.name.lower())
            raise ValidationError(
                f"He encontrado varios productos muy parecidos: {_format_product_options(candidates)}. "
                "Indica cual quieres usar exactamente."
            )
        return exact_matches

    fuzzy_matches = [product for product in products if _matches_product_tokens(name, product.name)]
    if not fuzzy_matches:
        raise DoesNotExist(f"No existe ningun articulo llamado {name} en el inventario.")

    if len(fuzzy_matches) > 1:
        raise ValidationError(
            f"He encontrado varios productos compatibles: {_format_product_options(fuzzy_matches)}. "
            "Indica el nombre exacto antes de continuar."
        )

    return fuzzy_matches


def serialize_product(product):
    """Transforma un documento Product en JSON para API/frontend.

    MongoEngine usa objetos y Decimal/DateTime; aqui se convierten a strings,
    floats y valores simples para que React pueda mostrar tablas y graficas.
    """
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
    from apps.waste.services import process_expired_products

    # Antes de listar, procesa caducidades para que el stock mostrado sea real.
    process_expired_products()
    return [serialize_product(product) for product in Product.objects.order_by("name")]


def product_insights(kind, limit=None, threshold=None, search=None):
    # Consultas avanzadas usadas por el agente: stock bajo, inventario total,
    # busquedas por nombre, productos caros, resumen, etc.
    products = list(Product.objects)
    if kind == "low_stock":
        max_stock = int(threshold if threshold is not None else 5)
        products = [product for product in products if int(product.stock) < max_stock]
        products.sort(key=lambda product: product.stock)
        return [serialize_product(product) for product in products[: limit or len(products)]]
    if kind == "most_stock":
        products.sort(key=lambda product: product.stock, reverse=True)
        return [serialize_product(product) for product in products[:1]]
    if kind == "price_desc":
        products.sort(key=lambda product: product.unit_price, reverse=True)
        return [serialize_product(product) for product in products[: limit or len(products)]]
    if kind == "name_contains":
        needle = normalize_lookup(search or "")
        return [serialize_product(product) for product in products if needle in normalize_lookup(product.name)]
    if kind == "inventory_value":
        total_value = sum(float(product.unit_price) for product in products)
        total_units = sum(int(product.stock) for product in products)
        return {
            "products_count": len(products),
            "total_units": total_units,
            "inventory_value": total_value,
        }
    if kind == "products_count":
        return {
            "products_count": len(products),
            "_query_kind": "products_count",
        }
    if kind == "out_of_stock":
        products = [product for product in products if int(product.stock) == 0]
        products.sort(key=lambda product: product.name)
        return [serialize_product(product) for product in products]
    if kind == "top_expensive":
        products.sort(key=lambda product: product.unit_price, reverse=True)
        return [serialize_product(product) for product in products[: limit or 10]]
    if kind == "low_stock_chart":
        max_stock = int(threshold if threshold is not None else 5)
        products = [product for product in products if int(product.stock) < max_stock]
        products.sort(key=lambda product: product.stock)
        return {
            "chart_type": "inventory_stock",
            "title": "Productos con menos stock",
            "rows": [serialize_product(product) for product in products[: limit or len(products)]],
        }
    if kind == "summary":
        total_value = sum(float(product.unit_price) * int(product.stock) for product in products)
        total_units = sum(int(product.stock) for product in products)
        exhausted = sum(1 for product in products if int(product.stock) == 0)
        low_stock = sum(1 for product in products if int(product.stock) < 5)
        return {
            "products_count": len(products),
            "total_units": total_units,
            "inventory_value": total_value,
            "out_of_stock_count": exhausted,
            "low_stock_count": low_stock,
        }
    return [serialize_product(product) for product in products]


def get_product_by_id(product_id):
    from apps.waste.services import process_expired_products

    process_expired_products()
    product = Product.objects.get(id=product_id)
    return serialize_product(product)


def get_product_document_by_name(name):
    from apps.waste.services import process_expired_products

    process_expired_products()
    return _resolve_product_candidates(name)[0]


def create_product(data):
    """Alta de producto.

    Crea inventario nuevo con categoria, stock, precio y caducidad. El nombre se
    valida sin distinguir mayusculas para evitar duplicados como "Filtro HEPA" y
    "filtro hepa", que luego confundiran pedidos y desechos.
    """
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
    """Actualiza un producto existente sin obligar a reenviar todos los campos.

    Si cambia el nombre, tambien se actualizan las lineas de pedidos que guardan
    `product_name` como texto. Esto mantiene coherencia entre inventario y pedidos
    cuando el profesor consulte historiales en la interfaz.
    """
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


def delete_product(product_id, quantity=None):
    """Elimina un producto o descuenta una cantidad concreta de stock.

    Con `quantity` se comporta como ajuste parcial de inventario. Sin `quantity`
    intenta borrar el producto completo, pero bloquea el borrado si hay pedidos o
    desechos asociados para no dejar referencias rotas.
    """
    from apps.purchase_orders.models import PurchaseOrder
    from apps.waste.models import WasteRecord

    product = Product.objects.get(id=product_id)

    if quantity is not None:
        # Si llega una cantidad, se interpreta como salida parcial de stock.
        quantity = int(quantity)
        if quantity <= 0:
            raise ValidationError("La cantidad a borrar debe ser mayor que cero.")
        if quantity > product.stock:
            raise ValidationError(
                f"No puedes borrar {quantity} unidad(es) de {product.name} porque solo hay {product.stock} en inventario."
            )
        adjust_stock(product, -quantity)
        return {
            "deleted": False,
            "id": product_id,
            "name": product.name,
            "removed_quantity": quantity,
            "stock": product.stock,
            "minimum_stock": product.minimum_stock,
        }

    if PurchaseOrder.objects(items__product_id=str(product.id)).first():
        # No se borra un producto referenciado por pedidos para no romper el ERP.
        raise ValidationError("No se puede eliminar el producto porque aparece en pedidos. Puedes actualizarlo o revisar los pedidos asociados.")

    if WasteRecord.objects(product=product).first():
        raise ValidationError("No se puede eliminar el producto porque tiene desechos registrados. Puedes consultar los desechos asociados antes de decidir.")

    product.delete()
    return {"deleted": True, "id": product_id}


def clear_products_inventory():
    """Vacia todo el inventario solo si no hay dependencias.

    Se protege contra borrados masivos cuando existen pedidos o desechos, porque
    esos registros necesitan productos para conservar trazabilidad.
    """
    from apps.purchase_orders.models import PurchaseOrder
    from apps.waste.models import WasteRecord

    if PurchaseOrder.objects.first():
        raise ValidationError(
            "No se puede vaciar todo el inventario porque existen pedidos asociados a productos. "
            "Elimina o cierra primero esas referencias antes de continuar."
        )

    if WasteRecord.objects.first():
        raise ValidationError(
            "No se puede vaciar todo el inventario porque existen desechos asociados a productos. "
            "Revisa o elimina primero esos registros antes de continuar."
        )

    count = Product.objects.count()
    Product.objects.delete()
    return {"deleted": True, "deleted_count": count}


def adjust_stock(product, quantity_delta):
    # Punto central para entradas y salidas de stock. Lo reutilizan pedidos y desechos.
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

