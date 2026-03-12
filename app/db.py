import os
from typing import Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "journal_service")
MONGODB_JOURNAL_COLLECTION = os.getenv("MONGODB_JOURNAL_COLLECTION", "journal_entries")
MONGODB_USER_COLLECTION = os.getenv("MONGODB_USER_COLLECTION", "users")
MONGODB_SESSION_COLLECTION = os.getenv("MONGODB_SESSION_COLLECTION", "sessions")

_client: Optional[MongoClient] = None
_database: Optional[Database] = None


def initialize_database() -> None:
    global _client, _database

    if _client is not None:
        return

    _client = MongoClient(MONGODB_URL)
    _client.admin.command("ping")
    _database = _client[MONGODB_DB_NAME]
    _database[MONGODB_JOURNAL_COLLECTION].create_index(
        [("userId", ASCENDING), ("documentType", ASCENDING)],
        name="user_document_type_idx",
    )
    _database[MONGODB_USER_COLLECTION].create_index(
        [("email", ASCENDING)],
        name="email_unique_idx",
        unique=True,
    )
    _database[MONGODB_SESSION_COLLECTION].create_index(
        [("token", ASCENDING)],
        name="token_unique_idx",
        unique=True,
    )
    _database[MONGODB_SESSION_COLLECTION].create_index(
        [("userId", ASCENDING), ("createdAt", DESCENDING)],
        name="session_user_created_at_idx",
    )


def close_database() -> None:
    global _client, _database

    if _client is None:
        return

    _client.close()
    _client = None
    _database = None


def get_journal_collection() -> Collection:
    if _database is None:
        raise RuntimeError("Database is not initialized. Call initialize_database() first.")

    return _database[MONGODB_JOURNAL_COLLECTION]


def get_user_collection() -> Collection:
    if _database is None:
        raise RuntimeError("Database is not initialized. Call initialize_database() first.")

    return _database[MONGODB_USER_COLLECTION]


def get_session_collection() -> Collection:
    if _database is None:
        raise RuntimeError("Database is not initialized. Call initialize_database() first.")

    return _database[MONGODB_SESSION_COLLECTION]
