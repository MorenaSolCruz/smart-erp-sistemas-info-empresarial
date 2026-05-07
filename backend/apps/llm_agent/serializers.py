from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    provider = serializers.CharField(required=False, allow_blank=True)

