import json
from typing import Any, Dict, Optional
from aiogram.fsm.storage.base import BaseStorage, StorageKey


class PostgresStorage(BaseStorage):
    """FSM storage backed by PostgreSQL — survives bot restarts."""

    def __init__(self, pool):
        self._pool = pool

    @classmethod
    async def create(cls, pool):
        storage = cls(pool)
        await storage._init_table()
        return storage

    async def _init_table(self):
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS fsm_storage (
                    key VARCHAR(255) PRIMARY KEY,
                    state VARCHAR(255),
                    data JSONB DEFAULT '{}'
                )
            """)

    def _make_key(self, key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.destiny}"

    async def set_state(self, key: StorageKey, state=None):
        db_key = self._make_key(key)
        state_str = state.state if hasattr(state, "state") else state
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO fsm_storage (key, state)
                VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET state = EXCLUDED.state
            """, db_key, state_str)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        db_key = self._make_key(key)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state FROM fsm_storage WHERE key = $1", db_key
            )
            return row["state"] if row else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]):
        db_key = self._make_key(key)
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO fsm_storage (key, data)
                VALUES ($1, $2::jsonb)
                ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data
            """, db_key, json.dumps(data))

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        db_key = self._make_key(key)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM fsm_storage WHERE key = $1", db_key
            )
            if row and row["data"]:
                return json.loads(row["data"])
            return {}

    async def close(self):
        pass
