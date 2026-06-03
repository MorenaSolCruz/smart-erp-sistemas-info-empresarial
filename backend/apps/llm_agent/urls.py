from django.urls import path

from apps.llm_agent.views import AgentChatView, AgentMetricsView

urlpatterns = [
    # chat/ procesa ordenes del usuario; metrics/ permite comprobar salud y observabilidad.
    path("chat/", AgentChatView.as_view(), name="agent-chat"),
    path("metrics/", AgentMetricsView.as_view(), name="agent-metrics"),
]
