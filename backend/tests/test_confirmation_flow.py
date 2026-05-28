from datetime import datetime
import unittest

from apps.llm_agent.services import CONVERSATION_MEMORY, execute_agent_action
from apps.suppliers.models import Supplier


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


class ConfirmationFlowTests(unittest.TestCase):
    def setUp(self):
        Supplier.objects.delete()
        CONVERSATION_MEMORY["pending_action"] = None
        CONVERSATION_MEMORY["last_supplier_name"] = None

    def tearDown(self):
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


if __name__ == "__main__":
    unittest.main()
