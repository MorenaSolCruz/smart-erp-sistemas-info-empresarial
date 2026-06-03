from django.urls import path

from apps.products.views import ProductDetailView, ProductListCreateView

urlpatterns = [
    # /api/products/ lista o crea productos; /api/products/<id>/ opera sobre uno.
    path("", ProductListCreateView.as_view(), name="product-list-create"),
    path("<str:product_id>/", ProductDetailView.as_view(), name="product-detail"),
]

