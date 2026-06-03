from datetime import datetime
import unicodedata

from mongoengine.errors import NotUniqueError, ValidationError

from apps.suppliers.models import Supplier

SUPPLIER_FIELDS = ["name", "contact_email", "tax_id", "phone", "address", "products_supplied"]


def normalize_lookup(value):
    """Normaliza nombres de proveedor para busqueda robusta.

    Sirve para que el agente no falle por tildes, mayusculas o espacios extra
    cuando el usuario escribe el nombre de un proveedor en lenguaje natural.
    """
    value = unicodedata.normalize("NFD", str(value or "").strip().lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return " ".join(value.split())


def resolve_supplier_matches(name):
    # Permite encontrar proveedores aunque el usuario escriba variantes simples
    # del nombre, por ejemplo con tildes o numeros pegados.
    requested = normalize_lookup(name)
    requested_without_digits = normalize_lookup("".join(char for char in str(name or "") if not char.isdigit()))
    matches = []
    for supplier in Supplier.objects:
        supplier_name = normalize_lookup(supplier.name)
        if supplier_name == requested or (requested_without_digits and supplier_name == requested_without_digits):
            matches.append(supplier)
            if len(matches) > 1:
                break
    return matches


def serialize_supplier(supplier):
    """Convierte Supplier en JSON simple para API, chat y panel."""
    return {
        "id": str(supplier.id),
        "name": supplier.name,
        "contact_email": supplier.contact_email,
        "tax_id": supplier.tax_id,
        "phone": supplier.phone,
        "address": supplier.address,
        "products_supplied": supplier.products_supplied,
        "created_at": supplier.created_at.isoformat() if supplier.created_at else None,
        "updated_at": supplier.updated_at.isoformat() if supplier.updated_at else None,
    }


def sanitize_supplier_payload(data, include_defaults=False):
    # Normaliza entradas del agente/API y acepta "cif" como alias de tax_id.
    payload = dict(data or {})
    if "cif" in payload and "tax_id" not in payload:
        payload["tax_id"] = payload["cif"]

    normalized = {}
    for field in SUPPLIER_FIELDS:
        if field in payload:
            normalized[field] = payload[field]

    if include_defaults:
        normalized.setdefault("contact_email", "")
        normalized.setdefault("tax_id", "")
        normalized.setdefault("phone", "")
        normalized.setdefault("address", "")
        normalized.setdefault("products_supplied", [])

    return normalized


def supplier_changed_fields(supplier, data):
    """Detecta que campos realmente cambian antes de guardar.

    Esto permite responder "ya tenia esos datos" y evita actualizaciones vacias
    que ensuciarian `updated_at` o la auditoria.
    """
    normalized = sanitize_supplier_payload(data)
    return [field for field, value in normalized.items() if getattr(supplier, field) != value]


def list_suppliers():
    """Lista proveedores ordenados por nombre para el panel y el chat."""
    return [serialize_supplier(supplier) for supplier in Supplier.objects.order_by("name")]


def get_supplier_by_id(supplier_id):
    """Recupera un proveedor exacto por ID para el endpoint de detalle."""
    return serialize_supplier(Supplier.objects.get(id=supplier_id))


def get_supplier_document_by_name(name):
    """Busca el documento Supplier por nombre para operaciones del agente.

    Devuelve el documento, no JSON, porque pedidos y reposicion automatica
    necesitan enlazar el proveedor real en MongoDB.
    """
    exact_supplier = Supplier.objects(name=name).first()
    if exact_supplier:
        return exact_supplier

    matches = list(Supplier.objects(name__iexact=name).limit(2))
    if not matches:
        matches = resolve_supplier_matches(name)
    if not matches:
        raise Supplier.DoesNotExist("Proveedor no encontrado.")
    if len(matches) > 1:
        raise ValidationError("Hay varios proveedores con nombres muy parecidos. Usa el nombre exacto que aparece al listar proveedores.")
    return matches[0]


def create_supplier(data):
    # Si el proveedor ya existe, no duplica registros: devuelve el existente
    # o lo actualiza cuando llegan datos nuevos.
    normalized_data = sanitize_supplier_payload(data, include_defaults=True)
    existing_supplier = Supplier.objects(name__iexact=data["name"]).first()
    if not existing_supplier:
        matches = resolve_supplier_matches(data["name"])
        if len(matches) == 1:
            existing_supplier = matches[0]
    if existing_supplier:
        changed_fields = supplier_changed_fields(existing_supplier, normalized_data)
        if not changed_fields:
            return {
                **serialize_supplier(existing_supplier),
                "_sync_status": "already_exists",
                "_changed_fields": [],
            }
        return update_supplier(
            str(existing_supplier.id),
            normalized_data,
            sync_status="updated_existing",
            changed_fields=changed_fields,
        )

    now = datetime.utcnow()
    supplier = Supplier(
        name=normalized_data["name"],
        contact_email=normalized_data["contact_email"],
        tax_id=normalized_data.get("tax_id", ""),
        phone=normalized_data.get("phone", ""),
        address=normalized_data.get("address", ""),
        products_supplied=normalized_data.get("products_supplied", []),
        created_at=now,
        updated_at=now,
    )
    supplier.save()
    return {**serialize_supplier(supplier), "_sync_status": "created", "_changed_fields": []}


def update_supplier(supplier_id, data, sync_status="updated", changed_fields=None):
    """Actualiza solo campos que cambiaron y devuelve metadatos internos.

    `_sync_status` ayuda al agente a responder distinto si creo, actualizo un
    existente o no habia cambios. La vista oculta esos campos al usuario final.
    """
    supplier = Supplier.objects.get(id=supplier_id)
    normalized_data = sanitize_supplier_payload(data)
    changed_fields = changed_fields if changed_fields is not None else supplier_changed_fields(supplier, normalized_data)

    if not changed_fields:
        return {
            **serialize_supplier(supplier),
            "_sync_status": "unchanged",
            "_changed_fields": [],
        }

    for field in changed_fields:
        setattr(supplier, field, normalized_data[field])

    supplier.updated_at = datetime.utcnow()
    supplier.save()
    return {
        **serialize_supplier(supplier),
        "_sync_status": sync_status,
        "_changed_fields": changed_fields,
    }


def delete_supplier(supplier_id):
    from apps.purchase_orders.models import PurchaseOrder

    supplier = Supplier.objects.get(id=supplier_id)

    if PurchaseOrder.objects(supplier=supplier).first():
        # Mantiene la integridad: un pedido debe conservar su proveedor.
        raise ValidationError("No se puede eliminar el proveedor porque tiene pedidos asociados.")

    supplier.delete()
    return {"deleted": True, "id": supplier_id}


def clear_suppliers():
    """Elimina proveedores y tambien pedidos asociados.

    Esta accion es masiva y por eso el agente pide confirmacion antes. Se usa
    para reiniciar datos durante una demo o prueba controlada.
    """
    from apps.purchase_orders.models import PurchaseOrder

    orders_count = PurchaseOrder.objects.count()
    PurchaseOrder.objects.delete()
    count = Supplier.objects.count()
    Supplier.objects.delete()
    return {"deleted": True, "deleted_count": count, "orders_deleted": orders_count}

