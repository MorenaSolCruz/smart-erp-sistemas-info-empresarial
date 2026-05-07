from mongoengine.errors import DoesNotExist, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.purchase_orders.serializers import PurchaseOrderSerializer
from apps.purchase_orders.services import (
    create_purchase_order,
    delete_purchase_order,
    get_purchase_order_by_id,
    list_purchase_orders,
    update_purchase_order,
)


class PurchaseOrderListCreateView(APIView):
    def get(self, request):
        return Response(list_purchase_orders())

    def post(self, request):
        serializer = PurchaseOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = create_purchase_order(serializer.validated_data)
            return Response(order, status=status.HTTP_201_CREATED)
        except DoesNotExist:
            return Response({"detail": "Proveedor o producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PurchaseOrderDetailView(APIView):
    def get(self, request, order_id):
        try:
            return Response(get_purchase_order_by_id(order_id))
        except DoesNotExist:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, order_id):
        serializer = PurchaseOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(update_purchase_order(order_id, serializer.validated_data))
        except DoesNotExist:
            return Response({"detail": "Pedido, proveedor o producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, order_id):
        return self.put(request, order_id)

    def delete(self, request, order_id):
        try:
            return Response(delete_purchase_order(order_id))
        except DoesNotExist:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
