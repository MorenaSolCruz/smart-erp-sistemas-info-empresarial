from datetime import datetime


def product_queryset(document_cls):
    """Devuelve productos asegurando fechas basicas.

    Algunos datos antiguos o demo pueden no traer `created_at`/`updated_at`.
    Esta funcion los rellena para que el frontend y estadisticas no muestren
    valores vacios inesperados.
    """
    for product in document_cls.objects:
        if not product.created_at:
            product.created_at = datetime.utcnow()
        if not product.updated_at:
            product.updated_at = datetime.utcnow()
    return document_cls.objects

