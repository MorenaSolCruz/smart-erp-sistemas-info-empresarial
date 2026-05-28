from datetime import datetime
from decimal import Decimal
import unittest

from mongoengine.errors import DoesNotExist, ValidationError

from apps.llm_agent.services import execute_agent_action
from apps.products.models import Product
from apps.products.services import clear_products_inventory, get_product_document_by_name
from apps.purchase_orders.models import PurchaseOrder
from apps.purchase_orders.services import create_purchase_order
from apps.suppliers.models import Supplier
from apps.waste.models import WasteRecord


def make_product(name, stock=10):
    now = datetime.utcnow()
    return Product(
        name=name,
        description="",
        category="Inventario",
        stock=stock,
        minimum_stock=0,
        unit_price=Decimal("10.00"),
        created_at=now,
        updated_at=now,
    ).save()


class ProductResolutionAndDeleteTests(unittest.TestCase):
    def setUp(self):
        PurchaseOrder.objects.delete()
        WasteRecord.objects.delete()
        Supplier.objects.delete()
        Product.objects.delete()

    def tearDown(self):
        PurchaseOrder.objects.delete()
        WasteRecord.objects.delete()
        Supplier.objects.delete()
        Product.objects.delete()

    def test_returns_explicit_message_when_product_does_not_exist(self):
        response = execute_agent_action("borra el articulo Inventado", provider_name="mock")

        self.assertFalse(response["success"])
        self.assertIn("No existe ningun articulo llamado Inventado", response["reply"])

    def test_partial_delete_only_removes_requested_quantity(self):
        make_product("Filtro HEPA", stock=10)

        response = execute_agent_action("borra 3 unidades de filtro hep", provider_name="mock")

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "delete_product")
        self.assertEqual(response["data"]["removed_quantity"], 3)
        self.assertEqual(response["data"]["stock"], 7)
        self.assertEqual(Product.objects.get(name="Filtro HEPA").stock, 7)

    def test_fuzzy_name_can_resolve_single_close_match(self):
        make_product("Filtro HEPA", stock=10)

        product = get_product_document_by_name("Filtro Hep")

        self.assertEqual(product.name, "Filtro HEPA")

    def test_ambiguous_short_name_requires_clarification(self):
        make_product("Filtro HEPA", stock=10)
        make_product("Filtro HEPAR", stock=8)

        with self.assertRaises(ValidationError) as exc:
            get_product_document_by_name("Filtro")

        self.assertIn("Filtro HEPA", str(exc.exception))
        self.assertIn("Filtro HEPAR", str(exc.exception))

    def test_exact_name_that_is_prefix_of_another_requires_clarification(self):
        make_product("Filtro HEPA", stock=10)
        make_product("Filtro HEPAR", stock=8)

        with self.assertRaises(ValidationError) as exc:
            get_product_document_by_name("Filtro HEPA")

        self.assertIn("Filtro HEPA", str(exc.exception))
        self.assertIn("Filtro HEPAR", str(exc.exception))

    def test_unknown_name_still_raises_does_not_exist(self):
        make_product("Filtro HEPA", stock=10)

        with self.assertRaises(DoesNotExist):
            get_product_document_by_name("Monitor Industrial")

    def test_clear_inventory_is_blocked_when_purchase_orders_exist(self):
        product = make_product("Filtro HEPA", stock=10)
        supplier = Supplier(
            name="Tecnosur",
            contact_email="compras@tecnosur.test",
            phone="",
            address="",
            products_supplied=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ).save()
        create_purchase_order(
            {
                "supplier_id": str(supplier.id),
                "items": [{"product_id": str(product.id), "quantity": 5}],
            }
        )

        with self.assertRaises(ValidationError) as exc:
            clear_products_inventory()

        self.assertIn("existen pedidos asociados", str(exc.exception))
        self.assertEqual(Product.objects.count(), 1)


if __name__ == "__main__":
    unittest.main()
