import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                name VARCHAR(255),
                role VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_number VARCHAR(20) UNIQUE NOT NULL,
                description TEXT NOT NULL,
                color VARCHAR(100),
                photo_file_id VARCHAR(255),
                client_id INTEGER REFERENCES users(id),
                manager_id INTEGER REFERENCES users(id),
                deadline DATE NOT NULL,
                status VARCHAR(50) DEFAULT 'accepted',
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                shipped_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS order_extensions (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                old_deadline DATE NOT NULL,
                new_deadline DATE NOT NULL,
                reason TEXT NOT NULL,
                extended_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS order_status_log (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                old_status VARCHAR(50),
                new_status VARCHAR(50),
                changed_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
    logger.info("Database initialized")


async def get_user_by_telegram_id(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )


async def create_user(telegram_id: int, name: str = None, role: str = "pending"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """INSERT INTO users (telegram_id, name, role)
               VALUES ($1, $2, $3)
               ON CONFLICT (telegram_id) DO UPDATE SET name = EXCLUDED.name
               RETURNING *""",
            telegram_id, name, role
        )


async def update_user_name(telegram_id: int, name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "UPDATE users SET name = $1 WHERE telegram_id = $2 RETURNING *",
            name, telegram_id
        )


async def update_user_role(telegram_id: int, name: str, role: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """UPDATE users SET name = $1, role = $2
               WHERE telegram_id = $3 RETURNING *""",
            name, role, telegram_id
        )


async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM users WHERE role != 'pending' ORDER BY role, name"
        )


async def delete_user(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE telegram_id = $1", telegram_id)


async def get_all_pending_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM users WHERE role = 'pending' ORDER BY created_at"
        )


async def get_all_clients():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM users WHERE role IN ('client', 'client_no_tg') ORDER BY name"
        )


async def get_clients_no_tg():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM users WHERE role = 'client_no_tg' ORDER BY name"
        )


async def link_client_to_user(client_no_tg_id: int, telegram_id: int, name: str):
    """Привязывает реального Telegram-пользователя к существующему клиенту без TG.
    Удаляет pending-запись, обновляет client_no_tg запись реальным telegram_id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM users WHERE telegram_id = $1 AND role = 'pending'",
            telegram_id
        )
        return await conn.fetchrow(
            """UPDATE users SET telegram_id = $1, name = $2, role = 'client'
               WHERE id = $3 RETURNING *""",
            telegram_id, name, client_no_tg_id
        )


async def create_client_no_tg(name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        min_id = await conn.fetchval(
            "SELECT COALESCE(MIN(telegram_id), 0) FROM users WHERE telegram_id < 0"
        )
        new_tg_id = min_id - 1
        return await conn.fetchrow(
            """INSERT INTO users (telegram_id, name, role)
               VALUES ($1, $2, 'client_no_tg')
               RETURNING *""",
            new_tg_id, name
        )


async def create_order(description, color, photo_file_id, client_id, manager_id, deadline):
    pool = await get_pool()
    async with pool.acquire() as conn:
        max_num = await conn.fetchval(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(order_number FROM 2) AS INTEGER)), 0) FROM orders"
        )
        order_number = f"#{str(max_num + 1).zfill(4)}"
        return await conn.fetchrow(
            """INSERT INTO orders
               (order_number, description, color, photo_file_id, client_id, manager_id, deadline, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'accepted')
               RETURNING *""",
            order_number, description, color, photo_file_id, client_id, manager_id, deadline
        )


async def get_order_by_id(order_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """SELECT o.*, 
                      c.name as client_name, c.telegram_id as client_telegram_id,
                      m.name as manager_name
               FROM orders o
               LEFT JOIN users c ON o.client_id = c.id
               LEFT JOIN users m ON o.manager_id = m.id
               WHERE o.id = $1""",
            order_id
        )


async def get_active_orders():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*,
                      c.name as client_name,
                      m.name as manager_name
               FROM orders o
               LEFT JOIN users c ON o.client_id = c.id
               LEFT JOIN users m ON o.manager_id = m.id
               WHERE o.status != 'shipped'
               ORDER BY o.deadline ASC"""
        )


