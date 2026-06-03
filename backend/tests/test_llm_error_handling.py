# Pruebas de errores del agente: comprueban respuestas ante fallos del LLM,
# datos incompletos o acciones que no se pueden ejecutar.
import os
import unittest
from unittest.mock import Mock, patch

from apps.llm_agent.providers import LocalLLMProvider
from apps.llm_agent.services import execute_agent_action


class LLMErrorHandlingTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=False)
    def test_missing_openai_key_returns_generic_admin_message(self):
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            response = execute_agent_action("muestrame los productos", provider_name="openai")
        finally:
            if original_key is not None:
                os.environ["OPENAI_API_KEY"] = original_key

        self.assertFalse(response["success"])
        self.assertEqual(response["action"], "fallback")
        self.assertEqual(
            response["reply"],
            "El LLM no pudo procesar la solicitud, contacte con el administrador.",
        )
        self.assertIsNone(response["provider_status"])

    @patch.dict(os.environ, {"LOCAL_LLM_URL": "http://localhost:11434", "LOCAL_LLM_MODEL": "llama3.1:8b"}, clear=False)
    @patch("apps.llm_agent.providers.requests.post")
    def test_local_provider_uses_configured_local_api(self, post_mock):
        post_mock.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={"response": '{"intent":"list_products","reply":"Consulto productos.","data":{}}'}),
        )

        response = LocalLLMProvider().generate_response("muestrame los productos", {})

        self.assertEqual(response["intent"], "list_products")
        self.assertEqual(response["provider_status"], "API local: llama3.1:8b")
        post_mock.assert_called_once()
        self.assertTrue(post_mock.call_args.args[0].endswith("/api/generate"))

    @patch.dict(os.environ, {"LOCAL_LLM_URL": "http://localhost:11434", "LOCAL_LLM_MODEL": "llama3.1:8b"}, clear=False)
    @patch("apps.llm_agent.providers.requests.post")
    def test_local_provider_includes_conversation_context_in_prompt(self, post_mock):
        post_mock.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={"response": '{"intent":"create_purchase_order","reply":"Registro pedido.","data":{}}'}),
        )

        LocalLLMProvider().generate_response(
            "Créale un pedido de 20 Filtro HEPA",
            {"last_supplier_name": "Pepito"},
        )

        prompt = post_mock.call_args.kwargs["json"]["prompt"]
        self.assertIn("ultimo_proveedor: Pepito", prompt)
        self.assertIn("Créale un pedido de 20 Filtro HEPA", prompt)


if __name__ == "__main__":
    unittest.main()
