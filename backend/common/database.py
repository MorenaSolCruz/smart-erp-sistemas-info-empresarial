import os
import time

from mongoengine import connect
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def connect_to_mongo():
    """Abre la conexion principal MongoEngine usada por todos los modelos.

    El ERP no usa la base de datos relacional de Django; por eso los modelos
    de productos, proveedores, pedidos, desechos y auditoria se conectan a
    MongoDB mediante este alias `default`.
    """
    return connect(
        db=os.getenv("MONGODB_DB_NAME", "erp_llm"),
        host=os.getenv("MONGODB_URI", "mongodb://mongodb:27017/erp_llm"),
        alias="default",
    )


def wait_for_mongo(max_retries=20, delay=2):
    """Espera hasta que MongoDB responda antes de arrancar Django.

    docker-compose puede iniciar el backend antes de que la base de datos acepte
    conexiones. Este metodo hace pings repetidos para evitar que seed_demo_data
    o runserver fallen por arrancar demasiado pronto.
    """
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/erp_llm")

    for attempt in range(1, max_retries + 1):
        try:
            # Se usa PyMongo directo para hacer un ping de infraestructura,
            # independiente de los documentos MongoEngine del ERP.
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            client.close()
            return True
        except PyMongoError:
            if attempt == max_retries:
                # Si se agotan intentos, el comando de gestion puede avisar
                # que MongoDB no esta disponible.
                return False
            time.sleep(delay)

