import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
PORT = int(os.getenv("PORT", "10000"))

DB_PATH = Path("data/2k50.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")


# =========================
# СИСТЕМА
# =========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("2k50")

dp = Dispatcher()
router = Router()
dp.include_router(router)


# =========================
# СОСТОЯНИЯ
# =========================

class Form(StatesGroup):
    choosing_goal = State()
    journal = State()
    community = State()
    support = State()


# =========================
# ЦЕЛИ
# =========================

GOALS = {
    "self": "🧠 Разобраться в себе",
    "discipline": "🎯 Дисциплина и привычки",
    "people": "🤝 Общение и отношения",
    "career": "💼 Учёба и карьера",
    "energy": "⚡ Энергия, сон и спорт",
}


# =========================
# НАВЫКИ
# =========================

SKILLS = {
    "self": [
        ("Самооценка", "selfesteem"),
        ("Эмоциональная устойчивость", "emotion"),
        ("Цели", "goals"),
    ],
    "people": [
        ("Общение", "communication"),
        ("Границы", "boundaries"),
        ("Знакомства и друзья", "friends"),
    ],
    "life": [
        ("Дисциплина", "discipline"),
        ("Сон и режим", "sleep"),
        ("Фокус", "focus"),
        ("Деньги", "money"),
    ],
    "hard": [
        ("Когда всё достало", "hard"),
        ("Одиночество", "loneliness"),
        ("После расставания", "breakup"),
        ("Тревожный день", "anxiety"),
    ],
}


# =========================
# ПРОГРАММЫ
# =========================

PROGRAMS = {

    "selfesteem": {
        "title": "Самооценка",
        "steps": [
            "Назови 3 вещи, которые у тебя уже получаются.",
            "Запиши ситуацию, где ты обычно себя критикуешь. Что бы ты сказал другу на твоём месте?",
            "Сделай сегодня одно небольшое действие, которое давно откладывал.",
        ],
    },

    "emotion": {
        "title": "Эмоциональная устойчивость",
        "steps": [
            "Назови эмоцию одним словом. Не оценивай её.",
            "Отдели факт от мысли: что произошло объективно, а что ты предполагаешь?",
            "Выбери действие на ближайшие 10 минут, которое зависит от тебя.",
        ],
    },

    "goals": {
        "title": "Цели",
        "steps": [
            "Запиши одну цель на ближайшие 30 дней.",
            "Разбей её на результат, который можно проверить.",
            "Определи самый маленький шаг, который можно сделать сегодня за 15 минут.",
        ],
    },

    "communication": {
        "title": "Общение",
        "steps": [
            "Задай одному человеку открытый вопрос и выслушай ответ.",
            "Назови один интерес собеседника и задай уточняющий вопрос.",
            "Начни короткий разговор с человеком, с которым обычно не общаешься.",
        ],
    },

    "boundaries": {
        "title": "Границы",
        "steps": [
            "Вспомни ситуацию, где ты согласился против желания.",
            "Подготовь фразу: «Мне это не подходит» или «Сейчас не могу».",
            "Сегодня используй одну спокойную границу без длинных оправданий.",
        ],
    },

    "friends": {
        "title": "Знакомства и друзья",
        "steps": [
            "Найди среду, где регулярно бывают люди с похожими интересами.",
            "Напиши человеку первым. Коротко и без попытки понравиться.",
            "Предложи простое совместное действие: прогулку, игру, тренировку или учёбу.",
        ],
    },

    "discipline": {
        "title": "Дисциплина",
        "steps": [
            "Выбери одну привычку. Только одну.",
            "Уменьши её до версии на 2 минуты.",
            "Привяжи её к уже существующему действию.",
        ],
    },

    "sleep": {
        "title": "Сон и режим",
        "steps": [
            "Выбери реалистичное время подъёма на ближайшие 3 дня.",
            "За 30 минут до сна убери одну вещь, которая затягивает вечер.",
            "Утром выйди на дневной свет и немного подвигайся.",
        ],
    },

    "focus": {
        "title": "Фокус",
        "steps": [
            "Выбери одну задачу и сформулируй результат одним предложением.",
            "Поставь таймер на 15 минут и работай только над ней.",
            "После 15 минут реши: продолжать или сделать перерыв.",
        ],
    },

    "money": {
        "title": "Деньги",
        "steps": [
            "Запиши обязательные расходы за неделю.",
            "Найди одну регулярную трату, которую можно пересмотреть.",
            "Определи одну финансовую цель на ближайшие 30 дней.",
        ],
    },

    "hard": {
        "title": "Когда всё достало",
        "steps": [
            "Не решай всю жизнь сегодня. Запиши, что сейчас самое тяжёлое.",
            "Выбери одну базовую вещь: еда, вода, душ, сон или прогулка.",
            "Напиши безопасному человеку: «Мне сейчас тяжело, можешь немного побыть на связи?»",
        ],
    },

    "loneliness": {
        "title": "Одиночество",
        "steps": [
            "Отдели «я сейчас один» от «я никому не нужен».",
            "Напиши одному человеку без длинного объяснения.",
            "Найди регулярную среду по интересу, где люди встречаются повторно.",
        ],
    },

    "breakup": {
        "title": "После расставания",
        "steps": [
            "Запиши, что именно ты потерял: человека, привычку, планы или близость.",
            "Убери на несколько дней один сильный триггер.",
            "Сделай сегодня одну вещь, которая возвращает тебя к своей жизни.",
        ],
    },

    "anxiety": {
        "title": "Тревожный день",
        "steps": [
            "Назови, чего именно ты боишься сейчас.",
            "Раздели: что зависит от тебя сегодня, а что нет.",
            "Сделай одно короткое действие из первой группы.",
        ],
    },
}


