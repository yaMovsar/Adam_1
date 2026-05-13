from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import date


STATUS_LABELS = {
    "accepted": "✅ Принят",
    "in_production": "🔨 В производстве",
    "ready": "📦 Готов",
    "shipped": "🚚 Отправлен",
}

STATUS_EMOJI = {
    "accepted": "✅",
    "in_production": "🔨",
    "ready": "📦",
    "shipped": "🚚",
}


def _deadline_label(deadline) -> str:
    if deadline is None:
        return ""
    today = date.today()
    if hasattr(deadline, "date"):
        deadline = deadline.date()
    delta = (deadline - today).days
    if delta < 0:
        return f" • 🔴 просрочен {-delta}д"
    if delta == 0:
        return " • 🔴 сегодня"
    if delta <= 2:
        return f" • 🟡 {delta}д"
    return f" • 🟢 {delta}д"


def main_menu_manager():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Новый заказ")],
        [KeyboardButton(text="📋 Активные заказы"), KeyboardButton(text="🗂 Архив")],
    ], resize_keyboard=True)
    return kb


def main_menu_adam():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Активные заказы")],
        [KeyboardButton(text="🗂 Архив")],
    ], resize_keyboard=True)
    return kb


def main_menu_client():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="🗂 Архив")],
    ], resize_keyboard=True)
    return kb


def main_menu_admin():
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Новый заказ")],
        [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="⏳ Ожидают подтверждения")],
        [KeyboardButton(text="📋 Активные заказы"), KeyboardButton(text="🗂 Архив")],
    ], resize_keyboard=True)
    return kb


def clients_keyboard(clients):
    builder = InlineKeyboardBuilder()
    for client in clients:
        builder.button(
            text=client["name"],
            callback_data=f"select_client:{client['id']}"
        )
    builder.button(text="➕ Новый клиент", callback_data="new_client")
    builder.adjust(2)
    return builder.as_markup()


def edit_clients_keyboard(clients):
    builder = InlineKeyboardBuilder()
    for client in clients:
        builder.button(
            text=client["name"],
            callback_data=f"edit_select_client:{client['id']}"
        )
    builder.button(text="➕ Новый клиент", callback_data="edit_new_client")
    builder.button(text="❌ Отмена", callback_data="edit_cancel_client")
    builder.adjust(2)
    return builder.as_markup()


def order_actions_keyboard(order_id: int, current_status: str, role: str):
    builder = InlineKeyboardBuilder()

    status_flow = {
        "accepted": "in_production",
        "in_production": "ready",
        "ready": "shipped",
    }

    next_status = status_flow.get(current_status)
    if next_status:
        label = STATUS_LABELS.get(next_status, next_status)
        builder.button(
            text=f"➡️ {label}",
            callback_data=f"set_status:{order_id}:{next_status}"
        )

    builder.button(
        text="📅 Продлить срок",
        callback_data=f"extend_deadline:{order_id}"
    )

    if role == "admin":
        builder.button(text="✏️ Редактировать", callback_data=f"edit_order:{order_id}")
        builder.button(text="🗑 Удалить заказ", callback_data=f"delete_order:{order_id}")

    builder.adjust(1)
    return builder.as_markup()


def order_edit_keyboard(order_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Описание", callback_data=f"edit_field:{order_id}:description")
    builder.button(text="🎨 Цвет", callback_data=f"edit_field:{order_id}:color")
    builder.button(text="📅 Срок", callback_data=f"edit_field:{order_id}:deadline")
    builder.button(text="👤 Клиент", callback_data=f"edit_field:{order_id}:client")
    builder.button(text="❌ Отмена", callback_data=f"cancel_edit:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_delete_keyboard(order_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"confirm_delete:{order_id}")
    builder.button(text="❌ Отмена", callback_data=f"cancel_edit:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def orders_list_keyboard(orders, prefix="order"):
    builder = InlineKeyboardBuilder()
    for order in orders:
        status = STATUS_EMOJI.get(order["status"], order["status"])
        deadline = _deadline_label(order.get("deadline"))
        builder.button(
            text=f"{order['order_number']} • {order['client_name']} • {status}{deadline}",
            callback_data=f"{prefix}_detail:{order['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()


def confirm_status_keyboard(order_id: int, new_status: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"confirm_status:{order_id}:{new_status}")
    builder.button(text="❌ Отмена", callback_data=f"cancel_action:{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def users_list_keyboard(users):
    builder = InlineKeyboardBuilder()
    for u in users:
        builder.button(
            text=u["name"] or "Без имени",
            callback_data=f"user_info:{u['telegram_id']}"
        )
    builder.adjust(2)
    return builder.as_markup()


def user_manage_keyboard(telegram_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить роль", callback_data=f"change_role:{telegram_id}")
    builder.button(text="🗑 Удалить", callback_data=f"delete_user:{telegram_id}")
    builder.button(text="« Назад к списку", callback_data="users_back")
    builder.adjust(2, 1)
    return builder.as_markup()


def admin_pending_user_keyboard(telegram_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Назначить роль", callback_data=f"assign_role:{telegram_id}")
    builder.button(text="🔗 Привязать к клиенту", callback_data=f"link_user:{telegram_id}")
    builder.button(text="❌ Отклонить", callback_data=f"reject_user:{telegram_id}")
    builder.adjust(2)
    return builder.as_markup()


def link_clients_keyboard(clients, telegram_id: int):
    builder = InlineKeyboardBuilder()
    for client in clients:
        builder.button(
            text=client["name"],
            callback_data=f"link_to:{client['id']}:{telegram_id}"
        )
    builder.button(text="❌ Отмена", callback_data=f"link_cancel:{telegram_id}")
    builder.adjust(1)
    return builder.as_markup()


def role_selection_keyboard(telegram_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Менеджер", callback_data=f"set_role:{telegram_id}:manager")
    builder.button(text="🔧 Мастер (Адам)", callback_data=f"set_role:{telegram_id}:adam")
    builder.button(text="🛋 Клиент", callback_data=f"set_role:{telegram_id}:client")
    builder.adjust(1)
    return builder.as_markup()
