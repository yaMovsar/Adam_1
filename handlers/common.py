from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from config import ADMIN_ID
from database.db import get_user_by_telegram_id, create_user
from keyboards.keyboards import (
    main_menu_admin, main_menu_manager,
    main_menu_adam, main_menu_client
)
from utils.helpers import notify_owner

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    telegram_id = message.from_user.id
    user = await get_user_by_telegram_id(telegram_id)

    if telegram_id == ADMIN_ID:
        if not user:
            await create_user(telegram_id, message.from_user.full_name, "admin")
        await message.answer(
            f"👑 Добро пожаловать, администратор!\n"
            f"Управляйте пользователями и заказами.",
            reply_markup=main_menu_admin()
        )
        return

    if not user:
        await create_user(telegram_id, message.from_user.full_name, "pending")
        await message.answer(
            "👋 Привет! Вы зарегистрированы в системе.\n"
            "Ожидайте подтверждения от администратора."
        )
        from aiogram import Bot
        bot = message.bot
        notice = (
            f"⏳ Новый пользователь ожидает подтверждения:\n"
            f"Имя: {message.from_user.full_name}\n"
            f"ID: {telegram_id}\n"
            f"Username: @{message.from_user.username or 'нет'}"
        )
        try:
            await bot.send_message(ADMIN_ID, notice)
        except Exception:
            pass
        await notify_owner(bot, notice)
        return

    role = user["role"]
    if role == "pending":
        await message.answer("⏳ Ваш запрос ещё не подтверждён. Ожидайте.")
    elif role == "admin":
        await message.answer("👑 Главное меню", reply_markup=main_menu_admin())
    elif role == "manager":
        await message.answer("📋 Главное меню менеджера", reply_markup=main_menu_manager())
    elif role == "adam":
        await message.answer("🔨 Главное меню мастера", reply_markup=main_menu_adam())
    elif role == "client":
        await message.answer(
            f"🛋 Добро пожаловать, {user['name']}!",
            reply_markup=main_menu_client()
        )
    else:
        await message.answer("Неизвестная роль. Обратитесь к администратору.")
