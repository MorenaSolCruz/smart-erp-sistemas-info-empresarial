from rest_framework import serializers


class PurchaseOrderItemSerializer(serializers.Serializer):
    product_id = serializers.CharField(required=False, allow_blank=True)
    product_name = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class PurchaseOrderSerializer(serializers.Serializer):
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
    product_id = serializers.CharField(required=False, allow_blank=True)
    product_name = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)


class PurchaseOrderActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["receive", "cancel"])
    received_items = PurchaseOrderReceiptItemSerializer(many=True, required=False)
    reason = serializers.CharField(required=False, allow_blank=True)
