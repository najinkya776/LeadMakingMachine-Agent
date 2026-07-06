"""Database configuration for PostgreSQL and Redis."""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# PostgreSQL Configuration
# =============================================================================

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "lead_making_machine"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# =============================================================================
# Redis Configuration
# =============================================================================

REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    "password": os.getenv("REDIS_PASSWORD", None),
}

# =============================================================================
# Queue Names
# =============================================================================

QUEUES = {
    "raw": "leads:raw",
    "qualified": "leads:qualified",
    "auditing": "leads:auditing",
    "scored": "leads:scored",
    "completed": "leads:completed",
    "failed": "leads:failed",
}

# =============================================================================
# Database Helpers
# =============================================================================

def get_db_connection_string():
    """Get PostgreSQL connection string."""
    return f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"


def get_redis_url():
    """Get Redis connection URL."""
    if REDIS_CONFIG["password"]:
        return f"redis://:{REDIS_CONFIG['password']}@{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"
    return f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"