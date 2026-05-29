from rest_framework.response import Response
from rest_framework.views import APIView

from apps.llm_agent.serializers import ChatRequestSerializer
from apps.llm_agent.services import execute_agent_action
from common.observability import generate_request_id, metrics_snapshot


class AgentChatView(APIView):
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id = request.headers.get("X-Request-Id") or generate_request_id()

        response_data = execute_agent_action(
            message=serializer.validated_data["message"],
            provider_name=serializer.validated_data.get("provider"),
            request_id=request_id,
        )
        return Response(response_data)


class AgentMetricsView(APIView):
    def get(self, request):
        return Response(metrics_snapshot())
