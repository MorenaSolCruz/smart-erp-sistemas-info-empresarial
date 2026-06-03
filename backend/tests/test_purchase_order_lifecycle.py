# Pruebas del ciclo de vida de pedidos: crear, recibir parcial/total, cancelar
# y ajustar stock segun la operacion.
from datetime import datetime
from decimal import Decimal
import unittest

from apps.llm_agent.providers import MockLLMProvider
from apps.llm_agent.services import execute_agent_action
from apps.products.models import Product
from apps.purchase_orders.models import PurchaseOrder
from apps.suppliers.models import Supplier
from apps.statistics.services import orders_by_supplier


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


class PurchaseOrderLifecycleTests(unittest.TestCase):
    def setUp(self):
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()

    def tearDown(self):
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()

    def test_create_order_registers_pending_order_without_adding_stock(self):
        make_product("Filtro HEPA", stock=5)
        make_supplier("Tecnosur")

        response = execute_agent_action(
            "crea un pedido al proveedor TecnoSur de 8 unidades de filtro hepa",
            provider_name="mock",
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "create_purchase_order")
        self.assertEqual(response["data"]["status"], "pending")
        self.assertEqual(Product.objects.get(name="Filtro HEPA").stock, 5)
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        self.assertEqual(orders_by_supplier()[0]["orders_count"], 1)

    def test_receive_order_marks_it_received_and_adds_products(self):
        make_product("Filtro HEPA", stock=5)
        make_supplier("Tecnosur")
        execute_agent_action(
            "crea un pedido al proveedor TecnoSur de 8 unidades de filtro hepa",
            provider_name="mock",
        )

        response = execute_agent_action(
            "recibimos el pedido del proveedor TecnoSur",
            provider_name="mock",
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "receive_purchase_order")
        self.assertEqual(response["data"]["status"], "received")
        self.assertEqual(Product.objects.get(name="Filtro HEPA").stock, 13)
        self.assertGreaterEqual(len(response["data"]["history"]), 2)

    def test_partial_receipt_keeps_order_open_and_tracks_history(self):
        make_product("Filtro HEPA", stock=5)
        make_supplier("Tecnosur")
        execute_agent_action(
            "crea un pedido al proveedor TecnoSur de 8 unidades de filtro hepa",
            provider_name="mock",
        )

        response = execute_agent_action(
            "recibimos 3 unidades de filtro hepa del pedido del proveedor TecnoSur",
            provider_name="mock",
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["data"]["status"], "partially_received")
        self.assertEqual(Product.objects.get(name="Filtro HEPA").stock, 8)
        self.assertEqual(response["data"]["items"][0]["received_quantity"], 3)
        self.assertEqual(response["data"]["items"][0]["pending_quantity"], 5)
        self.assertEqual(response["data"]["items"][0]["line_status"], "partially_received")
        self.assertEqual(response["data"]["history"][-1]["event"], "partial_receipt")

    def test_cancel_open_order_closes_pending_quantities(self):
        make_product("Filtro HEPA", stock=5)
        make_supplier("Tecnosur")
        execute_agent_action(
            "crea un pedido al proveedor TecnoSur de 8 unidades de filtro hepa",
            provider_name="mock",
        )

        response = execute_agent_action(
            "cancela el pedido del proveedor TecnoSur por rotura",
            provider_name="mock",
        )

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "cancel_purchase_order")
        self.assertEqual(response["data"]["status"], "cancelled")
        self.assertEqual(response["data"]["items"][0]["pending_quantity"], 0)
        self.assertEqual(response["data"]["items"][0]["cancelled_quantity"], 8)
        self.assertEqual(response["data"]["history"][-1]["event"], "cancelled")

    def test_receive_order_parsing_by_supplier(self):
        result = MockLLMProvider().generate_response("recibimos el pedido del proveedor TecnoSur", {})

        self.assertEqual(result["intent"], "receive_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Tecnosur")

    def test_pending_orders_query_only_returns_pending_orders(self):
        make_product("Filtro HEPA", stock=5)
        make_product("Kit Analitico", stock=3)
        make_supplier("Tecnosur")
        make_supplier("Climasur")
        execute_agent_action(
            "crea un pedido al proveedor TecnoSur de 8 unidades de filtro hepa",
            provider_name="mock",
        )
        execute_agent_action(
            "crea un pedido al proveedor ClimaSur de 4 unidades de kit analitico",
            provider_name="mock",
        )
        execute_agent_action(
            "recibimos el pedido del proveedor ClimaSur",
            provider_name="mock",
        )

        response = execute_agent_action("que pedidos faltan por recibir", provider_name="mock")

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "list_purchase_orders")
        self.assertEqual(len(response["data"]), 1)
        self.assertEqual(response["data"][0]["supplier_name"], "Tecnosur")
        self.assertEqual(response["data"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
