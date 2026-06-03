import os

from django.core.asgi import get_asgi_application

# Punto de entrada ASGI. Django lo usa si se despliega con servidores asincronos.
# En esta demo se usa principalmente runserver, pero el archivo forma parte del
# esqueleto estandar de proyectos Django.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erp_backend.settings")

application = get_asgi_application()

