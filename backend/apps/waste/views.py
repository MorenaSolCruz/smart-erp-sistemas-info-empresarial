from mongoengine.errors import DoesNotExist, ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.waste.serializers import WasteSerializer
from apps.waste.services import (
    create_waste_record,
    delete_waste_record,
    get_waste_record_by_id,
    list_waste_records,
    update_waste_record,
)


class WasteListCreateView(APIView):
    # Endpoint /api/waste/: lista desechos o registra una nueva merma.
    def get(self, request):
        # GET lista mermas y primero procesa caducidades pendientes.
        return Response(list_waste_records())

    def post(self, request):
        # POST registra una merma manual, descuenta stock y calcula perdida.
        serializer = WasteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record = create_waste_record(serializer.validated_data)
            return Response(record, status=status.HTTP_201_CREATED)
        except DoesNotExist:
            return Response({"detail": "Producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class WasteDetailView(APIView):
    # Endpoint /api/waste/<id>/: consulta, corrige o elimina un registro de desecho.
    def get(self, request, record_id):
        # Consulta un desecho concreto por ID completo o prefijo corto.
        try:
            return Response(get_waste_record_by_id(record_id))
        except DoesNotExist:
            return Response({"detail": "Desecho no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, record_id):
        # PUT corrige una merma: el servicio revierte stock anterior y aplica el nuevo.
        serializer = WasteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(update_waste_record(record_id, serializer.validated_data))
        except DoesNotExist:
            return Response({"detail": "Desecho o producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, record_id):
        # En esta API PATCH reutiliza PUT para mantener una unica regla de correccion.
        return self.put(request, record_id)

    def delete(self, request, record_id):
        # Al borrar un desecho, devuelve al stock la cantidad que se habia descontado.
        try:
            return Response(delete_waste_record(record_id))
        except DoesNotExist:
            return Response({"detail": "Desecho no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
