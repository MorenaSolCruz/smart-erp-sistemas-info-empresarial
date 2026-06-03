from django.urls import path

from apps.waste.views import WasteDetailView, WasteListCreateView

urlpatterns = [
    # /api/waste/ lista o crea desechos; /api/waste/<id>/ consulta, edita o borra.
    path("", WasteListCreateView.as_view(), name="waste-list-create"),
    path("<str:record_id>/", WasteDetailView.as_view(), name="waste-detail"),
]