async def get_active_orders_adam():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*,
                      c.name as client_name,
                      m.name as manager_name
               FROM orders o
               LEFT JOIN users c ON o.client_id = c.id
               LEFT JOIN users m ON o.manager_id = m.id
               WHERE o.status IN ('accepted', 'in_production')
               ORDER BY o.deadline ASC"""
        )


async def get_orders_for_client(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*, m.name as manager_name
               FROM orders o
               LEFT JOIN users m ON o.manager_id = m.id
               WHERE o.client_id = $1
               ORDER BY o.created_at DESC""",
            client_id
        )


async def get_orders_due_soon(days: int = 2):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*, 
                      c.name as client_name,
                      c.telegram_id as client_telegram_id
               FROM orders o
               LEFT JOIN users c ON o.client_id = c.id
               WHERE o.status != 'shipped'
                 AND o.deadline <= CURRENT_DATE + $1
               ORDER BY o.deadline ASC""",
            days
        )


async def update_order_status(order_id: int, new_status: str, changed_by_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow("SELECT status FROM orders WHERE id = $1", order_id)
        old_status = order["status"] if order else None

        updates = {"status": new_status}
        if new_status == "ready":
            await conn.execute(
                "UPDATE orders SET status = $1, completed_at = NOW() WHERE id = $2",
                new_status, order_id
            )
        elif new_status == "shipped":
            await conn.execute(
                "UPDATE orders SET status = $1, shipped_at = NOW() WHERE id = $2",
                new_status, order_id
            )
        else:
            await conn.execute(
                "UPDATE orders SET status = $1 WHERE id = $2",
                new_status, order_id
            )

        await conn.execute(
            """INSERT INTO order_status_log (order_id, old_status, new_status, changed_by)
               VALUES ($1, $2, $3, $4)""",
            order_id, old_status, new_status, changed_by_id
        )
        return await get_order_by_id(order_id)


async def extend_order_deadline(order_id: int, new_deadline, reason: str, extended_by_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow("SELECT deadline FROM orders WHERE id = $1", order_id)
        old_deadline = order["deadline"]

        await conn.execute(
            "UPDATE orders SET deadline = $1 WHERE id = $2",
            new_deadline, order_id
        )
        await conn.execute(
            """INSERT INTO order_extensions (order_id, old_deadline, new_deadline, reason, extended_by)
               VALUES ($1, $2, $3, $4, $5)""",
            order_id, old_deadline, new_deadline, reason, extended_by_id
        )
        return await get_order_by_id(order_id)


async def delete_order(order_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM order_extensions WHERE order_id = $1", order_id)
        await conn.execute("DELETE FROM order_status_log WHERE order_id = $1", order_id)
        await conn.execute("DELETE FROM orders WHERE id = $1", order_id)


async def update_order_field(order_id: int, field: str, value):
    allowed = {"description", "color", "deadline", "client_id"}
    if field not in allowed:
        raise ValueError(f"Invalid field: {field}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE orders SET {field} = $1 WHERE id = $2", value, order_id)
        return await get_order_by_id(order_id)


async def get_archived_orders():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*,
                      c.name as client_name,
                      m.name as manager_name
               FROM orders o
               LEFT JOIN users c ON o.client_id = c.id
               LEFT JOIN users m ON o.manager_id = m.id
               WHERE o.status = 'shipped'
               ORDER BY o.shipped_at DESC
               LIMIT 50"""
        )


async def get_archived_orders_for_client(client_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT o.*, m.name as manager_name
               FROM orders o
               LEFT JOIN users m ON o.manager_id = m.id
               WHERE o.client_id = $1 AND o.status = 'shipped'
               ORDER BY o.shipped_at DESC""",
            client_id
        )
