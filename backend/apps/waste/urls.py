from django.urls import path

from apps.waste.views import WasteDetailView, WasteListCreateView

urlpatterns = [
    path("", WasteListCreateView.as_view(), name="waste-list-create"),
    path("<str:record_id>/", WasteDetailView.as_view(), name="waste-detail"),
]
