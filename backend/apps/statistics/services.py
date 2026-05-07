from collections import defaultdict

from apps.products.models import Product
from apps.purchase_orders.models import PurchaseOrder
from apps.waste.models import WasteRecord


def low_stock_products(limit=5):
    products = Product.objects.order_by("stock")[:limit]
    return [
        {
            "product_name": product.name,
            "stock": product.stock,
            "minimum_stock": product.minimum_stock,
        }
        for product in products
    ]


def most_wasted_products(limit=5):
    totals = defaultdict(int)
    for record in WasteRecord.objects:
        totals[record.product.name] += record.quantity

    sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [{"product_name": name, "wasted_quantity": quantity} for name, quantity in sorted_items]


def waste_economic_losses():
    totals = defaultdict(float)
    for record in WasteRecord.objects:
        totals[record.reason] += float(record.economic_loss)

    return [{"reason": reason, "economic_loss": amount} for reason, amount in totals.items()]


def orders_by_supplier():
    totals = defaultdict(lambda: {"orders_count": 0, "total_amount": 0.0})
    for order in PurchaseOrder.objects:
        bucket = totals[order.supplier.name]
        bucket["orders_count"] += 1
        bucket["total_amount"] += float(order.total_amount)

    return [
        {
            "supplier_name": supplier_name,
            "orders_count": values["orders_count"],
            "total_amount": values["total_amount"],
        }
        for supplier_name, values in totals.items()
    ]


def statistics_overview():
    return {
        "low_stock_products": low_stock_products(),
        "most_wasted_products": most_wasted_products(),
        "waste_economic_losses": waste_economic_losses(),
        "orders_by_supplier": orders_by_supplier(),
    }

