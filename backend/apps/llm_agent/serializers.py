from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    # Valida el cuerpo enviado por el chat: mensaje obligatorio y proveedor LLM opcional.
    message = serializers.CharField()
    provider = serializers.CharField(required=False, allow_blank=True)

