from mongoengine.errors import DoesNotExist, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.purchase_orders.domain import PurchaseOrderDomainError
from apps.purchase_orders.serializers import PurchaseOrderActionSerializer, PurchaseOrderSerializer
from apps.purchase_orders.services import (
    cancel_purchase_order,
    create_purchase_order,
    delete_purchase_order,
    get_purchase_order_by_id,
    list_purchase_orders,
    receive_purchase_order,
    update_purchase_order,
)


class PurchaseOrderListCreateView(APIView):
    def get(self, request):
        return Response(list_purchase_orders(status=request.query_params.get("status")))

    def post(self, request):
        serializer = PurchaseOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = create_purchase_order(serializer.validated_data)
            return Response(order, status=status.HTTP_201_CREATED)
        except DoesNotExist:
            return Response({"detail": "Proveedor o producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except PurchaseOrderDomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
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
        except PurchaseOrderDomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, order_id):
        if request.data.get("action"):
            serializer = PurchaseOrderActionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                action = serializer.validated_data["action"]
                if action == "receive":
                    return Response(
                        receive_purchase_order(order_id, received_items=serializer.validated_data.get("received_items"))
                    )
                return Response(cancel_purchase_order(order_id, reason=serializer.validated_data.get("reason", "")))
            except DoesNotExist:
                return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
            except PurchaseOrderDomainError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except ValidationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self.put(request, order_id)

    def delete(self, request, order_id):
        try:
            return Response(delete_purchase_order(order_id))
        except DoesNotExist:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except PurchaseOrderDomainError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
