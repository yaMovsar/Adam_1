import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/furniture_bot")

# Telegram ID администратора (ты)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Telegram ID Адама
ADAM_ID = int(os.getenv("ADAM_ID", "0"))

# Telegram ID хозяина компании (получает все уведомления)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Рабочие дни: 0=пн, 1=вт, 2=ср, 3=чт, 4=пт, 5=сб, 6=вс
# Пятница (4) — выходной
WORK_DAYS = [0, 1, 2, 3, 5, 6]

# Время дайджеста
DIGEST_HOUR = 8
DIGEST_MINUTE = 30
