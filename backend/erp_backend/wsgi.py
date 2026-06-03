import os

from django.core.wsgi import get_wsgi_application

# Punto de entrada WSGI. Sirve para desplegar Django en servidores tradicionales
# y apunta a la misma configuracion `settings.py` que usa runserver.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erp_backend.settings")

application = get_wsgi_application()

