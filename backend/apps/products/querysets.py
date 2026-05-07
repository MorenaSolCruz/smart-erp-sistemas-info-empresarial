from datetime import datetime


def product_queryset(document_cls):
    for product in document_cls.objects:
        if not product.created_at:
            product.created_at = datetime.utcnow()
        if not product.updated_at:
            product.updated_at = datetime.utcnow()
    return document_cls.objects