# =========================
# DATABASE
# =========================

def now():
    return datetime.now(timezone.utc).isoformat()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            alias TEXT NOT NULL,
            goal TEXT,
            points INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS progress (
            user_id INTEGER NOT NULL,
            program TEXT NOT NULL,
            step INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            PRIMARY KEY (user_id, program, step)
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS community_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            alias TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


def ensure_user(user_id: int):
    conn = db()

    row = conn.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if not row:
        alias = f"Участник {str(user_id)[-4:]}"

        conn.execute(
            """
            INSERT INTO users
            (user_id, alias, created_at, last_seen)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, alias, now(), now()),
        )
    else:
        conn.execute(
            "UPDATE users SET last_seen = ? WHERE user_id = ?",
            (now(), user_id),
        )

    conn.commit()
    conn.close()


def get_user(user_id: int):
    conn = db()

    row = conn.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return row


def set_goal(user_id: int, goal: str):
    conn = db()

    conn.execute(
        "UPDATE users SET goal = ? WHERE user_id = ?",
        (goal, user_id),
    )

    conn.commit()
    conn.close()


def add_points(user_id: int, points: int):
    conn = db()

    conn.execute(
        "UPDATE users SET points = points + ? WHERE user_id = ?",
        (points, user_id),
    )

    conn.commit()
    conn.close()


def completed_steps(user_id: int, program: str):
    conn = db()

    rows = conn.execute(
        """
        SELECT step
        FROM progress
        WHERE user_id = ? AND program = ?
        """,
        (user_id, program),
    ).fetchall()

    conn.close()

    return {row["step"] for row in rows}


def complete_step(user_id: int, program: str, step: int):
    conn = db()

    try:
        conn.execute(
            """
            INSERT INTO progress
            (user_id, program, step, completed_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, program, step, now()),
        )

        conn.execute(
            """
            UPDATE users
            SET points = points + 10
            WHERE user_id = ?
            """,
            (user_id,),
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:
        conn.rollback()
        return False

    finally:
        conn.close()


def save_journal(user_id: int, text: str):
    conn = db()

    conn.execute(
        """
        INSERT INTO journal
        (user_id, text, created_at)
        VALUES (?, ?, ?)
        """,
        (user_id, text[:4000], now()),
    )

    conn.commit()
    conn.close()


def journal_count(user_id: int):
    conn = db()

    row = conn.execute(
        "SELECT COUNT(*) AS count FROM journal WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return row["count"]


# =========================
# КЛАВИАТУРЫ
# =========================

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧭 Мой путь"),
                KeyboardButton(text="🧠 Навыки"),
            ],
            [
                KeyboardButton(text="🎯 Задача дня"),
                KeyboardButton(text="📝 Дневник"),
            ],
            [
                KeyboardButton(text="👥 Сообщество"),
                KeyboardButton(text="🤝 Поддержка"),
            ],
            [
                KeyboardButton(text="👤 Профиль"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def back_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="↩️ Назад")],
        ],
        resize_keyboard=True,
    )


def goals_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=GOALS["self"]),
                KeyboardButton(text=GOALS["discipline"]),
            ],
            [
                KeyboardButton(text=GOALS["people"]),
                KeyboardButton(text=GOALS["career"]),
            ],
            [
                KeyboardButton(text=GOALS["energy"]),
            ],
            [
                KeyboardButton(text="↩️ Назад"),
            ],
        ],
        resize_keyboard=True,
    )


