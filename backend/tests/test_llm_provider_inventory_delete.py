import unittest

from apps.llm_agent.providers import MockLLMProvider


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


if __name__ == "__main__":
    unittest.main()
