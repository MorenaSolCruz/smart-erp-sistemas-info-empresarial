from django.apps import AppConfig


class PurchaseOrdersConfig(AppConfig):
    # Registra el modulo de pedidos de compra dentro de Django.
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.purchase_orders"

