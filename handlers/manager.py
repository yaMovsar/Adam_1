from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta

from config import ADAM_ID
from database.db import (
    get_user_by_telegram_id, get_all_clients, create_order, create_client_no_tg,
    get_active_orders, get_archived_orders, get_order_by_id,
    update_order_status
)
from keyboards.keyboards import (
    main_menu_manager, main_menu_admin, clients_keyboard, orders_list_keyboard,
    order_actions_keyboard, STATUS_LABELS
)
from utils.helpers import format_order_card, parse_deadline, calculate_deadline, notify_owner

router = Router()


class OrderStates(StatesGroup):
    waiting_photo = State()
    waiting_color = State()
    waiting_description = State()
    waiting_client = State()
    waiting_new_client_name = State()
    waiting_deadline = State()
    waiting_extend_reason = State()
    waiting_extend_date = State()


async def check_role(telegram_id: int, allowed_roles: list):
    user = await get_user_by_telegram_id(telegram_id)
    return user and user["role"] in allowed_roles


@router.message(F.text == "➕ Новый заказ")
async def new_order_start(message: Message, state: FSMContext):
    if not await check_role(message.from_user.id, ["manager", "admin"]):
        return
    await state.set_state(OrderStates.waiting_photo)
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    skip_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ Без фото")]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer("📷 Отправьте фото изделия:", reply_markup=skip_kb)


@router.message(OrderStates.waiting_photo, F.photo)
async def order_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_id)
    await state.set_state(OrderStates.waiting_color)
    await message.answer("🎨 Укажите цвет:")


@router.message(OrderStates.waiting_photo, F.text == "⏭ Без фото")
async def order_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=None)
    await state.set_state(OrderStates.waiting_color)
    await message.answer("🎨 Укажите цвет:")


@router.message(OrderStates.waiting_color)
async def order_color(message: Message, state: FSMContext):
    await state.update_data(color=message.text.strip())
    await state.set_state(OrderStates.waiting_description)
    await message.answer("📝 Введите описание заказа (тип, размеры, особенности):")


@router.message(OrderStates.waiting_description)
async def order_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(OrderStates.waiting_client)

    clients = await get_all_clients()
    if clients:
        await message.answer(
            "👤 Выберите клиента:",
            reply_markup=clients_keyboard(clients)
        )
    else:
        await message.answer(
            "👤 Клиентов пока нет. Введите имя нового клиента:"
        )
        await state.set_state(OrderStates.waiting_new_client_name)


@router.callback_query(OrderStates.waiting_client, F.data.startswith("select_client:"))
async def select_client(callback: CallbackQuery, state: FSMContext):
    client_id = int(callback.data.split(":")[1])
    await state.update_data(client_id=client_id)
    await state.set_state(OrderStates.waiting_deadline)
    await callback.message.answer(
        "📅 Укажите срок выполнения (например: 15.05 или через 3 дня):"
    )
    await callback.answer()


@router.callback_query(OrderStates.waiting_client, F.data == "new_client")
async def new_client_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.waiting_new_client_name)
    await callback.message.answer("Введите имя нового клиента:")
    await callback.answer()


@router.message(OrderStates.waiting_new_client_name)
async def new_client_name(message: Message, state: FSMContext):
    name = message.text.strip()
    new_client = await create_client_no_tg(name)

    await state.update_data(client_id=new_client["id"])
    await state.set_state(OrderStates.waiting_deadline)
    await message.answer(
        f"✅ Клиент «{name}» добавлен.\n"
        f"📅 Укажите срок выполнения (например: 15.05 или через 3 дня):"
    )


