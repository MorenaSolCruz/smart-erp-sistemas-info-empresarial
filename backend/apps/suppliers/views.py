from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.suppliers.serializers import SupplierSerializer
from apps.suppliers.services import (
    create_supplier,
    delete_supplier,
    get_supplier_by_id,
    list_suppliers,
    update_supplier,
)


def sanitize_supplier_response(data):
    return {key: value for key, value in data.items() if not key.startswith("_")}


class SupplierListCreateView(APIView):
    def get(self, request):
        return Response(list_suppliers())

    def post(self, request):
        serializer = SupplierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            supplier = create_supplier(serializer.validated_data)
            response_status = (
                status.HTTP_201_CREATED if supplier.get("_sync_status") == "created" else status.HTTP_200_OK
            )
            return Response(sanitize_supplier_response(supplier), status=response_status)
        except NotUniqueError:
            return Response({"detail": "Ya existe un proveedor con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)


class SupplierDetailView(APIView):
    def get(self, request, supplier_id):
        try:
            return Response(get_supplier_by_id(supplier_id))
        except DoesNotExist:
            return Response({"detail": "Proveedor no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, supplier_id):
        serializer = SupplierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(sanitize_supplier_response(update_supplier(supplier_id, serializer.validated_data)))
        except DoesNotExist:
            return Response({"detail": "Proveedor no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except NotUniqueError:
            return Response({"detail": "Ya existe un proveedor con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, supplier_id):
        serializer = SupplierSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(sanitize_supplier_response(update_supplier(supplier_id, serializer.validated_data)))
        except DoesNotExist:
            return Response({"detail": "Proveedor no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except NotUniqueError:
            return Response({"detail": "Ya existe un proveedor con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, supplier_id):
        try:
            return Response(delete_supplier(supplier_id))
        except DoesNotExist:
            return Response({"detail": "Proveedor no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
