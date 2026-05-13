from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import get_user_by_telegram_id, get_order_by_id, extend_order_deadline
from keyboards.keyboards import order_actions_keyboard
from utils.helpers import format_order_card, parse_deadline

router = Router()


class ExtendStates(StatesGroup):
    waiting_reason = State()
    waiting_new_date = State()


@router.callback_query(F.data.startswith("extend_deadline:"))
async def extend_deadline_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user or user["role"] not in ["manager", "admin", "adam"]:
        return

    order_id = int(callback.data.split(":")[1])
    order = await get_order_by_id(order_id)

    await state.set_state(ExtendStates.waiting_reason)
    await state.update_data(order_id=order_id, user_id=user["id"])

    await callback.message.answer(
        f"📅 Продление срока заказа {order['order_number']}\n"
        f"Текущий срок: {order['deadline'].strftime('%d.%m.%Y')}\n\n"
        f"Укажите причину продления:"
    )
    await callback.answer()


@router.message(ExtendStates.waiting_reason)
async def extend_reason(message: Message, state: FSMContext):
    await state.update_data(reason=message.text.strip())
    await state.set_state(ExtendStates.waiting_new_date)
    await message.answer("📅 Укажите новый срок (например: 20.05 или через 5 дней):")


@router.message(ExtendStates.waiting_new_date)
async def extend_new_date(message: Message, state: FSMContext):
    new_deadline = parse_deadline(message.text.strip())
    if not new_deadline:
        await message.answer("❌ Не понял дату. Попробуйте: 20.05 или «через 5 дней»")
        return

    data = await state.get_data()
    order = await extend_order_deadline(
        order_id=data["order_id"],
        new_deadline=new_deadline,
        reason=data["reason"],
        extended_by_id=data["user_id"]
    )
    await state.clear()

    await message.answer(
        f"✅ Срок продлён до {new_deadline.strftime('%d.%m.%Y')}\n"
        f"Причина: {data['reason']}\n\n"
        f"{format_order_card(order)}",
        reply_markup=order_actions_keyboard(order["id"], order["status"], "adam")
    )
