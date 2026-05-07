from django.urls import path

from apps.purchase_orders.views import PurchaseOrderDetailView, PurchaseOrderListCreateView

urlpatterns = [
    path("", PurchaseOrderListCreateView.as_view(), name="purchase-order-list-create"),
    path("<str:order_id>/", PurchaseOrderDetailView.as_view(), name="purchase-order-detail"),
]

