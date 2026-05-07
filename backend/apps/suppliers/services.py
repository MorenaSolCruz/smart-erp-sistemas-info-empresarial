from datetime import datetime

from apps.suppliers.models import Supplier


def serialize_supplier(supplier):
    return {
        "id": str(supplier.id),
        "name": supplier.name,
        "contact_email": supplier.contact_email,
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
    return Supplier.objects.get(name__iexact=name)


def create_supplier(data):
    now = datetime.utcnow()
    supplier = Supplier(
        name=data["name"],
        contact_email=data["contact_email"],
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

    for field in ["name", "contact_email", "phone", "address", "products_supplied"]:
        if field in data:
            setattr(supplier, field, data[field])

    supplier.updated_at = datetime.utcnow()
    supplier.save()
    return serialize_supplier(supplier)


def delete_supplier(supplier_id):
    supplier = Supplier.objects.get(id=supplier_id)
    supplier.delete()
    return {"deleted": True, "id": supplier_id}

