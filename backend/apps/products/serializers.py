from rest_framework import serializers


class ProductSerializer(serializers.Serializer):
    """Contrato de datos del producto para la API.

    Valida que el frontend/agente no mande stock negativo, precio mal formado
    o campos fuera de lo esperado. Esto protege al servicio antes de guardar.
    """
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.CharField(required=False, allow_blank=True, default="")
    stock = serializers.IntegerField(min_value=0)
    minimum_stock = serializers.IntegerField(min_value=0, required=False, default=0)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    expiration_date = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