def skills_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🧠 Я"),
                KeyboardButton(text="🤝 Люди"),
            ],
            [
                KeyboardButton(text="🌱 Жизнь"),
                KeyboardButton(text="🆘 Тяжёлый период"),
            ],
            [
                KeyboardButton(text="↩️ Назад"),
            ],
        ],
        resize_keyboard=True,
    )


def category_keyboard(category: str):
    builder = InlineKeyboardBuilder()

    for title, code in SKILLS[category]:
        builder.button(
            text=title,
            callback_data=f"program:{code}",
        )

    builder.adjust(1)

    return builder.as_markup()


# =========================
# ГЛАВНАЯ
# =========================

async def send_home(message: Message):
    user = get_user(message.from_user.id)

    goal = (
        GOALS.get(user["goal"], "не выбрана")
        if user and user["goal"]
        else "не выбрана"
    )

    await message.answer(
        "<b>2К50</b>\n\n"
        "Место, где ты можешь развивать себя, "
        "находить своих людей и получать поддержку, "
        "когда жизнь идёт тяжело.\n\n"
        f"<b>Твоя цель:</b> {html.quote(goal)}\n\n"
        "Выбери, с чего хочешь начать 👇",
        reply_markup=main_menu(),
    )


# =========================
# START
# =========================

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    ensure_user(message.from_user.id)
    await state.clear()
    await send_home(message)


@router.message(Command("menu"))
async def menu(message: Message, state: FSMContext):
    ensure_user(message.from_user.id)
    await state.clear()
    await send_home(message)


@router.message(Command("myid"))
async def my_id(message: Message):
    await message.answer(
        f"Твой Telegram ID:\n<code>{message.from_user.id}</code>"
    )


# =========================
# МОЙ ПУТЬ
# =========================

@router.message(F.text == "🧭 Мой путь")
async def my_path(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)

    if user and user["goal"]:
        await message.answer(
            "<b>🧭 Мой путь</b>\n\n"
            f"Текущая цель:\n{html.quote(GOALS[user['goal']])}\n\n"
            "Можешь изменить её или перейти к навыкам.",
            reply_markup=goals_menu(),
        )
    else:
        await state.set_state(Form.choosing_goal)

        await message.answer(
            "<b>🧭 Мой путь</b>\n\n"
            "Что сейчас для тебя важнее всего?",
            reply_markup=goals_menu(),
        )


@router.message(Form.choosing_goal)
async def choose_goal(message: Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        return await send_home(message)

    mapping = {value: key for key, value in GOALS.items()}

    if message.text not in mapping:
        return await message.answer(
            "Выбери один вариант кнопкой ниже.",
            reply_markup=goals_menu(),
        )

    goal = mapping[message.text]

    set_goal(message.from_user.id, goal)

    await state.clear()

    await message.answer(
        "<b>Готово.</b>\n\n"
        f"Твоя цель: {html.quote(GOALS[goal])}\n\n"
        "Теперь открой «🧠 Навыки» и выбери программу.",
        reply_markup=main_menu(),
    )


# =========================
# НАВЫКИ
# =========================

@router.message(F.text == "🧠 Навыки")
async def skills(message: Message):
    await message.answer(
        "<b>🧠 Навыки</b>\n\n"
        "Выбери направление:",
        reply_markup=skills_menu(),
    )


@router.message(F.text == "🧠 Я")
async def skills_self(message: Message):
    await message.answer(
        "<b>🧠 Про себя</b>",
        reply_markup=category_keyboard("self"),
    )


@router.message(F.text == "🤝 Люди")
async def skills_people(message: Message):
    await message.answer(
        "<b>🤝 Про людей</b>",
        reply_markup=category_keyboard("people"),
    )


@router.message(F.text == "🌱 Жизнь")
async def skills_life(message: Message):
    await message.answer(
        "<b>🌱 Жизнь</b>",
        reply_markup=category_keyboard("life"),
    )


@router.message(F.text == "🆘 Тяжёлый период")
async def skills_hard(message: Message):
    await message.answer(
        "<b>🆘 Тяжёлый период</b>\n\n"
        "Не нужно решать всю жизнь сразу. "
        "Выбери конкретную ситуацию:",
        reply_markup=category_keyboard("hard"),
    )


@router.callback_query(F.data.startswith("program:"))
async def open_program(callback: CallbackQuery):
    code = callback.data.split(":", 1)[1]

    if code not in PROGRAMS:
        await callback.answer("Программа не найдена.", show_alert=True)
        return

    program = PROGRAMS[code]
    done = completed_steps(callback.from_user.id, code)

    text = (
        f"<b>{html.quote(program['title'])}</b>\n\n"
        "Короткая программа из 3 шагов.\n\n"
    )

    for i, step in enumerate(program["steps"]):
        mark = "✅" if i in done else "▫️"

        text += (
            f"{mark} <b>Шаг {i + 1}</b>\n"
            f"{html.quote(step)}\n\n"
        )

    builder = InlineKeyboardBuilder()

    for i in range(3):
        if i not in done:
            builder.button(
                text=f"✅ Выполнить шаг {i + 1}",
                callback_data=f"done:{code}:{i}",
            )

    builder.button(
        text="🧠 Другие программы",
        callback_data="skills_back",
    )

    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("done:"))
