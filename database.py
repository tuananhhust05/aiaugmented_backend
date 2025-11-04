from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import os

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27018/fastapi_db")
DATABASE_NAME = os.getenv("MONGO_DB", "fastapi_db")

# Async client for FastAPI
client: AsyncIOMotorClient = None
database = None

async def connect_to_mongo():
    """Kết nối đến MongoDB"""
    global client, database
    client = AsyncIOMotorClient(DATABASE_URL)
    database = client[DATABASE_NAME]
    print("Đã kết nối đến MongoDB")

async def close_mongo_connection():
    """Đóng kết nối MongoDB"""
    global client
    if client:
        client.close()
        print("Đã đóng kết nối MongoDB")

def get_database():
    """Lấy database instance"""
    return database
