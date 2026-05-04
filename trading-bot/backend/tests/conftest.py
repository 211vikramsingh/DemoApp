"""
Root conftest — sets environment variables for the entire test suite.
Uses SQLite in-memory via aiosqlite so no PostgreSQL/asyncpg is needed.
"""
import os

# Must be set before any app imports so pydantic-settings picks them up
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-bytes-minimum!")
os.environ.setdefault("ENCRYPTION_KEY", "a" * 64)  # 64 hex chars = 32 bytes
os.environ.setdefault("KITE_API_KEY", "test_kite_key")
os.environ.setdefault("KITE_API_SECRET", "test_kite_secret")
os.environ.setdefault("DELTA_API_KEY", "test_delta_key")
os.environ.setdefault("DELTA_API_SECRET", "test_delta_secret")
os.environ.setdefault("DELTA_BASE_URL", "https://api.delta.exchange")
