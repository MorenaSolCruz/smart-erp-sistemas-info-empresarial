from rest_framework import serializers


class SupplierSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=120)
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    tax_id = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    products_supplied = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

