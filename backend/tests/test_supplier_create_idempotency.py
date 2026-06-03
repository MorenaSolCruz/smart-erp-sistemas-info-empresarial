# Pruebas de proveedores: comprueban que crear un proveedor existente no duplique
# registros y actualice datos cuando corresponde.
from datetime import datetime, timedelta
import unittest

from apps.llm_agent.services import CONVERSATION_MEMORY, execute_agent_action
from apps.suppliers.models import Supplier


def make_supplier(name, email, phone="", updated_at=None):
    timestamp = updated_at or datetime.utcnow()
    return Supplier(
        name=name,
        contact_email=email,
        tax_id="",
        phone=phone,
        address="",
        products_supplied=[],
        created_at=timestamp,
        updated_at=timestamp,
    ).save()


def normalized_mongo_datetime(value):
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


class SupplierCreateIdempotencyTests(unittest.TestCase):
    def setUp(self):
        Supplier.objects.delete()
        CONVERSATION_MEMORY["last_supplier_name"] = None
        CONVERSATION_MEMORY["pending_action"] = None

    def tearDown(self):
        Supplier.objects.delete()
        CONVERSATION_MEMORY["last_supplier_name"] = None
        CONVERSATION_MEMORY["pending_action"] = None

    def test_create_supplier_reports_existing_when_same_data_is_sent(self):
        original_timestamp = datetime.utcnow() - timedelta(days=1)
        existing_supplier = make_supplier("Proveedorsyncuno", "sync1@test.com", updated_at=original_timestamp)
        baseline_updated_at = normalized_mongo_datetime(existing_supplier.updated_at)

        response = execute_agent_action(
            "registra un proveedor llamado ProveedorSyncUno con email sync1@test.com",
            provider_name="mock",
        )

        supplier = Supplier.objects.get(name="Proveedorsyncuno")
        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "create_supplier")
        self.assertIn("ya existia", response["reply"].lower())
        self.assertIn("no ha sido necesario aplicar cambios", response["reply"].lower())
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(supplier.contact_email, "sync1@test.com")
        self.assertEqual(normalized_mongo_datetime(supplier.updated_at), baseline_updated_at)

    def test_create_supplier_updates_existing_record_when_new_data_differs(self):
        original_timestamp = datetime.utcnow() - timedelta(days=1)
        make_supplier("Proveedorsyncdos", "sync-old@test.com", updated_at=original_timestamp)

        response = execute_agent_action(
            "registra un proveedor llamado ProveedorSyncDos con email sync-new@test.com telefono 600 123 123",
            provider_name="mock",
        )

        supplier = Supplier.objects.get(name="Proveedorsyncdos")
        self.assertTrue(response["success"])
        self.assertEqual(response["action"], "create_supplier")
        self.assertIn("ya existia", response["reply"].lower())
        self.assertIn("actualizado", response["reply"].lower())
        self.assertEqual(Supplier.objects.count(), 1)
        self.assertEqual(supplier.contact_email, "sync-new@test.com")
        self.assertEqual(supplier.phone, "600 123 123")
        self.assertGreater(supplier.updated_at, original_timestamp)


if __name__ == "__main__":
    unittest.main()
