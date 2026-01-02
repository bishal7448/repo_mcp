from pymongo import MongoClient
from app.core.config import settings

class MongoDBClient:
    def __init__(self):
        self.client = MongoClient(settings.MONGODB_URI)

    def get_client(self):
        return self.client
    
mongodb_client = MongoDBClient()
