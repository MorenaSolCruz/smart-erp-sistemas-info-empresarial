from rest_framework.response import Response
from rest_framework.views import APIView

from apps.statistics.services import (
    low_stock_products,
    most_wasted_products,
    orders_by_supplier,
    statistics_overview,
    waste_economic_losses,
)


class StatisticsOverviewView(APIView):
    # Devuelve el dashboard completo de indicadores para el panel derecho.
    def get(self, request):
        return Response(statistics_overview())


class LowStockProductsView(APIView):
    # Lista productos con menos stock para detectar necesidades de reposicion.
    def get(self, request):
        return Response(low_stock_products())


class MostWastedProductsView(APIView):
    # Agrupa desechos para conocer que productos se desperdician mas.
    def get(self, request):
        return Response(most_wasted_products())


class WasteEconomicLossesView(APIView):
    # Calcula perdidas economicas acumuladas por motivo de desecho.
    def get(self, request):
        return Response(waste_economic_losses())


class OrdersBySupplierView(APIView):
    # Resume cuantos pedidos e importe total tiene cada proveedor.
    def get(self, request):
        return Response(orders_by_supplier())

