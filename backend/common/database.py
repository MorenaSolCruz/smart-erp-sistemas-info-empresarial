import os
import time

from mongoengine import connect
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def connect_to_mongo():
    return connect(
        db=os.getenv("MONGODB_DB_NAME", "erp_llm"),
        host=os.getenv("MONGODB_URI", "mongodb://mongodb:27017/erp_llm"),
        alias="default",
    )


def wait_for_mongo(max_retries=20, delay=2):
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://mongodb:27017/erp_llm")

    for attempt in range(1, max_retries + 1):
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            client.close()
            return True
        except PyMongoError:
            if attempt == max_retries:
                return False
            time.sleep(delay)

