# Pruebas de dominio de pedidos: validan estados, cantidades recibidas y reglas
# de negocio independientes de la API.
from datetime import datetime
from decimal import Decimal
import unittest

from apps.products.models import Product
from apps.purchase_orders.domain import (
    ExcessiveReceiptQuantityError,
    OrderClosedError,
    OrderNotEditableError,
)
from apps.purchase_orders.models import PurchaseOrder
from apps.purchase_orders.services import (
    cancel_purchase_order,
    create_purchase_order,
    receive_purchase_order,
    update_purchase_order,
)
from apps.suppliers.models import Supplier


def make_product(name, stock=10, unit_price="10.00"):
    now = datetime.utcnow()
    return Product(
        name=name,
        description="",
        category="Inventario",
        stock=stock,
        minimum_stock=0,
        unit_price=Decimal(unit_price),
        created_at=now,
        updated_at=now,
    ).save()


def make_supplier(name):
    now = datetime.utcnow()
    return Supplier(
        name=name,
        contact_email=f"{name.lower()}@mail.test",
        phone="",
        address="",
        products_supplied=[],
        created_at=now,
        updated_at=now,
    ).save()


class PurchaseOrderDomainTests(unittest.TestCase):
    def setUp(self):
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()
        self.product = make_product("Filtro HEPA", stock=5)
        self.supplier = make_supplier("Tecnosur")

    def tearDown(self):
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()

    def test_cannot_edit_order_after_partial_receipt(self):
        order = create_purchase_order(
            {
                "supplier_id": str(self.supplier.id),
                "items": [{"product_name": "Filtro HEPA", "quantity": 8}],
            }
        )
        receive_purchase_order(order["id"], received_items=[{"product_name": "Filtro HEPA", "quantity": 3}])

        with self.assertRaises(OrderNotEditableError):
            update_purchase_order(
                order["id"],
                {
                    "supplier_id": str(self.supplier.id),
                    "items": [{"product_name": "Filtro HEPA", "quantity": 10}],
                },
            )

    def test_cannot_receive_more_than_pending_quantity(self):
        order = create_purchase_order(
            {
                "supplier_id": str(self.supplier.id),
                "items": [{"product_name": "Filtro HEPA", "quantity": 8}],
            }
        )
        receive_purchase_order(order["id"], received_items=[{"product_name": "Filtro HEPA", "quantity": 3}])

        with self.assertRaises(ExcessiveReceiptQuantityError):
            receive_purchase_order(order["id"], received_items=[{"product_name": "Filtro HEPA", "quantity": 6}])

    def test_cannot_cancel_order_closed_partial(self):
        order = create_purchase_order(
            {
                "supplier_id": str(self.supplier.id),
                "items": [{"product_name": "Filtro HEPA", "quantity": 8}],
            }
        )
        receive_purchase_order(order["id"], received_items=[{"product_name": "Filtro HEPA", "quantity": 3}])
        cancelled = cancel_purchase_order(order["id"], reason="sin suministro")

        self.assertEqual(cancelled["status"], "closed_partial")

        with self.assertRaises(OrderClosedError):
            cancel_purchase_order(order["id"], reason="doble cancelacion")


if __name__ == "__main__":
    unittest.main()
