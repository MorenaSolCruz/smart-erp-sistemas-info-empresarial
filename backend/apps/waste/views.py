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
    def get(self, request):
        return Response(list_waste_records())

    def post(self, request):
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
    def get(self, request, record_id):
        try:
            return Response(get_waste_record_by_id(record_id))
        except DoesNotExist:
            return Response({"detail": "Desecho no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, record_id):
        serializer = WasteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            return Response(update_waste_record(record_id, serializer.validated_data))
        except DoesNotExist:
            return Response({"detail": "Desecho o producto no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, record_id):
        return self.put(request, record_id)

    def delete(self, request, record_id):
        try:
            return Response(delete_waste_record(record_id))
        except DoesNotExist:
            return Response({"detail": "Desecho no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
