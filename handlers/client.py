from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.db import (
    get_user_by_telegram_id, get_orders_for_client,
    get_archived_orders_for_client, get_order_by_id
)
from keyboards.keyboards import orders_list_keyboard, STATUS_LABELS
from utils.helpers import format_order_card

router = Router()


@router.message(F.text == "📦 Мои заказы")
async def my_orders(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user["role"] != "client":
        return

    orders = await get_orders_for_client(user["id"])
    active = [o for o in orders if o["status"] != "shipped"]

    if not active:
        await message.answer("📭 У вас нет активных заказов.")
        return

    await message.answer(
        f"📦 Ваши активные заказы ({len(active)}):",
        reply_markup=orders_list_keyboard(active, prefix="client_order")
    )


@router.message(F.text == "🗂 Архив")
async def client_archive(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user["role"] != "client":
        return

    orders = await get_archived_orders_for_client(user["id"])
    if not orders:
        await message.answer("📭 Архив пуст.")
        return

    await message.answer(
        f"🗂 Выполненные заказы ({len(orders)}):",
        reply_markup=orders_list_keyboard(orders, prefix="client_archive")
    )


@router.callback_query(F.data.startswith("client_order:"))
async def client_order_detail(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "client":
        return

    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)

    if not order or order["client_id"] != user["id"]:
        await callback.answer("Заказ не найден")
        return

    status = STATUS_LABELS.get(order["status"], order["status"])
    text = (
        f"📦 Заказ {order['order_number']}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 {order['description']}\n"
        f"🎨 Цвет: {order['color']}\n"
        f"📅 Срок: {order['deadline'].strftime('%d.%m.%Y')}\n"
        f"📊 Статус: {status}\n"
        f"🗓 Создан: {order['created_at'].strftime('%d.%m.%Y')}"
    )

    if order.get("photo_file_id"):
        await callback.message.answer_photo(order["photo_file_id"], caption=text)
    else:
        await callback.message.answer(text)

    await callback.answer()


@router.callback_query(F.data.startswith("client_archive:"))
async def client_archive_detail(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "client":
        return

    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)

    if not order or order["client_id"] != user["id"]:
        await callback.answer("Заказ не найден")
        return

    shipped = order["shipped_at"].strftime("%d.%m.%Y") if order.get("shipped_at") else "—"
    created = order["created_at"].strftime("%d.%m.%Y")

    text = (
        f"🗂 Архив • Заказ {order['order_number']}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📝 {order['description']}\n"
        f"🎨 Цвет: {order['color']}\n"
        f"🗓 Создан: {created}\n"
        f"🚚 Отправлен: {shipped}\n"
        f"✅ Выполнен"
    )

    await callback.message.answer(text)
    await callback.answer()
