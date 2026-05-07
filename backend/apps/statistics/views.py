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
    def get(self, request):
        return Response(statistics_overview())


class LowStockProductsView(APIView):
    def get(self, request):
        return Response(low_stock_products())


class MostWastedProductsView(APIView):
    def get(self, request):
        return Response(most_wasted_products())


class WasteEconomicLossesView(APIView):
    def get(self, request):
        return Response(waste_economic_losses())


class OrdersBySupplierView(APIView):
    def get(self, request):
        return Response(orders_by_supplier())

