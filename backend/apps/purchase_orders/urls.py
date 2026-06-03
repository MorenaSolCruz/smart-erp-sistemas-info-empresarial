from django.urls import path

from apps.purchase_orders.views import PurchaseOrderDetailView, PurchaseOrderListCreateView

urlpatterns = [
    # /api/purchase-orders/ gestiona coleccion; /api/purchase-orders/<id>/ gestiona uno.
    path("", PurchaseOrderListCreateView.as_view(), name="purchase-order-list-create"),
    path("<str:order_id>/", PurchaseOrderDetailView.as_view(), name="purchase-order-detail"),
]

