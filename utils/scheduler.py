from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
import logging

from config import ADAM_ID, DIGEST_HOUR, DIGEST_MINUTE
from database.db import get_orders_due_soon
from keyboards.keyboards import STATUS_LABELS

logger = logging.getLogger(__name__)


async def send_morning_digest(bot: Bot):
    try:
        orders = await get_orders_due_soon(days=2)
        if not orders:
            await bot.send_message(
                ADAM_ID,
                "🌅 Доброе утро! На ближайшие 2 дня срочных заказов нет."
            )
            return

        text = f"🌅 Доброе утро! Заказы со сроком до 2 дней ({len(orders)}):\n\n"
        for order in orders:
            status = STATUS_LABELS.get(order["status"], order["status"])
            deadline = order["deadline"].strftime("%d.%m.%Y")
            text += (
                f"📦 {order['order_number']} — {order['description'][:40]}\n"
                f"   👤 {order.get('client_name') or '—'} • 📅 {deadline} • {status}\n\n"
            )

        await bot.send_message(ADAM_ID, text)
        logger.info(f"Morning digest sent: {len(orders)} orders")
    except Exception as e:
        logger.error(f"Error sending morning digest: {e}")


def start_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_morning_digest,
        trigger=CronTrigger(hour=DIGEST_HOUR, minute=DIGEST_MINUTE),
        args=[bot],
        id="morning_digest",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started. Digest at {DIGEST_HOUR}:{DIGEST_MINUTE:02d}")
