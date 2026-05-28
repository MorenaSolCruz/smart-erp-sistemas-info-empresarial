import os
import unittest

from rest_framework.test import APIRequestFactory

from apps.llm_agent.services import execute_agent_action
from apps.llm_agent.views import AgentMetricsView
from common.observability import metrics_snapshot, reset_metrics


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        reset_metrics()
        self.factory = APIRequestFactory()

    def test_functional_error_is_classified_and_counted(self):
        response = execute_agent_action("borra el articulo Inventado", provider_name="mock", request_id="req-functional")

        snapshot = metrics_snapshot()
        self.assertFalse(response["success"])
        self.assertEqual(response["error_type"], "functional")
        self.assertEqual(response["request_id"], "req-functional")
        self.assertIn("operation_failure_total|error_code=not_found|error_type=functional|operation=agent_chat", snapshot["counters"])

    def test_technical_error_is_classified_and_counted(self):
        original_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            response = execute_agent_action("muestrame los productos", provider_name="openai", request_id="req-technical")
        finally:
            if original_key is not None:
                os.environ["OPENAI_API_KEY"] = original_key

        snapshot = metrics_snapshot()
        self.assertFalse(response["success"])
        self.assertEqual(response["error_type"], "technical")
        self.assertEqual(response["request_id"], "req-technical")
        self.assertIn("operation_failure_total|error_code=llm_unavailable|error_type=technical|operation=agent_chat", snapshot["counters"])

    def test_metrics_endpoint_returns_snapshot(self):
        execute_agent_action("muestrame los productos", provider_name="mock", request_id="req-metrics")

        request = self.factory.get("/api/agent/metrics/")
        response = AgentMetricsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("generated_at", response.data)
        self.assertIn("counters", response.data)
        self.assertIn("timings", response.data)


if __name__ == "__main__":
    unittest.main()
