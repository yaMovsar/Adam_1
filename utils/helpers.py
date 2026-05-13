from datetime import date, timedelta
import re
from keyboards.keyboards import STATUS_LABELS


async def notify_owner(bot, text: str):
    from config import OWNER_ID
    if not OWNER_ID:
        return
    try:
        await bot.send_message(OWNER_ID, text)
    except Exception:
        pass


def format_order_card(order, archived=False) -> str:
    status = STATUS_LABELS.get(order["status"], order["status"])
    deadline = order["deadline"].strftime("%d.%m.%Y") if order.get("deadline") else "—"
    created = order["created_at"].strftime("%d.%m.%Y") if order.get("created_at") else "—"

    text = (
        f"📦 Заказ {order['order_number']}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 {order['description']}\n"
        f"🎨 Цвет: {order['color'] or '—'}\n"
        f"👤 Клиент: {order.get('client_name') or '—'}\n"
        f"📅 Срок: {deadline}\n"
        f"📊 Статус: {status}\n"
        f"🗓 Создан: {created}"
    )

    if archived and order.get("shipped_at"):
        shipped = order["shipped_at"].strftime("%d.%m.%Y")
        text += f"\n🚚 Отправлен: {shipped}"

    return text


def parse_deadline(text: str):
    text = text.strip().lower()

    match = re.search(r"через\s+(\d+)\s+дн", text)
    if match:
        days = int(match.group(1))
        return date.today() + timedelta(days=days)

    for fmt in ["%d.%m.%Y", "%d.%m", "%d/%m/%Y", "%d/%m"]:
        try:
            parsed = __import__("datetime").datetime.strptime(text, fmt)
            if fmt in ["%d.%m", "%d/%m"]:
                parsed = parsed.replace(year=date.today().year)
            return parsed.date()
        except ValueError:
            continue

    return None


def calculate_deadline(days: int, work_days: list = None) -> date:
    if work_days is None:
        work_days = [0, 1, 2, 3, 5, 6]

    current = date.today()
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() in work_days:
            added += 1
    return current
