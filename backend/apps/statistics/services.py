from collections import defaultdict

from apps.products.models import Product
from apps.purchase_orders.models import PurchaseOrder
from apps.waste.models import WasteRecord
from apps.waste.services import process_expired_products


def low_stock_products(limit=5):
    # Toma los productos con menos unidades para alimentar alertas y KPIs.
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
    # Suma unidades desechadas por producto.
    totals = defaultdict(int)
    for record in WasteRecord.objects:
        totals[record.product.name] += record.quantity

    sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [{"product_name": name, "wasted_quantity": quantity} for name, quantity in sorted_items]


def waste_economic_losses():
    # Suma dinero perdido agrupado por motivo de desecho.
    totals = defaultdict(float)
    for record in WasteRecord.objects:
        totals[record.reason] += float(record.economic_loss)

    return [{"reason": reason, "economic_loss": amount} for reason, amount in totals.items()]


def waste_quantities_by_reason():
    # Suma unidades desechadas agrupadas por motivo.
    totals = defaultdict(int)
    for record in WasteRecord.objects:
        totals[record.reason] += int(record.quantity)

    return [{"reason": reason, "quantity": amount} for reason, amount in totals.items()]


def expiration_waste_summary():
    # Resume el impacto especifico de productos caducados.
    expired_records = list(WasteRecord.objects(reason="caducidad"))
    unique_products = {str(record.product.id) for record in expired_records}
    return {
        "expired_products_count": len(unique_products),
        "expired_units": sum(int(record.quantity) for record in expired_records),
        "expired_economic_loss": sum(float(record.economic_loss) for record in expired_records),
    }


def orders_by_supplier():
    # Calcula volumen de pedidos e importe por proveedor.
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
    # Punto central del dashboard: procesa caducidades y junta todos los indicadores.
    process_expired_products()
    return {
        "low_stock_products": low_stock_products(),
        "most_wasted_products": most_wasted_products(),
        "waste_economic_losses": waste_economic_losses(),
        "waste_quantities_by_reason": waste_quantities_by_reason(),
        "expiration_waste_summary": expiration_waste_summary(),
        "orders_by_supplier": orders_by_supplier(),
    }
