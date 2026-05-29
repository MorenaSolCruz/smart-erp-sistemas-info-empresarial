from datetime import datetime
import unittest

from apps.llm_agent.services import CONVERSATION_MEMORY, execute_agent_action
from apps.products.models import Product
from apps.purchase_orders.models import PurchaseOrder
from apps.suppliers.models import Supplier
from apps.waste.models import WasteRecord


def make_supplier(name):
    now = datetime.utcnow()
    return Supplier(
        name=name,
        contact_email=f"{name.lower()}@mail.test",
        tax_id="",
        phone="",
        address="",
        products_supplied=[],
        created_at=now,
        updated_at=now,
    ).save()


def make_product(name, stock=10, price="5.00"):
    now = datetime.utcnow()
    return Product(
        name=name,
        description="",
        category="",
        stock=stock,
        minimum_stock=0,
        unit_price=price,
        created_at=now,
        updated_at=now,
    ).save()


def make_purchase_order(supplier, product, quantity=2):
    now = datetime.utcnow()
    return PurchaseOrder(
        supplier=supplier,
        items=[
            {
                "product_id": str(product.id),
                "product_name": product.name,
                "quantity": quantity,
                "received_quantity": 0,
                "cancelled_quantity": 0,
                "pending_quantity": quantity,
                "unit_price": float(product.unit_price),
                "reception_history": [],
            }
        ],
        total_amount=float(product.unit_price) * quantity,
        status="pending",
        history=[],
        created_at=now,
        updated_at=now,
    ).save()


def make_waste_record(product, quantity=1):
    now = datetime.utcnow()
    return WasteRecord(
        product=product,
        quantity=quantity,
        reason="caducidad",
        date=now,
        economic_loss=float(product.unit_price) * quantity,
    ).save()


class ConfirmationFlowTests(unittest.TestCase):
    def setUp(self):
        WasteRecord.objects.delete()
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()
        CONVERSATION_MEMORY["pending_action"] = None
        CONVERSATION_MEMORY["last_supplier_name"] = None

    def tearDown(self):
        WasteRecord.objects.delete()
        PurchaseOrder.objects.delete()
        Product.objects.delete()
        Supplier.objects.delete()
        CONVERSATION_MEMORY["pending_action"] = None
        CONVERSATION_MEMORY["last_supplier_name"] = None

    def test_delete_supplier_confirmation_token_executes_without_mock_provider(self):
        make_supplier("Electromalaga")

        first_response = execute_agent_action(
            "Elimina el proveedor ElectroMálaga",
            provider_name="gemini-2.5-flash",
        )

        self.assertFalse(first_response["success"])
        self.assertEqual(first_response["action"], "confirmation_required")
        self.assertIn("confirmation_token", first_response["data"])

        confirmed_response = execute_agent_action(
            first_response["data"]["confirmation_token"],
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(confirmed_response["success"])
        self.assertEqual(confirmed_response["action"], "delete_supplier")
        self.assertTrue(confirmed_response["data"]["deleted"])
        self.assertEqual(Supplier.objects.count(), 0)

    def test_delete_all_suppliers_confirmation_token_executes(self):
        make_supplier("Proveedor Norte")
        make_supplier("Proveedor Sur")

        first_response = execute_agent_action(
            "Borra todos los proveedores",
            provider_name="gemini-2.5-flash",
        )

        self.assertFalse(first_response["success"])
        self.assertEqual(first_response["action"], "confirmation_required")

        confirmed_response = execute_agent_action(
            first_response["data"]["confirmation_token"],
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(confirmed_response["success"])
        self.assertEqual(confirmed_response["action"], "delete_all_suppliers")
        self.assertEqual(Supplier.objects.count(), 0)

    def test_delete_all_purchase_orders_confirmation_token_executes(self):
        supplier = make_supplier("Pedidos Uno")
        product = make_product("Filtro Industrial")
        make_purchase_order(supplier, product)

        first_response = execute_agent_action(
            "Elimina los pedidos",
            provider_name="gemini-2.5-flash",
        )

        self.assertFalse(first_response["success"])
        self.assertEqual(first_response["action"], "confirmation_required")

        confirmed_response = execute_agent_action(
            first_response["data"]["confirmation_token"],
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(confirmed_response["success"])
        self.assertEqual(confirmed_response["action"], "delete_all_purchase_orders")
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_delete_all_waste_confirmation_token_executes(self):
        product = make_product("Detector de humo", stock=12)
        make_waste_record(product, quantity=3)

        first_response = execute_agent_action(
            "Elimina todos los desechos registrados",
            provider_name="gemini-2.5-flash",
        )

        self.assertFalse(first_response["success"])
        self.assertEqual(first_response["action"], "confirmation_required")

        confirmed_response = execute_agent_action(
            first_response["data"]["confirmation_token"],
            provider_name="gemini-2.5-flash",
        )

        self.assertTrue(confirmed_response["success"])
        self.assertEqual(confirmed_response["action"], "delete_all_waste")
        self.assertEqual(WasteRecord.objects.count(), 0)


if __name__ == "__main__":
    unittest.main()
