import re
import os
import json
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from datetime import datetime


# ============ НАСТРОЙКИ ============
BOT_TOKEN = "8640113508:AAHhQlvZO4CV9xPi_JsrgzCyaJHr3TeGIHY"
ADMIN_IDS = [5123455277, 5050181546]
SHEET_ID = "1cgMBDudmP0b6gFuHXeyQ3Fw-ZeLCwEkR8KiFZC_UwKQ"

# --- АВТОРИЗАЦИЯ GOOGLE SHEETS ---
creds_json = os.environ.get('GOOGLE_CREDS_JSON')
creds_dict = json.loads(creds_json)
client = gspread.service_account_from_dict(creds_dict)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# ============ КЛАВИАТУРА (постоянная, внизу чата) ============
def get_main_keyboard():
    """Создает постоянную клавиатуру с кнопками"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("🎟 Ввести промокод"),
        KeyboardButton("🏆 Мои призы")
    )
    keyboard.add(KeyboardButton("ℹ️ Как это работает?"))
    return keyboard


# ============ GOOGLE SHEETS ============
def get_google_sheet():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Таблице: {e}")
        return None


def check_and_use_promocode(code: str, username: str, user_id: int):
    """
    Проверяет код в таблице и если он свободен - использует его.
    
    Новая структура таблицы:
    A: №
    B: код
    C: выигрыш (0 или 1)  <-- НОВЫЙ СТОЛБЕЦ
    D: приз
    E: использование
    F: примечание
    G: дата
    """
    try:
        sheet = get_google_sheet()
        if not sheet:
            return False, "❌ Ошибка подключения к базе данных. Попробуйте позже."
        
        # Получаем все значения столбца B (коды)
        codes_column = sheet.col_values(2)
        
        input_code = code.strip().upper()
        found_row_index = None
        
        for i, table_code in enumerate(codes_column):
            if i == 0:  # Пропускаем заголовок
                continue
            if str(table_code).strip().upper() == input_code:
                found_row_index = i + 1
                break
        
        if not found_row_index:
            return False, "❌ Неверный промокод."
        
        # Проверяем столбец E (использование) — индекс 5
        usage_cell = sheet.cell(found_row_index, 5).value
        try:
            usage_count = int(usage_cell) if usage_cell else 0
        except:
            usage_count = 0
        
        if usage_count > 0:
            return False, "❌ Промокод уже был использован!"
        
        # Получаем значение "выигрыш" из столбца C — индекс 3
        win_cell = sheet.cell(found_row_index, 3).value
        try:
            is_winner = int(win_cell) if win_cell else 0
        except:
            is_winner = 0
        
        # Получаем приз из столбца D — индекс 4
        prize = sheet.cell(found_row_index, 4).value or "Секретный приз"
        
        # Обновляем таблицу:
        # 1. Увеличиваем использование на 1 (столбец E)
        sheet.update_cell(found_row_index, 5, 1)
        
        # 2. Записываем username и ID в столбец F (примечание)
        sheet.update_cell(found_row_index, 6, f"@{username} (ID:{user_id})")
        
        # 3. Записываем дату в столбец G
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        sheet.update_cell(found_row_index, 7, now)
        
        # 4. Формируем ответ в зависимости от выигрыша
        if is_winner == 1:
            return True, f"🎉 Поздравляем! Вы выиграли: {prize}", True
        else:
            return True, "😔 К сожалению, данный билет оказался не выигрышным. Попробуйте другой код!", False
        
    except Exception as e:
        print(f"Ошибка при проверке кода: {e}")
        return False, "❌ Произошла ошибка при проверке кода. Попробуйте позже.", False


def get_user_prizes(user_id: int):
    """
    Получает только ВЫИГРЫШНЫЕ призы пользователя.
    
    Структура: A(№), B(код), C(выигрыш), D(приз), E(использование), F(примечание), G(дата)
    """
    try:
        sheet = get_google_sheet()
        if not sheet:
            return None
        
        all_values = sheet.get_all_values()
        
        if len(all_values) < 2:
            return []
        
        data_rows = all_values[1:]  # Пропускаем заголовок
        user_prizes = []
        
        for row in data_rows:
            if len(row) < 7:
                continue
            
            # row[0]=№, row[1]=код, row[2]=выигрыш, row[3]=приз, 
            # row[4]=использование, row[5]=примечание, row[6]=дата
            note = row[5]
            win_value = row[2]
            
            # Ищем ID пользователя в примечании
            if f"ID:{user_id}" not in note:
                continue
            
            # Показываем ТОЛЬКО выигрышные билеты (где выигрыш = 1)
            try:
                is_winner = int(win_value) if win_value else 0
            except:
                is_winner = 0
            
            if is_winner == 1:
                prize_info = {
                    'number': row[0],
                    'code': row[1],
                    'prize': row[3],
                    'datetime': row[6]
                }
                user_prizes.append(prize_info)
        
        return user_prizes
        
    except Exception as e:
        print(f"Ошибка при получении призов: {e}")
        return None


# ============ FSM ============
class PromoCodeStates(StatesGroup):
    waiting_for_code = State()


# ============ ХЕНДЛЕРЫ ============

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = get_main_keyboard()
    
    await message.answer(
        "👋 Привет! Я бот для проведения акции 'Новогодний БУМ от PABO SHOP'.\n\n"
        "Используй кнопки ниже, чтобы ввести промокод или посмотреть свои призы.",
        reply_markup=keyboard
    )


@dp.message_handler(lambda m: m.text == "ℹ️ Как это работает?")
async def info_handler(message: types.Message):
    await message.answer(
        "ℹ️ <b>Как это работает?</b>\n\n"
        "1. Нажми кнопку «🎟 Ввести промокод»\n"
        "2. Отправь мне свой промокод\n"
        "3. Если код верный — узнаешь, выиграл ты приз или нет!\n\n"
        "Чтобы посмотреть свои выигрыши, нажми «🏆 Мои призы».\n\n"
        "Удачи! 🍀",
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )


@dp.message_handler(lambda m: m.text == "🎟 Ввести промокод")
async def enter_promo_handler(message: types.Message, state: FSMContext):
    await PromoCodeStates.waiting_for_code.set()
    
    # Убираем клавиатуру на время ввода
    await message.answer(
        "📝 Отправь мне свой промокод.\n\n"
        "Просто напиши его одним сообщением (например: A1B2C3D4)\n\n"
        "Чтобы отменить ввод, напиши /cancel",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message_handler(commands=['cancel'], state=PromoCodeStates.waiting_for_code)
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "❌ Ввод отменён.",
        reply_markup=get_main_keyboard()
    )


@dp.message_handler(state=PromoCodeStates.waiting_for_code, content_types=types.ContentType.TEXT)
async def process_promocode(message: types.Message, state: FSMContext):
    code = message.text.strip()
    
    if len(code) < 8:
        await message.answer(
            "❌ Промокод слишком короткий. Проверь и попробуй снова.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    username = message.from_user.username or f"user{message.from_user.id}"
    user_id = message.from_user.id
    
    result = check_and_use_promocode(code, username, user_id)
    
    # Обработка нового формата ответа (3 значения)
    if len(result) == 3:
        is_valid, result_message, is_winner = result
    else:
        is_valid, result_message = result
        is_winner = False
    
    await state.finish()
    
    # Отвечаем пользователю и возвращаем клавиатуру
    await message.answer(result_message, reply_markup=get_main_keyboard())
    
    if is_valid:
        print(f"✅ Код {code} обработан для {username} (выигрыш: {is_winner})")
    else:
        print(f"❌ Неудачная попытка: {code} от {username}")


@dp.message_handler(lambda m: m.text == "🏆 Мои призы")
async def my_prizes_handler(message: types.Message):
    user_id = message.from_user.id
    prizes = get_user_prizes(user_id)
    
    if prizes is None:
        await message.answer(
            "❌ Ошибка подключения к базе данных. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )
        return
    
    if not prizes:
        await message.answer(
            "📭 У вас пока нет выигранных призов.\n\n"
            "Введите промокод, чтобы узнать свой результат!",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = "🏆 <b>Ваши выигрышные призы:</b>\n\n"
    
    for prize in prizes:
        text += f"📌 <b>Билет №{prize['number']}</b>\n"
        text += f"🎟 Код: <code>{prize['code']}</code>\n"
        text += f"🎁 Приз: {prize['prize']}\n"
        text += f"📅 Дата: {prize['datetime']}\n\n"
    
    await message.answer(text, parse_mode='HTML', reply_markup=get_main_keyboard())


# ============ АДМИНКА ============

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Доступ только для администратора.")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("🔄 Проверить подключение", callback_data="admin_check")
    )
    
    await message.answer("🔧 Панель администратора:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    try:
        sheet = get_google_sheet()
        if not sheet:
            await callback.message.answer("❌ Нет подключения к таблице")
            await callback.answer()
            return
        
        all_values = sheet.get_all_values()
        
        if len(all_values) < 2:
            await callback.message.answer("📊 Таблица пуста")
            await callback.answer()
            return
        
        data_rows = all_values[1:]
        total = len(data_rows)
        
        # Считаем использованные (столбец E, индекс 4)
        used = sum(1 for row in data_rows if len(row) > 4 and row[4] and int(row[4]) > 0)
        
        # Считаем выигрышные (столбец C, индекс 2)
        winners = sum(1 for row in data_rows if len(row) > 2 and row[2] and int(row[2]) == 1)
        
        available = total - used
        
        await callback.message.answer(
            f"📊 <b>Статистика таблицы:</b>\n\n"
            f"🔢 Всего кодов: {total}\n"
            f"🏆 Выигрышных билетов: {winners}\n"
            f"✅ Использовано: {used}\n"
            f"🟢 Доступно: {available}",
            parse_mode='HTML'
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "admin_check")
async def admin_check(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    sheet = get_google_sheet()
    if sheet:
        await callback.message.answer("✅ Подключение к Google Таблице работает!")
    else:
        await callback.message.answer("❌ Ошибка подключения. Проверьте credentials.json")
    
    await callback.answer()


# ============ ЗАПУСК ============

async def on_startup(dispatcher):
    print("✅ Бот запущен")
    
    sheet = get_google_sheet()
    if sheet:
        print("✅ Google Таблица подключена")
    else:
        print("⚠️ Google Таблица НЕ подключена")

async def on_shutdown(dispatcher):
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


if __name__ == '__main__':
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )
