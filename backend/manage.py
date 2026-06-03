#!/usr/bin/env python
"""Entrada de comandos Django.

Se usa para arrancar el servidor, ejecutar comandos propios como wait_for_mongo
y seed_demo_data, y correr pruebas o tareas de mantenimiento del backend.
"""
import os
import sys


def main():
    # Indica a Django que cargue la configuracion principal del ERP antes de
    # ejecutar cualquier comando recibido por terminal o por docker-compose.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erp_backend.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

