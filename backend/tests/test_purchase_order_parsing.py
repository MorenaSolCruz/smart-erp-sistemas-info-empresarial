import unittest

from apps.llm_agent.providers import MockLLMProvider


class PurchaseOrderParsingTests(unittest.TestCase):
    def setUp(self):
        self.provider = MockLLMProvider()

    def test_contextual_order_is_not_confused_with_stock_question(self):
        result = self.provider.generate_response("haz un pedido de 8 unidades de filtro hepa", {"last_supplier_name": "TecnoSur"})

        self.assertEqual(result["intent"], "create_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Tecnosur")
        self.assertEqual(result["data"]["items"][0]["product_name"], "Filtro HEPA")
        self.assertEqual(result["data"]["items"][0]["quantity"], 8)

    def test_order_with_explicit_supplier_is_parsed(self):
        result = self.provider.generate_response("haz un pedido a TecnoSur de 8 unidades de filtro hepa", {})

        self.assertEqual(result["intent"], "create_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Tecnosur")
        self.assertEqual(result["data"]["items"][0]["product_name"], "Filtro HEPA")
        self.assertEqual(result["data"]["items"][0]["quantity"], 8)

    def test_create_order_to_supplier_is_parsed(self):
        result = self.provider.generate_response("crea un pedido al proveedor TecnoSur de 8 unidades de filtro hepa", {})

        self.assertEqual(result["intent"], "create_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Tecnosur")
        self.assertEqual(result["data"]["items"][0]["product_name"], "Filtro HEPA")
        self.assertEqual(result["data"]["items"][0]["quantity"], 8)

    def test_create_order_to_supplier_without_unidades_keyword_is_parsed(self):
        result = self.provider.generate_response(
            "crea un pedido al proveedor IndustrialTech de 15 Detectores de Humo",
            {},
        )

        self.assertEqual(result["intent"], "create_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Industrialtech")
        self.assertEqual(result["data"]["items"][0]["product_name"], "Detectores De Humo")
        self.assertEqual(result["data"]["items"][0]["quantity"], 15)

    def test_create_order_to_second_supplier_without_unidades_keyword_is_parsed(self):
        result = self.provider.generate_response(
            "crea un pedido al proveedor ClimaPro de 25 Sensores Térmicos",
            {},
        )

        self.assertEqual(result["intent"], "create_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Climapro")
        self.assertEqual(result["data"]["items"][0]["product_name"], "Sensores Termicos")
        self.assertEqual(result["data"]["items"][0]["quantity"], 25)

    def test_pending_orders_query_is_parsed(self):
        result = self.provider.generate_response("muestra pedidos pendientes", {})

        self.assertEqual(result["intent"], "list_purchase_orders")
        self.assertEqual(result["data"]["status"], "pending")

    def test_partial_receipt_is_parsed(self):
        result = self.provider.generate_response(
            "recibimos 3 unidades de filtro hepa del pedido del proveedor TecnoSur",
            {},
        )

        self.assertEqual(result["intent"], "receive_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Tecnosur")
        self.assertEqual(result["data"]["items"][0]["product_name"], "Filtro HEPA")
        self.assertEqual(result["data"]["items"][0]["quantity"], 3)

    def test_cancel_order_is_parsed(self):
        result = self.provider.generate_response("cancela el pedido del proveedor TecnoSur por rotura", {})

        self.assertEqual(result["intent"], "cancel_purchase_order")
        self.assertEqual(result["data"]["supplier_name"], "Tecnosur")
        self.assertEqual(result["data"]["reason"], "rotura")

    def test_compound_request_is_rejected_instead_of_guessing(self):
        result = self.provider.generate_response(
            "pide 4 filtros y borra 2 monitores si no quedan valvulas",
            {"last_supplier_name": "TecnoSur"},
        )

        self.assertEqual(result["intent"], "missing_data")
        self.assertEqual(result["data"]["reason"], "compound_request")

    def test_multi_target_query_is_rejected(self):
        result = self.provider.generate_response("lista productos y proveedores", {})

        self.assertEqual(result["intent"], "missing_data")
        self.assertEqual(result["data"]["reason"], "multi_target_query")

    def test_inventory_total_value_question_is_parsed(self):
        result = self.provider.generate_response("¿Cuánto vale el inventario total?", {})

        self.assertEqual(result["intent"], "query_products")
        self.assertEqual(result["data"]["kind"], "inventory_value")


if __name__ == "__main__":
    unittest.main()
