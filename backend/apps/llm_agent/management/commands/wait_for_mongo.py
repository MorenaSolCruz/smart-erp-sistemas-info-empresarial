from django.core.management.base import BaseCommand

from common.database import wait_for_mongo


class Command(BaseCommand):
    help = "Espera a que MongoDB esté disponible antes de arrancar el backend."

    def handle(self, *args, **options):
        self.stdout.write("Esperando a MongoDB...")
        if wait_for_mongo():
            self.stdout.write(self.style.SUCCESS("MongoDB disponible."))
            return
        raise RuntimeError("No se pudo conectar con MongoDB tras varios intentos.")

