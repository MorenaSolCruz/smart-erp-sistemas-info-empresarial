from datetime import datetime
from decimal import Decimal
import unittest

from apps.llm_agent.services import CONVERSATION_MEMORY, execute_agent_action
from apps.products.models import Product
from apps.purchase_orders.models import PurchaseOrder
from apps.purchase_orders.services import create_purchase_order
from apps.suppliers.models import Supplier
from apps.waste.models import WasteRecord


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


def make_supplier(name, email="demo@test.com"):
    now = datetime.utcnow()
    return Supplier(
        name=name,
        contact_email=email,
        tax_id="",
        phone="",
        address="",
        products_supplied=[],
        created_at=now,
        updated_at=now,
    ).save()


class DemoPromptCoverageTests(unittest.TestCase):
    def setUp(self):
        WasteRecord.objects.delete()
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()
        CONVERSATION_MEMORY["last_supplier_name"] = None
        CONVERSATION_MEMORY["last_product_name"] = None
        CONVERSATION_MEMORY["last_purchase_order_id"] = None
        CONVERSATION_MEMORY["pending_action"] = None
        CONVERSATION_MEMORY["auto_replenishment_enabled"] = False
        CONVERSATION_MEMORY["auto_replenishment_threshold"] = None

    def tearDown(self):
        WasteRecord.objects.delete()
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()

    def test_last_supplier_email_prompt_is_covered(self):
        make_supplier("FireControl", "pedidos@firecontrol.com")
        CONVERSATION_MEMORY["last_supplier_name"] = "FireControl"

        response = execute_agent_action("¿Cuál es el email del último proveedor registrado?", provider_name="gemini-2.5-flash")

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "list_suppliers")
        self.assertEqual(response["data"]["contact_email"], "pedidos@firecontrol.com")

    def test_previous_supplier_phone_update_prompt_is_covered(self):
        supplier = make_supplier("FireControl", "pedidos@firecontrol.com")
        CONVERSATION_MEMORY["last_supplier_name"] = supplier.name

        response = execute_agent_action(
            "Actualiza el teléfono del proveedor anterior a 654321987",
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "update_supplier")
        self.assertEqual(Supplier.objects.get(name="FireControl").phone, "654321987")

    def test_add_items_to_same_order_prompt_is_covered(self):
        make_product("Filtro HEPA", stock=25, unit_price="35.00")
        make_product("Sensor Térmico", stock=15, unit_price="30.00")
        supplier = make_supplier("FireControl", "pedidos@firecontrol.com")

        first_order = create_purchase_order(
            {
                "supplier_id": str(supplier.id),
                "items": [{"product_name": "Filtro HEPA", "quantity": 20}],
            }
        )
        CONVERSATION_MEMORY["last_purchase_order_id"] = first_order["id"]

        second_response = execute_agent_action(
            "Añade también 10 Sensores Térmicos al mismo pedido",
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(second_response["success"])
        self.assertEqual(second_response["action"], "update_purchase_order")
        order = PurchaseOrder.objects.get(id=first_order["id"])
        self.assertEqual(str(order.supplier.id), str(supplier.id))
        self.assertEqual(len(order.items), 2)
        self.assertEqual(order.items[1]["product_name"], "Sensor Térmico")
        self.assertEqual(order.items[1]["quantity"], 10)

    def test_products_count_prompt_is_covered(self):
        make_product("Detector de Humo", stock=20, unit_price="45.00")
        make_product("Sensor Térmico", stock=15, unit_price="30.00")

        response = execute_agent_action("¿Cuántos productos hay registrados actualmente?", provider_name="gemini-2.5-flash")

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "query_products")
        self.assertEqual(response["data"]["products_count"], 2)

    def test_waste_reasons_deterioro_and_obsolescencia_are_covered(self):
        make_product("Filtro HEPA", stock=25, unit_price="35.00")
        make_product("Sensor Térmico", stock=15, unit_price="30.00")

        deterioro = execute_agent_action(
            "Registra un desecho de 3 unidades de Filtro HEPA por deterioro",
            provider_name="gemini-2.5-flash",
        )
        obsolescencia = execute_agent_action(
            "Registra un desecho de 2 unidades de Sensor Térmico por obsolescencia",
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(deterioro["success"])
        self.assertTrue(obsolescencia["success"])
        self.assertEqual(deterioro["data"]["reason"], "deterioro")
        self.assertEqual(obsolescencia["data"]["reason"], "obsolescencia")

    def test_inventory_analysis_prompts_are_covered(self):
        make_product("Detector de Humo", stock=4, unit_price="45.00")
        make_product("Sensor Térmico", stock=2, unit_price="30.00")
        make_product("Cable Industrial", stock=12, unit_price="5.00")

        low_stock = execute_agent_action("Muéstrame los productos con menos de 5 unidades", provider_name="gemini-2.5-flash")
        expensive = execute_agent_action("Dame los 10 productos más caros", provider_name="gemini-2.5-flash")
        economic_value = execute_agent_action("Calcula el valor económico total del almacén", provider_name="gemini-2.5-flash")
        graph = execute_agent_action("Genera una gráfica de productos con menos stock", provider_name="gemini-2.5-flash")

        self.assertTrue(low_stock["success"])
        self.assertEqual(low_stock["action"], "query_products")
        self.assertEqual(len(low_stock["data"]), 2)
        self.assertTrue(expensive["success"])
        self.assertEqual(expensive["data"][0]["name"], "Detector de Humo")
        self.assertTrue(economic_value["success"])
        self.assertEqual(economic_value["data"]["inventory_value"], 80.0)
        self.assertTrue(graph["success"])
        self.assertEqual(graph["data"]["chart_type"], "inventory_stock")

    def test_automation_prompts_are_covered(self):
        enable_threshold = execute_agent_action(
            "Activa la reposición automática para productos con menos de 5 unidades",
            provider_name="gemini-2.5-flash",
        )
        enable_out_of_stock = execute_agent_action(
            "Genera automáticamente pedidos cuando un producto se quede sin stock",
            provider_name="gemini-2.5-flash",
        )
        disable_alerts = execute_agent_action(
            "Desactiva las alertas automáticas de stock",
            provider_name="gemini-2.5-flash",
        )
        disable_all = execute_agent_action(
            "Desactiva todas las automatizaciones",
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(enable_threshold["success"])
        self.assertTrue(enable_threshold["data"]["enabled"])
        self.assertEqual(enable_threshold["data"]["threshold"], 5)
        self.assertTrue(enable_out_of_stock["success"])
        self.assertEqual(enable_out_of_stock["data"]["threshold"], 1)
        self.assertTrue(disable_alerts["success"])
        self.assertFalse(disable_alerts["data"]["enabled"])
        self.assertTrue(disable_all["success"])
        self.assertFalse(disable_all["data"]["enabled"])


if __name__ == "__main__":
    unittest.main()
