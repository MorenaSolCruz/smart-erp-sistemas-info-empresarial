from django.urls import path

from apps.suppliers.views import SupplierDetailView, SupplierListCreateView

urlpatterns = [
    path("", SupplierListCreateView.as_view(), name="supplier-list-create"),
    path("<str:supplier_id>/", SupplierDetailView.as_view(), name="supplier-detail"),
]

