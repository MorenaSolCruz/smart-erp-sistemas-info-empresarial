# Pruebas del proveedor LLM y borrado de inventario: verifican que el agente
# interprete correctamente eliminaciones y ajustes sobre productos.
import unittest

from apps.llm_agent.providers import MockLLMProvider
from apps.llm_agent.services import CONVERSATION_MEMORY, execute_agent_action


class InventoryDeleteParsingTests(unittest.TestCase):
    def setUp(self):
        self.provider = MockLLMProvider()

    def test_delete_specific_article_from_inventory_does_not_clear_everything(self):
        result = self.provider.generate_response("Borra el articulo Tablet del inventario", {})

        self.assertEqual(result["intent"], "delete_product")
        self.assertEqual(result["data"]["name"], "Tablet")

    def test_delete_all_inventory_still_requires_confirmation(self):
        result = self.provider.generate_response("Borra todo el inventario", {})

        self.assertEqual(result["intent"], "confirmation_required")
        self.assertEqual(result["data"]["pending_action"], "delete_all_products")

    def test_delete_all_suppliers_requires_confirmation(self):
        result = self.provider.generate_response("Borra todos los proveedores", {})

        self.assertEqual(result["intent"], "confirmation_required")
        self.assertEqual(result["data"]["pending_action"], "delete_all_suppliers")

    def test_delete_all_purchase_orders_requires_confirmation(self):
        result = self.provider.generate_response("Elimina los pedidos", {})

        self.assertEqual(result["intent"], "confirmation_required")
        self.assertEqual(result["data"]["pending_action"], "delete_all_purchase_orders")

    def test_delete_all_waste_requires_confirmation(self):
        result = self.provider.generate_response("Elimina todos los desechos registrados", {})

        self.assertEqual(result["intent"], "confirmation_required")
        self.assertEqual(result["data"]["pending_action"], "delete_all_waste")

    def test_disable_auto_replenishment_is_not_misread_as_enable(self):
        CONVERSATION_MEMORY["auto_replenishment_enabled"] = True

        response = execute_agent_action("Desactiva la reposicion automatica", provider_name="gemini-2.5-flash")

        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "configure_auto_replenishment")
        self.assertFalse(response["data"]["enabled"])


if __name__ == "__main__":
    unittest.main()