async def done_step(callback: CallbackQuery):
    _, code, step_raw = callback.data.split(":")

    if code not in PROGRAMS:
        await callback.answer("Ошибка.", show_alert=True)
        return

    step = int(step_raw)

    if step not in range(3):
        await callback.answer("Ошибка.", show_alert=True)
        return

    created = complete_step(
        callback.from_user.id,
        code,
        step,
    )

    if created:
        await callback.answer("+10 очков 🎯")
    else:
        await callback.answer("Этот шаг уже выполнен.")

    await open_program(callback)


@router.callback_query(F.data == "skills_back")
async def skills_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>🧠 Навыки</b>\n\n"
        "Вернись в меню и выбери направление.",
    )

    await callback.answer()


# =========================
# ЗАДАЧА ДНЯ
# =========================

@router.message(F.text == "🎯 Задача дня")
async def daily_task(message: Message):
    user = get_user(message.from_user.id)

    goal = user["goal"] if user else None

    tasks = {
        "self":
            "Запиши одну мысль, которая сегодня повторяется чаще всего. "
            "Отдели факт от своей интерпретации.",

        "discipline":
            "Выбери одну маленькую задачу и сделай её 10 минут без переключения.",

        "people":
            "Напиши одному человеку первым. "
            "Не нужен длинный текст — просто начни контакт.",

        "career":
            "Сделай 15 минут конкретного действия для учёбы или работы.",

        "energy":
            "Выйди на улицу на 10–15 минут и немного пройдись.",

        None:
            "Сделай сегодня одну маленькую вещь, "
            "которую давно откладываешь.",
    }

    task = tasks.get(goal, tasks[None])

    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Сделал",
        callback_data="daily_done",
    )

    builder.button(
        text="🔄 Другая задача",
        callback_data="daily_other",
    )

    builder.adjust(1)

    await message.answer(
        f"<b>🎯 Задача дня</b>\n\n{html.quote(task)}",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "daily_done")
async def daily_done(callback: CallbackQuery):
    add_points(callback.from_user.id, 5)

    await callback.message.edit_text(
        "<b>🎯 Задача дня</b>\n\n"
        "✅ Отмечено.\n\n"
        "+5 очков.\n\n"
        "Маленькие действия складываются в систему."
    )

    await callback.answer("+5 очков")


@router.callback_query(F.data == "daily_other")
async def daily_other(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>🎯 Другая задача</b>\n\n"
        "Убери на 15 минут одну вещь, "
        "которая постоянно отвлекает тебя: "
        "уведомления, лишнюю вкладку или телефон рядом."
    )

    await callback.answer()


# =========================
# ДНЕВНИК
# =========================

@router.message(F.text == "📝 Дневник")
async def journal_start(message: Message, state: FSMContext):
    await state.set_state(Form.journal)

    await message.answer(
        "<b>📝 Дневник</b>\n\n"
        "Напиши несколько строк о том, "
        "что сейчас у тебя в голове.\n\n"
        "Запись сохраняется для твоего аккаунта.\n\n"
        "Для выхода нажми «↩️ Назад».",
        reply_markup=back_menu(),
    )


