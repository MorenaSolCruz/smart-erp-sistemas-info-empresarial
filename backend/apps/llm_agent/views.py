from rest_framework.response import Response
from rest_framework.views import APIView

from apps.llm_agent.serializers import ChatRequestSerializer
from apps.llm_agent.services import execute_agent_action


class AgentChatView(APIView):
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_data = execute_agent_action(
            message=serializer.validated_data["message"],
            provider_name=serializer.validated_data.get("provider"),
        )
        return Response(response_data)

