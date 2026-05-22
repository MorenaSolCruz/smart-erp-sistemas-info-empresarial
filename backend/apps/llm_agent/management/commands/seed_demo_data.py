from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from apps.products.models import Product
from apps.products.services import create_product
from apps.purchase_orders.models import PurchaseOrder
from apps.purchase_orders.services import create_purchase_order
from apps.suppliers.models import Supplier
from apps.suppliers.services import create_supplier
from apps.waste.models import WasteRecord
from apps.waste.services import create_waste_record


class Command(BaseCommand):
    help = "Carga datos demo si la base esta vacia."

    def handle(self, *args, **options):
        if any(
            [
                Product.objects.count() > 0,
                Supplier.objects.count() > 0,
                PurchaseOrder.objects.count() > 0,
                WasteRecord.objects.count() > 0,
            ]
        ):
            self.stdout.write("Datos demo omitidos: ya existen registros.")
            return

        now = datetime.utcnow()

        suppliers = [
            create_supplier(
                {
                    "name": "TecnoSur",
                    "contact_email": "compras@tecnosur.com",
                    "phone": "+34 910 000 101",
                    "address": "Madrid",
                    "products_supplied": ["Filtro HEPA", "Sensor Termico"],
                }
            ),
            create_supplier(
                {
                    "name": "ClimaPro",
                    "contact_email": "pedidos@climapro.com",
                    "phone": "+34 910 000 202",
                    "address": "Valencia",
                    "products_supplied": ["Valvula Industrial", "Monitorizacion IoT"],
                }
            ),
            create_supplier(
                {
                    "name": "NovaLab",
                    "contact_email": "supply@novalab.com",
                    "phone": "+34 910 000 303",
                    "address": "Sevilla",
                    "products_supplied": ["Guante Nitrilo", "Kit Analitico"],
                }
            ),
        ]

        create_product(
            {
                "name": "Filtro HEPA",
                "description": "Filtro de alta eficiencia para equipos industriales.",
                "category": "Filtracion",
                "stock": 18,
                "minimum_stock": 12,
                "unit_price": 35,
                "expiration_date": now + timedelta(days=120),
            }
        )
        create_product(
            {
                "name": "Sensor Termico",
                "description": "Sensor para control termico.",
                "category": "Sensores",
                "stock": 7,
                "minimum_stock": 10,
                "unit_price": 22,
                "expiration_date": now + timedelta(days=240),
            }
        )
        create_product(
            {
                "name": "Valvula Industrial",
                "description": "Valvula de repuesto para lineas de produccion.",
                "category": "Mantenimiento",
                "stock": 14,
                "minimum_stock": 8,
                "unit_price": 48,
                "expiration_date": now + timedelta(days=365),
            }
        )
        create_product(
            {
                "name": "Guante Nitrilo",
                "description": "Consumible de proteccion.",
                "category": "Seguridad",
                "stock": 40,
                "minimum_stock": 20,
                "unit_price": 9.5,
                "expiration_date": now - timedelta(days=2),
            }
        )
        create_product(
            {
                "name": "Kit Analitico",
                "description": "Kit de analisis de muestras.",
                "category": "Laboratorio",
                "stock": 9,
                "minimum_stock": 6,
                "unit_price": 27,
                "expiration_date": now + timedelta(days=90),
            }
        )

        create_purchase_order(
            {
                "supplier_id": suppliers[0]["id"],
                "items": [{"product_name": "Filtro HEPA", "quantity": 6, "unit_price": 35}],
            }
        )
        create_purchase_order(
            {
                "supplier_id": suppliers[2]["id"],
                "items": [{"product_name": "Kit Analitico", "quantity": 4, "unit_price": 27}],
            }
        )

        create_waste_record(
            {
                "product_name": "Sensor Termico",
                "quantity": 2,
                "reason": "producto dañado",
            }
        )

        self.stdout.write(self.style.SUCCESS("Datos demo cargados correctamente."))
