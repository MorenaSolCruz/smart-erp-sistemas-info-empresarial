from django.urls import path

from apps.llm_agent.views import AgentChatView

urlpatterns = [
    path("chat/", AgentChatView.as_view(), name="agent-chat"),
]