@router.message(Form.journal)
async def journal_save(message: Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        return await send_home(message)

    text = (message.text or "").strip()

    if not text:
        return await message.answer("Напиши текстом.")

    save_journal(
        message.from_user.id,
        text,
    )

    add_points(
        message.from_user.id,
        5,
    )

    await state.clear()

    await message.answer(
        "📝 Запись сохранена.\n\n"
        "+5 очков.",
        reply_markup=main_menu(),
    )


# =========================
# ПРОФИЛЬ
# =========================

@router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user = get_user(message.from_user.id)

    if not user:
        ensure_user(message.from_user.id)
        user = get_user(message.from_user.id)

    goal = (
        GOALS.get(user["goal"], "не выбрана")
        if user["goal"]
        else "не выбрана"
    )

    count = journal_count(
        message.from_user.id
    )

    await message.answer(
        "<b>👤 Профиль</b>\n\n"
        f"<b>Твой ID:</b> {html.quote(user['alias'])}\n"
        f"<b>Цель:</b> {html.quote(goal)}\n"
        f"<b>Очки:</b> {user['points']}\n"
        f"<b>Записей в дневнике:</b> {count}\n\n"
        "Твой username другим участникам "
        "через систему бота не показывается.",
        reply_markup=main_menu(),
    )


# =========================
# СООБЩЕСТВО
# =========================

@router.message(F.text == "👥 Сообщество")
async def community(message: Message, state: FSMContext):
    if not ADMIN_CHAT_ID:
        await message.answer(
            "<b>👥 Сообщество</b>\n\n"
            "Модерация сообщества ещё не подключена.\n\n"
            "Функция уже заложена в систему — "
            "нужно подключить аккаунт администратора."
        )
        return

    await state.set_state(Form.community)

    await message.answer(
        "<b>👥 Сообщество</b>\n\n"
        "Здесь можно отправить сообщение "
        "анонимно для модерации.\n\n"
        "Другим участникам твой username "
        "не передаётся.\n\n"
        "Напиши сообщение:",
        reply_markup=back_menu(),
    )


@router.message(Form.community)
async def community_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
):
    if message.text == "↩️ Назад":
        await state.clear()
        return await send_home(message)

    text = (message.text or "").strip()

    if not text:
        return await message.answer("Напиши текстом.")

    user = get_user(message.from_user.id)

    conn = db()

    cursor = conn.execute(
        """
        INSERT INTO community_posts
        (user_id, alias, text, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            message.from_user.id,
            user["alias"],
            text[:4000],
            now(),
        ),
    )

    post_id = cursor.lastrowid

    conn.commit()
    conn.close()

    try:
        await bot.send_message(
            int(ADMIN_CHAT_ID),
            "<b>📝 Новый анонимный пост</b>\n\n"
            f"<b>#{post_id}</b>\n\n"
            f"{html.quote(text[:4000])}",
        )
    except Exception:
        logger.exception(
            "Не удалось отправить пост администратору"
        )

    await state.clear()

    await message.answer(
        "✅ Сообщение отправлено на модерацию.",
        reply_markup=main_menu(),
    )


# =========================
# ПОДДЕРЖКА
# =========================

@router.message(F.text == "🤝 Поддержка")
async def support(message: Message, state: FSMContext):
    if not ADMIN_CHAT_ID:
        await message.answer(
            "<b>🤝 Поддержка</b>\n\n"
            "Канал поддержки ещё не подключён."
        )
        return

    await state.set_state(Form.support)

    await message.answer(
        "<b>🤝 Поддержка</b>\n\n"
        "Если тебе тяжело — можешь написать, "
        "что происходит.\n\n"
        "Не нужно формулировать всё идеально.\n\n"
        "Если есть непосредственная опасность "
        "для тебя или другого человека, "
        "обратись в местную экстренную службу "
        "или к человеку рядом с тобой.\n\n"
        "Напиши сообщение:",
        reply_markup=back_menu(),
    )


@router.message(Form.support)
async def support_save(
    message: Message,
    state: FSMContext,
    bot: Bot,
):
    if message.text == "↩️ Назад":
        await state.clear()
        return await send_home(message)

    text = (message.text or "").strip()

    if not text:
        return await message.answer("Напиши сообщение.")

    try:
        await bot.send_message(
            int(ADMIN_CHAT_ID),
            "<b>🤝 Новое обращение</b>\n\n"
            f"{html.quote(text[:4000])}",
        )
    except Exception:
        logger.exception(
            "Не удалось отправить обращение"
        )

    await state.clear()

    await message.answer(
        "✅ Сообщение принято.",
        reply_markup=main_menu(),
    )


# =========================
# НАЗАД
# =========================

@router.message(F.text == "↩️ Назад")
async def back(message: Message, state: FSMContext):
    await state.clear()
    await send_home(message)


# =========================
# НЕИЗВЕСТНОЕ СООБЩЕНИЕ
# =========================

@router.message()
async def fallback(message: Message):
    await message.answer(
        "Выбери действие кнопками ниже 👇",
        reply_markup=main_menu(),
    )


# =========================
# RENDER HEALTH CHECK
# =========================

async def health(request):
    return web.Response(text="2K50 OK")


async def start_web_server():
    app = web.Application()

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT,
    )

    await site.start()

    logger.info(
        "Health server started on port %s",
        PORT,
    )

    return runner


# =========================
# ЗАПУСК
# =========================

async def main():
    init_db()

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    runner = await start_web_server()

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    finally:
        await bot.session.close()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