@router.message(OrderStates.waiting_deadline)
async def order_deadline(message: Message, state: FSMContext):
    deadline = parse_deadline(message.text.strip())
    if not deadline:
        await message.answer(
            "❌ Не понял дату. Попробуйте: 15.05 или 15.05.2025 или «через 3 дня»"
        )
        return

    data = await state.get_data()
    user = await get_user_by_telegram_id(message.from_user.id)

    order = await create_order(
        description=data["description"],
        color=data["color"],
        photo_file_id=data.get("photo_file_id"),
        client_id=data["client_id"],
        manager_id=user["id"],
        deadline=deadline,
    )

    await state.clear()

    text = format_order_card(order)
    menu = main_menu_admin() if user["role"] == "admin" else main_menu_manager()
    await message.answer(f"✅ Заказ создан!\n\n{text}", reply_markup=menu)

    await notify_owner(
        message.bot,
        f"🆕 Создан новый заказ\n\n{text}\n\n👨‍💼 Менеджер: {user['name']}"
    )

    try:
        await message.bot.send_message(
            ADAM_ID,
            f"🆕 Новый заказ!\n\n{text}",
            reply_markup=order_actions_keyboard(order["id"], order["status"], "adam")
        )
        if data.get("photo_file_id"):
            await message.bot.send_photo(ADAM_ID, data["photo_file_id"])
    except Exception:
        pass


@router.message(F.text == "📋 Активные заказы")
async def active_orders(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user["role"] not in ["manager", "admin", "adam"]:
        return

    orders = await get_active_orders()
    if not orders:
        await message.answer("📭 Активных заказов нет.")
        return

    await message.answer(
        f"📋 Активные заказы ({len(orders)}):",
        reply_markup=orders_list_keyboard(orders)
    )


@router.message(F.text == "🗂 Архив")
async def archive(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user["role"] not in ["manager", "admin", "adam"]:
        return

    orders = await get_archived_orders()
    if not orders:
        await message.answer("📭 Архив пуст.")
        return

    await message.answer(
        f"🗂 Архив ({len(orders)} заказов):",
        reply_markup=orders_list_keyboard(orders, prefix="archive")
    )


@router.callback_query(F.data.startswith("order_detail:"))
async def order_detail(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] not in ["manager", "admin", "adam"]:
        return

    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден")
        return

    text = format_order_card(order)

    if order.get("photo_file_id"):
        await callback.message.answer_photo(
            order["photo_file_id"],
            caption=text,
            reply_markup=order_actions_keyboard(order["id"], order["status"], user["role"])
        )
    else:
        await callback.message.answer(
            text,
            reply_markup=order_actions_keyboard(order["id"], order["status"], user["role"])
        )
    await callback.answer()


@router.callback_query(F.data.startswith("archive_detail:"))
async def archive_detail(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    if not order:
        await callback.answer("Заказ не найден")
        return

    text = format_order_card(order, archived=True)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data.startswith("set_status:"))
async def set_status(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] not in ["manager", "admin", "adam"]:
        return

    _, order_id_str, new_status = callback.data.split(":")
    order_id = int(order_id_str)

    order = await update_order_status(order_id, new_status, user["id"])
    label = STATUS_LABELS.get(new_status, new_status)

    await callback.message.edit_caption(
        caption=format_order_card(order) if order.get("photo_file_id") else None
    ) if order.get("photo_file_id") else None

    await callback.answer(f"✅ Статус: {label}")
    await callback.message.answer(
        f"✅ Статус заказа {order['order_number']} обновлён: {label}",
        reply_markup=order_actions_keyboard(order["id"], order["status"], user["role"])
    )

    await notify_owner(
        callback.bot,
        f"📊 Статус заказа обновлён\n\n"
        f"📦 Заказ {order['order_number']}\n"
        f"👤 Клиент: {order.get('client_name') or '—'}\n"
        f"📊 Новый статус: {label}\n"
        f"👨‍💼 Кем: {user['name']}"
    )

    if new_status in ["ready", "shipped"]:
        client_tg_id = order.get("client_telegram_id")
        if client_tg_id and client_tg_id > 0:
            msg = (
                f"📦 Ваш заказ {order['order_number']} готов к выдаче!"
                if new_status == "ready"
                else f"🚚 Ваш заказ {order['order_number']} отправлен!"
            )
            try:
                await callback.bot.send_message(client_tg_id, msg)
            except Exception:
                pass
