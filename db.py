from motor.motor_asyncio import AsyncIOMotorClient
from passlib.handlers import mysql

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "list/data"


client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
