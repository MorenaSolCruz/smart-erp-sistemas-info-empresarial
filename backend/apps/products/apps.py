from django.apps import AppConfig


class ProductsConfig(AppConfig):
    # Registra el modulo de inventario dentro de Django.
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products"

