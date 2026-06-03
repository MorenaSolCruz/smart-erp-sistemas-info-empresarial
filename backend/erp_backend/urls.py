from django.urls import include, path

urlpatterns = [
    # Mapa general de la API: cada modulo mantiene sus propias rutas internas.
    path("api/products/", include("apps.products.urls")),
    path("api/suppliers/", include("apps.suppliers.urls")),
    path("api/purchase-orders/", include("apps.purchase_orders.urls")),
    path("api/waste/", include("apps.waste.urls")),
    path("api/statistics/", include("apps.statistics.urls")),
    path("api/agent/", include("apps.llm_agent.urls")),
]
