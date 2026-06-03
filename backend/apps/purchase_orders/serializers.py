from rest_framework import serializers


class PurchaseOrderItemSerializer(serializers.Serializer):
    """Valida cada linea del pedido.

    Cada linea debe apuntar a un producto por id o nombre y llevar cantidad.
    El precio puede venir indicado o tomar el precio actual del producto.
    """
    product_id = serializers.CharField(required=False, allow_blank=True)
    product_name = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class PurchaseOrderSerializer(serializers.Serializer):
    """Contrato principal de pedido de compra para crear o editar pedidos."""
    id = serializers.CharField(read_only=True)
    supplier_id = serializers.CharField()
    items = PurchaseOrderItemSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    received_at = serializers.DateTimeField(read_only=True)
    cancelled_at = serializers.DateTimeField(read_only=True)
    history = serializers.ListField(read_only=True)


class PurchaseOrderReceiptItemSerializer(serializers.Serializer):
    """Contrato para recepciones parciales: producto recibido y cantidad."""
    product_id = serializers.CharField(required=False, allow_blank=True)
    product_name = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)


class PurchaseOrderActionSerializer(serializers.Serializer):
    """Valida acciones especiales sobre pedidos: recibir o cancelar."""
    action = serializers.ChoiceField(choices=["receive", "cancel"])
    received_items = PurchaseOrderReceiptItemSerializer(many=True, required=False)
    reason = serializers.CharField(required=False, allow_blank=True)
