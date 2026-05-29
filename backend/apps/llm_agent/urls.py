from django.urls import path

from apps.llm_agent.views import AgentChatView, AgentMetricsView

urlpatterns = [
    path("chat/", AgentChatView.as_view(), name="agent-chat"),
    path("metrics/", AgentMetricsView.as_view(), name="agent-metrics"),
]
