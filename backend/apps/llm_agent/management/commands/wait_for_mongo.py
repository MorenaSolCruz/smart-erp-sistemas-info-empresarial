from django.core.management.base import BaseCommand

from common.database import wait_for_mongo


class Command(BaseCommand):
    # Comando usado en docker-compose para no arrancar Django hasta que MongoDB
    # acepte conexiones. Evita errores intermitentes al levantar contenedores.
    help = "Espera a que MongoDB esté disponible antes de arrancar el backend."

    def handle(self, *args, **options):
        # Si Mongo responde, el siguiente comando puede cargar seed demo y arrancar API.
        self.stdout.write("Esperando a MongoDB...")
        if wait_for_mongo():
            self.stdout.write(self.style.SUCCESS("MongoDB disponible."))
            return
        raise RuntimeError("No se pudo conectar con MongoDB tras varios intentos.")

