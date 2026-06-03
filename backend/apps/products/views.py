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
    # Endpoint /api/products/: lista el inventario o crea un producto nuevo.
    def get(self, request):
        # GET devuelve el inventario completo para el panel y para consultas del chat.
        return Response(list_products())

    def post(self, request):
        # POST valida el cuerpo recibido y crea un producto que luego podra usarse
        # en pedidos, desechos y estadisticas.
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = create_product(serializer.validated_data)
            return Response(product, status=status.HTTP_201_CREATED)
        except NotUniqueError:
            return Response({"detail": "Ya existe un producto con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(APIView):
    # Endpoint /api/products/<id>/: opera sobre un producto concreto.
    def get(self, request, product_id):
        # Consulta detalle por ID; si no existe devuelve 404 claro para frontend/agente.
        try:
            return Response(get_product_by_id(product_id))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, product_id):
        # PUT espera el producto completo y lo pasa al servicio de actualizacion.
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(update_product(product_id, serializer.validated_data))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except NotUniqueError:
            return Response({"detail": "Ya existe un producto con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, product_id):
        # PATCH permite cambiar solo algunos campos, por ejemplo stock o precio.
        serializer = ProductSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(update_product(product_id, serializer.validated_data))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except NotUniqueError:
            return Response({"detail": "Ya existe un producto con ese nombre."}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, product_id):
        # El borrado puede eliminar el producto completo o fallar si esta
        # relacionado con pedidos/desechos para proteger la trazabilidad.
        try:
            return Response(delete_product(product_id))
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
