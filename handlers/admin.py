from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_all_pending_users, update_user_role, get_user_by_telegram_id
from keyboards.keyboards import admin_pending_user_keyboard, role_selection_keyboard, main_menu_admin
from utils.helpers import notify_owner

router = Router()


class AdminStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_role_telegram_id = State()


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
