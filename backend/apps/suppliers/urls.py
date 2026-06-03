from django.urls import path

from apps.suppliers.views import SupplierDetailView, SupplierListCreateView

urlpatterns = [
    # /api/suppliers/ lista o crea; /api/suppliers/<id>/ consulta, edita o borra.
    path("", SupplierListCreateView.as_view(), name="supplier-list-create"),
    path("<str:supplier_id>/", SupplierDetailView.as_view(), name="supplier-detail"),
]

