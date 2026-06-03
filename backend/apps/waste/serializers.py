from rest_framework import serializers


class WasteSerializer(serializers.Serializer):
    """Contrato de desechos.

    Obliga a indicar producto por id o nombre, cantidad positiva y motivo valido.
    La fecha y la perdida economica las calcula el backend para evitar manipulacion.
    """
    id = serializers.CharField(read_only=True)
    product_id = serializers.CharField(required=False, allow_blank=True)
    product_name = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=["caducidad", "producto dañado", "ajuste manual"])
    date = serializers.DateTimeField(read_only=True)
    economic_loss = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

