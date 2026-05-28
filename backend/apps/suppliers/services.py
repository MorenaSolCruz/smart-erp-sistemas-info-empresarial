from datetime import datetime
import unicodedata

from mongoengine.errors import NotUniqueError, ValidationError

from apps.suppliers.models import Supplier


def normalize_lookup(value):
    value = unicodedata.normalize("NFD", str(value or "").strip().lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return " ".join(value.split())


def resolve_supplier_matches(name):
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


def list_suppliers():
    return [serialize_supplier(supplier) for supplier in Supplier.objects.order_by("name")]


def get_supplier_by_id(supplier_id):
    return serialize_supplier(Supplier.objects.get(id=supplier_id))


def get_supplier_document_by_name(name):
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
    existing_supplier = Supplier.objects(name__iexact=data["name"]).first()
    if not existing_supplier:
        matches = resolve_supplier_matches(data["name"])
        if len(matches) == 1:
            existing_supplier = matches[0]
    if existing_supplier:
        return update_supplier(str(existing_supplier.id), data)

    now = datetime.utcnow()
    supplier = Supplier(
        name=data["name"],
        contact_email=data["contact_email"],
        tax_id=data.get("tax_id", ""),
        phone=data.get("phone", ""),
        address=data.get("address", ""),
        products_supplied=data.get("products_supplied", []),
        created_at=now,
        updated_at=now,
    )
    supplier.save()
    return serialize_supplier(supplier)


def update_supplier(supplier_id, data):
    supplier = Supplier.objects.get(id=supplier_id)

    for field in ["name", "contact_email", "tax_id", "phone", "address", "products_supplied"]:
        if field in data:
            setattr(supplier, field, data[field])

    supplier.updated_at = datetime.utcnow()
    supplier.save()
    return serialize_supplier(supplier)


def delete_supplier(supplier_id):
    from apps.purchase_orders.models import PurchaseOrder

    supplier = Supplier.objects.get(id=supplier_id)

    if PurchaseOrder.objects(supplier=supplier).first():
        raise ValidationError("No se puede eliminar el proveedor porque tiene pedidos asociados.")

    supplier.delete()
    return {"deleted": True, "id": supplier_id}


def clear_suppliers():
    from apps.purchase_orders.models import PurchaseOrder

    orders_count = PurchaseOrder.objects.count()
    PurchaseOrder.objects.delete()
    count = Supplier.objects.count()
    Supplier.objects.delete()
    return {"deleted": True, "deleted_count": count, "orders_deleted": orders_count}

