"""
server/config.py
----------------
Central configuration for:
- PostgreSQL (main DB)
- SQLite (local DB)

Uses environment variables when available.
"""

import os
from pathlib import Path


# ======================================
# Base Directory
# ======================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ======================================
# PostgreSQL Configuration
# ======================================

POSTGRES_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", 5432)),
    "dbname": os.getenv("PG_DBNAME", "your_database"),
    "user": os.getenv("PG_USER", "postgres"),
    "password": os.getenv("PG_PASSWORD", "your_password"),
}


# ======================================
# SQLite Configuration
# ======================================

SQLITE_CONFIG = {
    "path": BASE_DIR / "local.db"
}


# ======================================
# App Environment
# ======================================

ENVIRONMENT = os.getenv("APP_ENV", "development")
