from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.serializers import ProductSerializer
from apps.products.services import (
    create_product,
    delete_product,
    get_product_by_id,
    list_products,
    update_product,
)


class ProductListCreateView(APIView):
    def get(self, request):
        return Response(list_products())

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = create_product(serializer.validated_data)
            return Response(product, status=status.HTTP_201_CREATED)
        except NotUniqueError:
            return Response({"detail": "Ya existe un producto con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(APIView):
    def get(self, request, product_id):
        try:
            return Response(get_product_by_id(product_id))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, product_id):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(update_product(product_id, serializer.validated_data))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except NotUniqueError:
            return Response({"detail": "Ya existe un producto con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, product_id):
        serializer = ProductSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(update_product(product_id, serializer.validated_data))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except NotUniqueError:
            return Response({"detail": "Ya existe un producto con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, product_id):
        try:
            return Response(delete_product(product_id))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

