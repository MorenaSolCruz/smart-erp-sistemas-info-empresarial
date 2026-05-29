from datetime import datetime
from decimal import Decimal
import unittest

from mongoengine.errors import DoesNotExist, ValidationError

from apps.llm_agent.services import CONVERSATION_MEMORY, execute_agent_action
from apps.products.models import Product
from apps.products.services import clear_products_inventory, get_product_document_by_name, product_insights
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
        CONVERSATION_MEMORY["pending_action"] = None

    def tearDown(self):
        PurchaseOrder.objects.delete()
        WasteRecord.objects.delete()
        Supplier.objects.delete()
        Product.objects.delete()
        CONVERSATION_MEMORY["pending_action"] = None

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

    def test_inventory_add_clarification_keeps_pending_context_and_executes(self):
        make_product("Filtro Demo Azul", stock=10)
        make_product("Filtro Demo Rojo", stock=8)

        ambiguous_response = execute_agent_action(
            "Introduce 10 unidades de Filtro Demo al inventario",
            provider_name="mock",
        )

        self.assertFalse(ambiguous_response["success"])
        self.assertIn("He encontrado varios productos", ambiguous_response["reply"])
        self.assertEqual(CONVERSATION_MEMORY["pending_action"]["intent"], "add_product_stock")
        self.assertEqual(CONVERSATION_MEMORY["pending_action"]["quantity"], 10)

        clarified_response = execute_agent_action("Filtro Demo Azul", provider_name="mock")

        self.assertTrue(clarified_response["success"])
        self.assertEqual(clarified_response["action"], "add_product_stock")
        self.assertEqual(Product.objects.get(name="Filtro Demo Azul").stock, 20)
        self.assertIsNone(CONVERSATION_MEMORY["pending_action"])

    def test_duplicate_product_create_can_continue_with_update_command(self):
        product = make_product("Filtro HEPA", stock=5)
        product.unit_price = Decimal("10.00")
        product.save()

        duplicate_response = execute_agent_action(
            "Crea producto Filtro HEPA con precio 35 y stock 20",
            provider_name="mock",
        )

        self.assertFalse(duplicate_response["success"])
        self.assertIn("responde 'actualiza'", duplicate_response["reply"].lower())
        self.assertEqual(CONVERSATION_MEMORY["pending_action"]["intent"], "duplicate_create_product")

        update_response = execute_agent_action("actualiza", provider_name="mock")

        updated_product = Product.objects.get(name="Filtro HEPA")
        self.assertTrue(update_response["success"])
        self.assertEqual(update_response["action"], "update_product")
        self.assertEqual(updated_product.stock, 20)
        self.assertEqual(float(updated_product.unit_price), 35.0)
        self.assertIsNone(CONVERSATION_MEMORY["pending_action"])

    def test_duplicate_product_create_can_continue_with_update_command_for_real_provider_flow(self):
        product = make_product("Filtro HEPA", stock=5)
        product.unit_price = Decimal("10.00")
        product.save()

        CONVERSATION_MEMORY["pending_action"] = {
            "intent": "duplicate_create_product",
            "name": "Filtro HEPA",
            "update_data": {
                "name": "Filtro HEPA",
                "stock": 20,
                "unit_price": 35,
                "description": "",
                "category": "Inventario",
                "minimum_stock": 0,
            },
        }

        update_response = execute_agent_action("actualiza", provider_name="gemini-2.5-flash")

        updated_product = Product.objects.get(name="Filtro HEPA")
        self.assertTrue(update_response["success"])
        self.assertEqual(update_response["action"], "update_product")
        self.assertEqual(updated_product.stock, 20)
        self.assertEqual(float(updated_product.unit_price), 35.0)
        self.assertIsNone(CONVERSATION_MEMORY["pending_action"])

    def test_unknown_name_still_raises_does_not_exist(self):
        make_product("Filtro HEPA", stock=10)

        with self.assertRaises(DoesNotExist):
            get_product_document_by_name("Monitor Industrial")

    def test_inventory_value_returns_sum_of_all_product_prices(self):
        make_product("Filtro HEPA", stock=10)
        product = make_product("Monitor Industrial", stock=3)
        product.unit_price = Decimal("25.50")
        product.save()

        result = product_insights("inventory_value")

        self.assertEqual(result["products_count"], 2)
        self.assertEqual(result["total_units"], 13)
        self.assertEqual(result["inventory_value"], 35.5)

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
