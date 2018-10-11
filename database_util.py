from pymongo import MongoClient
from consul_util import get_config_value
import logging

logging.basicConfig(filename='./log/app.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    client = MongoClient(get_config_value('DB_IP').decode(encoding="utf-8"), int(get_config_value('DB_PORT')))
except Exception as e:
    logging.fatal(str(e))


def get_master_collection():
    db = client.botengine.master
    return db


def get_service_collection():
    db = client.botengine.services
    return db
