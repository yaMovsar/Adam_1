# МебельБот — Telegram бот для управления заказами

## Структура проекта

```
furniture_bot/
├── main.py              # Точка входа
├── config.py            # Конфигурация
├── requirements.txt     # Зависимости
├── Procfile             # Для Railway
├── .env.example         # Пример переменных окружения
├── database/
│   └── db.py            # Работа с PostgreSQL
├── handlers/
│   ├── common.py        # /start, роутинг по ролям
│   ├── admin.py         # Управление пользователями
│   ├── manager.py       # Создание заказов
│   ├── adam.py          # Продление сроков
│   └── client.py        # Просмотр своих заказов
├── keyboards/
│   └── keyboards.py     # Все клавиатуры
└── utils/
    ├── helpers.py        # Форматирование, парсинг дат
    └── scheduler.py     # Утренний дайджест в 8:30
```

## Роли

| Роль | Возможности |
|------|-------------|
| admin | Назначает роли, видит всё |
| manager | Создаёт заказы, меняет статусы |
| adam | Меняет статусы, продлевает сроки |
| client | Видит только свои заказы |

## Статусы заказов

`accepted` → `in_production` → `ready` → `shipped`

## Деплой на Railway

### 1. Создайте бота
- Откройте @BotFather → /newbot
- Сохраните токен

### 2. Узнайте Telegram ID
- Напишите @userinfobot
- Сохраните свой ID (ADMIN_ID) и ID Адама (ADAM_ID)

### 3. Создайте проект на Railway
- railway.app → New Project → Deploy from GitHub
- Или: railway.app → New Project → Empty Project

### 4. Добавьте PostgreSQL
- В Railway: Add Service → Database → PostgreSQL
- Скопируйте DATABASE_URL из настроек базы

### 5. Добавьте переменные окружения
В Railway → Variables добавьте:
```
BOT_TOKEN=ваш_токен
DATABASE_URL=postgresql://...
ADMIN_ID=ваш_telegram_id
ADAM_ID=telegram_id_адама
```

### 6. Задеплойте код
- Загрузите папку на GitHub
- Подключите репозиторий к Railway
- Railway автоматически установит зависимости и запустит бота

## Рабочие дни
Пн, Вт, Ср, Чт, Сб, Вс (пятница — выходной)

## Утренний дайджест
Каждый день в 8:30 Адам получает список заказов со сроком до 2 дней
