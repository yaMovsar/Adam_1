from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    get_all_pending_users, get_all_users, update_user_role, get_user_by_telegram_id,
    get_order_by_id, get_all_clients, get_clients_no_tg,
    delete_order, delete_user, update_order_field, create_client_no_tg, link_client_to_user
)
from keyboards.keyboards import (
    admin_pending_user_keyboard, role_selection_keyboard, main_menu_admin,
    order_actions_keyboard, order_edit_keyboard, confirm_delete_keyboard,
    edit_clients_keyboard, link_clients_keyboard, main_menu_client,
    user_manage_keyboard
)
from utils.helpers import notify_owner, format_order_card, parse_deadline

router = Router()


ROLE_LABELS = {
    "admin": "👑 Администратор",
    "manager": "👤 Менеджер",
    "adam": "🔧 Мастер",
    "client": "🛋 Клиент",
    "client_no_tg": "🛋 Клиент (без TG)",
}


class AdminStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_role_telegram_id = State()
    waiting_link_name = State()


class OrderEditStates(StatesGroup):
    waiting_value = State()
    waiting_client = State()
    waiting_new_client_name = State()


@router.message(F.text == "⏳ Ожидают подтверждения")
async def pending_users(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user["role"] != "admin":
        return

    pending = await get_all_pending_users()
    if not pending:
        await message.answer("✅ Нет пользователей, ожидающих подтверждения.")
        return

    for u in pending:
        await message.answer(
            f"👤 {u['name'] or 'Без имени'}\n"
            f"ID: {u['telegram_id']}\n"
            f"Зарегистрирован: {u['created_at'].strftime('%d.%m.%Y %H:%M')}",
            reply_markup=admin_pending_user_keyboard(u["telegram_id"])
        )


@router.callback_query(F.data.startswith("assign_role:"))
async def assign_role_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    telegram_id = int(callback.data.split(":")[1])
    target_user = await get_user_by_telegram_id(telegram_id)

    await state.set_state(AdminStates.waiting_for_name)
    await state.update_data(target_telegram_id=telegram_id)

    await callback.message.answer(
        f"Введите имя для пользователя (текущее: {target_user['name'] or 'не задано'}):\n"
        f"Например: «Рашид Оптовик» или «Магазин Уют»"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_name)
async def assign_role_name(message: Message, state: FSMContext):
    data = await state.get_data()
    telegram_id = data["target_telegram_id"]

    if message.text.strip() == ".":
        target = await get_user_by_telegram_id(telegram_id)
        name = target["name"] if target else message.text.strip()
    else:
        name = message.text.strip()

    await state.update_data(name=name)
    await state.set_state(AdminStates.waiting_for_role_telegram_id)

    await message.answer(
        f"Имя: «{name}»\nВыберите роль:",
        reply_markup=role_selection_keyboard(telegram_id)
    )


@router.callback_query(F.data.startswith("set_role:"))
async def set_role(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    _, telegram_id_str, role = callback.data.split(":")
    telegram_id = int(telegram_id_str)

    data = await state.get_data()
    name = data.get("name", "")

    await update_user_role(telegram_id, name, role)
    await state.clear()

    role_labels = {
        "manager": "Менеджер",
        "adam": "Мастер",
        "client": "Клиент",
    }

    await callback.message.edit_text(
        f"✅ Пользователю назначена роль:\n"
        f"Имя: {name}\n"
        f"Роль: {role_labels.get(role, role)}"
    )

    try:
        await callback.bot.send_message(
            telegram_id,
            f"✅ Ваш доступ подтверждён!\n"
            f"Ваше имя в системе: {name}\n"
            f"Роль: {role_labels.get(role, role)}\n\n"
            f"Напишите /start чтобы начать."
        )
    except Exception:
        pass

    await notify_owner(
        callback.bot,
        f"✅ Назначена роль\n\n"
        f"👤 Имя: {name}\n"
        f"🎭 Роль: {role_labels.get(role, role)}"
    )

    await callback.answer("Роль назначена")


@router.callback_query(F.data.startswith("reject_user:"))
async def reject_user(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    telegram_id = int(callback.data.split(":")[1])

    from database.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM users WHERE telegram_id = $1 AND role = 'pending'",
            telegram_id
        )

    await callback.message.edit_text("❌ Пользователь отклонён.")

    try:
        await callback.bot.send_message(
            telegram_id,
            "❌ Ваш запрос на доступ отклонён. Обратитесь к администратору."
        )
    except Exception:
        pass

    await callback.answer()


# ── Привязка пользователя к существующему клиенту ────────────────────────

@router.callback_query(F.data.startswith("link_user:"))
async def link_user_start(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    telegram_id = int(callback.data.split(":")[1])
    clients = await get_clients_no_tg()

    if not clients:
        await callback.message.answer(
            "❌ Нет клиентов без Telegram для привязки.\n"
            "Сначала создайте заказы для клиента вручную."
        )
        await callback.answer()
        return

    await callback.message.answer(
        "🔗 Выберите клиента, к которому привязать этого пользователя:\n"
        "(будут перенесены все его заказы)",
        reply_markup=link_clients_keyboard(clients, telegram_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("link_to:"))
async def link_to_client_select(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    parts = callback.data.split(":")
    client_no_tg_id, telegram_id = int(parts[1]), int(parts[2])

    from database.db import get_user_by_telegram_id as get_pending
    pending = await get_pending(telegram_id)
    current_name = pending["name"] if pending else ""

    await state.set_state(AdminStates.waiting_link_name)
    await state.update_data(client_no_tg_id=client_no_tg_id, link_telegram_id=telegram_id)
    await callback.message.answer(
        f"Введите имя клиента (текущее: {current_name}):\n"
        f"Или отправьте точку «.» чтобы оставить текущее имя."
    )
    await callback.answer()


@router.message(AdminStates.waiting_link_name)
async def link_name_enter(message: Message, state: FSMContext):
    data = await state.get_data()
    client_no_tg_id = data["client_no_tg_id"]
    telegram_id = data["link_telegram_id"]

    if message.text.strip() == ".":
        pending = await get_user_by_telegram_id(telegram_id)
        name = pending["name"] if pending else message.from_user.full_name
    else:
        name = message.text.strip()

    await link_client_to_user(client_no_tg_id, telegram_id, name)
    await state.clear()

    await message.answer(f"✅ Готово! «{name}» привязан — теперь он видит все свои заказы.")

    try:
        await message.bot.send_message(
            telegram_id,
            f"✅ Ваш доступ подтверждён!\n"
            f"Имя в системе: {name}\n\n"
            f"Напишите /start чтобы увидеть свои заказы."
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("link_cancel:"))
async def link_cancel(callback: CallbackQuery):
    await callback.message.edit_text("❌ Привязка отменена.")
    await callback.answer()


# ── Редактирование заказа ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit_order:"))
async def edit_order_start(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    await callback.message.answer(
        f"✏️ Редактирование заказа {order['order_number']}\nЧто изменить?",
        reply_markup=order_edit_keyboard(order_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def edit_field_select(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    parts = callback.data.split(":")
    order_id, field = int(parts[1]), parts[2]

    if field == "client":
        clients = await get_all_clients()
        await state.set_state(OrderEditStates.waiting_client)
        await state.update_data(order_id=order_id)
        await callback.message.answer(
            "👤 Выберите нового клиента:",
            reply_markup=edit_clients_keyboard(clients)
        )
    else:
        prompts = {
            "description": "📝 Введите новое описание:",
            "color": "🎨 Введите новый цвет:",
            "deadline": "📅 Введите новый срок (например: 20.05 или через 5 дней):",
        }
        await state.set_state(OrderEditStates.waiting_value)
        await state.update_data(order_id=order_id, field=field)
        await callback.message.answer(prompts[field])
    await callback.answer()


@router.message(OrderEditStates.waiting_value)
async def edit_field_value(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id, field = data["order_id"], data["field"]

    if field == "deadline":
        value = parse_deadline(message.text.strip())
        if not value:
            await message.answer("❌ Не понял дату. Попробуйте: 20.05 или «через 5 дней»")
            return
    else:
        value = message.text.strip()

    order = await update_order_field(order_id, field, value)
    await state.clear()
    await message.answer(
        f"✅ Заказ обновлён!\n\n{format_order_card(order)}",
        reply_markup=order_actions_keyboard(order["id"], order["status"], "admin")
    )


@router.callback_query(F.data.startswith("edit_select_client:"))
async def edit_client_select(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client_id = int(callback.data.split(":")[1])
    order = await update_order_field(data["order_id"], "client_id", client_id)
    await state.clear()
    await callback.message.answer(
        f"✅ Клиент обновлён!\n\n{format_order_card(order)}",
        reply_markup=order_actions_keyboard(order["id"], order["status"], "admin")
    )
    await callback.answer()


@router.callback_query(F.data == "edit_new_client")
async def edit_new_client_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderEditStates.waiting_new_client_name)
    await callback.message.answer("Введите имя нового клиента:")
    await callback.answer()


@router.message(OrderEditStates.waiting_new_client_name)
async def edit_new_client_name(message: Message, state: FSMContext):
    data = await state.get_data()
    name = message.text.strip()
    new_client = await create_client_no_tg(name)
    order = await update_order_field(data["order_id"], "client_id", new_client["id"])
    await state.clear()
    await message.answer(
        f"✅ Клиент «{name}» создан и привязан к заказу!\n\n{format_order_card(order)}",
        reply_markup=order_actions_keyboard(order["id"], order["status"], "admin")
    )


@router.callback_query(F.data == "edit_cancel_client")
async def edit_cancel_client(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Выбор клиента отменён.")
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_edit:"))
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()


# ── Удаление заказа ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("delete_order:"))
async def delete_order_start(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    await callback.message.answer(
        f"🗑 Удалить заказ {order['order_number']}?\n"
        f"👤 Клиент: {order.get('client_name') or '—'}\n\n"
        f"⚠️ Это действие нельзя отменить.",
        reply_markup=confirm_delete_keyboard(order_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return
    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)
    order_number = order["order_number"] if order else f"#{order_id}"
    await delete_order(order_id)
    await callback.message.edit_text(f"✅ Заказ {order_number} удалён.")
    await callback.answer()


# ── Список пользователей ──────────────────────────────────────────────────

@router.message(F.text == "👥 Пользователи")
async def all_users(message: Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user["role"] != "admin":
        return

    users = await get_all_users()
    if not users:
        await message.answer("👥 Пользователей пока нет.")
        return

    for u in users:
        role_label = ROLE_LABELS.get(u["role"], u["role"])
        tg = f"@{u['telegram_id']}" if u["telegram_id"] > 0 else "без TG"
        await message.answer(
            f"{role_label}\n"
            f"👤 {u['name'] or 'Без имени'}\n"
            f"🆔 {u['telegram_id']} {tg}",
            reply_markup=user_manage_keyboard(u["telegram_id"])
        )


@router.callback_query(F.data.startswith("change_role:"))
async def change_role_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    telegram_id = int(callback.data.split(":")[1])
    target = await get_user_by_telegram_id(telegram_id)

    await state.set_state(AdminStates.waiting_for_name)
    await state.update_data(target_telegram_id=telegram_id)

    await callback.message.answer(
        f"Введите имя для «{target['name'] or 'без имени'}» (или «.» чтобы оставить):"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_user:"))
async def delete_user_confirm(callback: CallbackQuery):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] != "admin":
        return

    telegram_id = int(callback.data.split(":")[1])
    target = await get_user_by_telegram_id(telegram_id)
    name = target["name"] if target else str(telegram_id)

    await delete_user(telegram_id)
    await callback.message.edit_text(f"✅ Пользователь «{name}» удалён.")
    await callback.answer()
