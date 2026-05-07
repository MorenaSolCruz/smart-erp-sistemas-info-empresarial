from django.urls import path

from apps.statistics.views import (
    LowStockProductsView,
    MostWastedProductsView,
    OrdersBySupplierView,
    StatisticsOverviewView,
    WasteEconomicLossesView,
)

urlpatterns = [
    path("overview/", StatisticsOverviewView.as_view(), name="statistics-overview"),
    path("low-stock/", LowStockProductsView.as_view(), name="statistics-low-stock"),
    path("most-wasted/", MostWastedProductsView.as_view(), name="statistics-most-wasted"),
    path("waste-losses/", WasteEconomicLossesView.as_view(), name="statistics-waste-losses"),
    path("orders-by-supplier/", OrdersBySupplierView.as_view(), name="statistics-orders-by-supplier"),
]

