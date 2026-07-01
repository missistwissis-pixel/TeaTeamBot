import asyncio
import json
import os
import re
import uuid
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
BOT_USERNAME = "TeaTeamShopBOT"
CHANNEL = "@TeaTeamMinecraft"
ADMIN = "@RussianMcLover"
OWNER_ID = 996965993

PLATEGA_MERCHANT_ID = "9e37c0bb-30b8-4539-8542-331478e10dd8"
PLATEGA_SECRET = "DJSSKPR980as7UyBTVVKPI05H9L15jKFqsXzjA5ThUBMvhd0WUEPPUFjtcvtKWSUnrCtk7nkvicf1fOYE5NwaRvbbqaxSy2isr38"
PLATEGA_API = "https://app.platega.io"

DATA_FILE = "users_data.json"
CONFIG_FILE = "config.json"
ORDER_COUNTER_FILE = "order_counter.json"

BLACKLIST = [
    6028866248, 7841921425, 5851583968, 7998844688, 7663328605,
    8125688106, 7871662960, 7593436831, 8490391673, 8180839860,
    1161186243, 6751712731, 8475175993, 8300401654, 8444427049,
    8374958394, 8598444994, 7976292866, 8437474889, 8299245784,
    8202621162, 7971979788, 7504669885, 8461924100, 7960787761,
    55382141593, 5031399526, 655345336, 71890516296, 6524402058,
    7394892115, 5635650244, 6901918900, 8332916633, 7482262391,
    1876141924, 1011364448, 7588612712, 7875849073, 6082672427,
    7639364903, 7884178201, 8340303290, 1219677017, 8551225670,
    5429462197, 8551042115, 8164365607, 8227995371,
    8294888347, 8508636521, 7266400452, 5243125820, 712714494,
    7181952222, 8231510672, 8505920539, 8542147824, 8404401120,
    8322534938, 537609682, 8588213096, 8586185355
]

RUSSIAN_BANKS = [
    "Сбербанк", "ВТБ", "Газпромбанк", "Альфа-Банк", "Россельхозбанк",
    "МКБ", "ФК Открытие", "Промсвязьбанк", "Совкомбанк", "Райффайзенбанк",
    "Тинькофф Банк", "ЮниКредит Банк", "Росбанк", "Банк ДОМ.РФ",
    "Почта Банк", "Ак Барс", "Уралсиб", "Зенит", "МТС Банк",
    "Хоум Кредит Банк", "ОТП Банк", "Ренессанс Кредит", "Восточный Банк",
    "Банк Санкт-Петербург", "Банк УРАЛСИБ", "Азиатско-Тихоокеанский Банк",
    "Примсоцбанк", "Банк ЗЕНИТ", "Банк Левобережный", "ЮMoney", "СБП",
    "Qiwi", "Яндекс.Деньги", "WebMoney", "PayPal"
]

RETURN_URL = f"https://t.me/{BOT_USERNAME}"
ACTIVE_POLLS = {}
USER_ORDER_DATA = {}

def get_next_order_id():
    if os.path.exists(ORDER_COUNTER_FILE):
        with open(ORDER_COUNTER_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {"counter": 0}
    data["counter"] += 1
    with open(ORDER_COUNTER_FILE, "w") as f:
        json.dump(data, f)
    return data["counter"]

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    default = {
        "stars_price_per_one": 1.5,
        "ton_price": 130,
        "ref_percent": 10,
        "commission": 6,
        "max_stars": 10000,
        "max_ton": 1000,
        "min_withdraw": 10,
        "all_users_ids": [],
        "admin_ids": [OWNER_ID]
    }
    save_config(default)
    return default

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

config = load_config()
STARS_PRICE_PER_ONE = config["stars_price_per_one"]
TON_PRICE = config["ton_price"]
REF_PERCENT = config["ref_percent"] / 100
COMMISSION = config["commission"] / 100
MAX_STARS = config["max_stars"]
MAX_TON = config["max_ton"]
MIN_WITHDRAW = config["min_withdraw"]

def reload_config():
    global config, STARS_PRICE_PER_ONE, TON_PRICE, REF_PERCENT, COMMISSION, MAX_STARS, MAX_TON, MIN_WITHDRAW
    config = load_config()
    STARS_PRICE_PER_ONE = config["stars_price_per_one"]
    TON_PRICE = config["ton_price"]
    REF_PERCENT = config["ref_percent"] / 100
    COMMISSION = config["commission"] / 100
    MAX_STARS = config["max_stars"]
    MAX_TON = config["max_ton"]
    MIN_WITHDRAW = config["min_withdraw"]

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class Purchase(StatesGroup):
    choosing_product = State()
    entering_amount = State()
    waiting_username = State()
    choosing_payment = State()
    waiting_payment = State()
    waiting_ton_wallet = State()
    confirm_ton_wallet = State()

class Withdraw(StatesGroup):
    waiting_amount = State()
    waiting_details = State()

class AdminStates(StatesGroup):
    in_admin_panel = State()
    changing_stars_price = State()
    changing_ton_price = State()
    changing_ref_percent = State()
    giving_balance_user = State()
    giving_balance_amount = State()
    sending_broadcast = State()
    giving_admin = State()
    removing_admin = State()

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def admin_ids():
    return load_config().get("admin_ids", [OWNER_ID])

def is_admin(user_id: str) -> bool:
    return int(user_id) in admin_ids()

def is_owner(user_id: str) -> bool:
    return int(user_id) == OWNER_ID

def is_blacklisted(user_id: int) -> bool:
    return user_id in BLACKLIST

def get_user_data(user_id: str):
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "balance": 0,
            "balance_tea": 0.0,
            "refs": [],
            "ref_link": None,
            "invited_by": None,
            "username": ""
        }
        cfg = load_config()
        if user_id not in cfg["all_users_ids"]:
            cfg["all_users_ids"].append(user_id)
            save_config(cfg)
        save_data(data)
    else:
        if "balance_tea" not in data[user_id]:
            data[user_id]["balance_tea"] = 0.0
            save_data(data)
    return data

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="product_stars")],
        [InlineKeyboardButton(text="💎 TON Coins", callback_data="product_ton")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🔗 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="📄 Документы", callback_data="documents")],
        [InlineKeyboardButton(text="📢 Наш канал", url=f"https://t.me/{CHANNEL[1:]}")],
        [InlineKeyboardButton(text="🆘 Тех. поддержка", url=f"https://t.me/{ADMIN[1:]}")]
    ])

def get_documents_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", url="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19")],
        [InlineKeyboardButton(text="🔒 Политика конфиденциальности", url="https://telegra.ph/Politika-konfidencialnosti-04-01-26")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

def get_main_reply_keyboard(user_id: str):
    buttons = [[KeyboardButton(text="🔄 Перезапустить бота")]]
    if is_admin(user_id):
        buttons.append([KeyboardButton(text="🔑 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Вывести деньги", callback_data="withdraw")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

def get_payment_method_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔵 СБП (рубли)", callback_data="pay_sbp")],
        [InlineKeyboardButton(text="🪙 Криптовалюта", callback_data="pay_crypto")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

def get_confirm_wallet_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, уверен", callback_data="wallet_confirm")],
        [InlineKeyboardButton(text="❌ Нет, изменить", callback_data="wallet_change")]
    ])

def get_admin_order_keyboard(user_id: str, order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data=f"done_{user_id}_{order_id}")],
        [InlineKeyboardButton(text="❌ Ошибка", callback_data=f"error_{user_id}_{order_id}")]
    ])

def get_sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=f"https://t.me/{CHANNEL[1:]}")],
        [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="check_sub")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

def get_ref_keyboard(ref_link: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data="copy_ref")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

def get_admin_keyboard(user_id: str):
    kb = [
        [KeyboardButton(text="⭐ Изменить цену Stars")],
        [KeyboardButton(text="💎 Изменить цену TON")],
        [KeyboardButton(text="🔗 Изменить % реферальной программы")],
        [KeyboardButton(text="📢 Рассылка всем пользователям")],
    ]
    if is_owner(user_id):
        kb.append([KeyboardButton(text="💰 Выдать баланс пользователю")])
        kb.append([KeyboardButton(text="👑 Выдать админку")])
        kb.append([KeyboardButton(text="🗑 Забрать админку")])
        kb.append([KeyboardButton(text="📋 Список админов")])
    kb.append([KeyboardButton(text="🔙 Выйти из админ-панели")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_back_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Назад в админ-панель")]],
        resize_keyboard=True
    )

def validate_requisites(text: str) -> str:
    digits_only = re.sub(r'\D', '', text)
    if len(digits_only) == 16:
        return "card_16"
    elif len(digits_only) == 11 or (len(digits_only) == 12 and digits_only.startswith("+")):
        return "phone"
    elif len(digits_only) >= 12 and len(digits_only) <= 20:
        return "card_other"
    elif any(bank.lower() in text.lower() for bank in RUSSIAN_BANKS):
        return "bank_name"
    elif "@" in text:
        return "email"
    elif text.lower().startswith("+7") or text.lower().startswith("8"):
        return "phone_text"
    return "unknown"

async def check_subscription(user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(CHANNEL, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except:
        return False

async def broadcast_message(text: str):
    data = load_data()
    for uid in data.keys():
        try:
            await bot.send_message(int(uid), text)
        except:
            pass

async def notify_admins(text: str, reply_markup=None):
    for aid in admin_ids():
        try:
            await bot.send_message(aid, text, reply_markup=reply_markup)
        except:
            pass

async def create_platega_payment(amount: float, description: str, payment_method: int = None) -> dict:
    url = f"{PLATEGA_API}/transaction/process"
    headers = {
        "Content-Type": "application/json",
        "X-MerchantId": PLATEGA_MERCHANT_ID,
        "X-Secret": PLATEGA_SECRET
    }
    unique_id = uuid.uuid4().hex[:12]
    body = {
        "paymentDetails": {
            "amount": amount,
            "currency": "RUB"
        },
        "description": f"{description}",
        "return": RETURN_URL,
        "failedUrl": RETURN_URL,
        "payload": unique_id
    }
    if payment_method:
        body["paymentMethod"] = payment_method

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                text = await resp.text()
                if resp.status != 200:
                    print(f"Platega create error: {resp.status} {text}")
                    return {}
                return json.loads(text) if text else {}
    except Exception as e:
        print(f"Platega create exception: {e}")
        return {}

async def check_platega_status(transaction_id: str) -> dict:
    url = f"{PLATEGA_API}/transaction/{transaction_id}"
    headers = {
        "X-MerchantId": PLATEGA_MERCHANT_ID,
        "X-Secret": PLATEGA_SECRET,
        "Content-Type": "application/json"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                text = await resp.text()
                if resp.status != 200:
                    return {}
                return json.loads(text) if text else {}
    except Exception as e:
        print(f"Platega status exception: {e}")
        return {}

async def poll_payment(transaction_id: str, user_id: str, item_name: str, total: int, chat_id: int, method_name: str, product: str, order_id: int):
    poll_key = f"{transaction_id}_{user_id}"
    for i in range(180):
        await asyncio.sleep(10)
        if poll_key not in ACTIVE_POLLS:
            return
        try:
            status_data = await check_platega_status(transaction_id)
            if not status_data:
                continue
            status = status_data.get("status", "")
            if status == "CONFIRMED":
                ACTIVE_POLLS.pop(poll_key, None)
                user_data = get_user_data(user_id)
                invited_by = user_data[user_id].get("invited_by")
                if invited_by:
                    ref_bonus_rub = int(total * REF_PERCENT)
                    ref_bonus_tc = ref_bonus_rub / 100
                    ref_data = get_user_data(invited_by)
                    ref_data[invited_by]["balance"] = ref_data[invited_by].get("balance", 0) + ref_bonus_rub
                    ref_data[invited_by]["balance_tea"] = ref_data[invited_by].get("balance_tea", 0.0) + ref_bonus_tc
                    save_data(ref_data)
                    try:
                        await bot.send_message(
                            int(invited_by),
                            f"🎉 По вашей реферальной ссылке оплачена покупка!\n\n"
                            f"📦 Товар: {item_name}\n"
                            f"💵 Сумма покупки: {total} руб\n"
                            f"💰 Вам начислено: {ref_bonus_rub} руб\n"
                            f"🍵 Баланс Tea Coin: {ref_data[invited_by].get('balance_tea', 0.0)} TC"
                        )
                    except:
                        pass

                username = user_data[user_id].get("username", "не указан")
                try:
                    await bot.send_message(
                        chat_id,
                        f"✅ Ваш платёж подтверждён!\n\n"
                        f"📦 Товар: {item_name}\n"
                        f"💵 Сумма: {total} руб\n"
                        f"🆔 Номер заказа: #{order_id}\n\n"
                        f"Ожидайте пополнения"
                    )
                except:
                    pass

                if product == "ton":
                    USER_ORDER_DATA[user_id] = {
                        "order_id": order_id,
                        "ton_total": total,
                        "ton_item": item_name,
                        "ton_username": username,
                        "transaction_id": transaction_id,
                        "method_name": method_name
                    }
                    await notify_admins(
                        f"✅ Платёж подтверждён! (TON)\n\n"
                        f"👤 Пользователь: @{username}\n"
                        f"🆔 ID: {user_id}\n"
                        f"📦 Товар: {item_name}\n"
                        f"💵 Сумма: {total} руб\n"
                        f"💰 Способ: {method_name}\n"
                        f"🆔 Транзакция: {transaction_id}\n"
                        f"📋 Номер заказа: #{order_id}\n\n"
                        f"⏳ Ожидаем ввод TON кошелька"
                    )
                    await bot.send_message(
                        chat_id,
                        f"💎 Введите ваш TON кошелёк (начинается с @ или UQ...)\n\n"
                        f"⚠️ Внимание! Не перепутайте кошелёк, возврата не будет!",
                        reply_markup=get_back_keyboard()
                    )
                else:
                    await notify_admins(
                        f"✅ Платёж подтверждён!\n\n"
                        f"👤 Пользователь: @{username}\n"
                        f"🆔 ID: {user_id}\n"
                        f"📦 Товар: {item_name}\n"
                        f"💵 Сумма: {total} руб\n"
                        f"💰 Способ: {method_name}\n"
                        f"🆔 Транзакция: {transaction_id}\n"
                        f"📋 Номер заказа: #{order_id}",
                        reply_markup=get_admin_order_keyboard(user_id, order_id)
                    )
                return
            elif status in ("CANCELED", "DECLINED", "EXPIRED"):
                ACTIVE_POLLS.pop(poll_key, None)
                try:
                    await bot.send_message(chat_id, "❌ Платёж отменён или истёк. Попробуйте снова.")
                except:
                    pass
                return
        except:
            pass
    ACTIVE_POLLS.pop(poll_key, None)
    try:
        await bot.send_message(chat_id, "⏰ Время ожидания платежа истекло (30 минут). Платёж отменён. Попробуйте снова.")
    except:
        pass

@dp.callback_query(F.data.startswith("done_"))
async def admin_done(callback: types.CallbackQuery):
    _, target_user_id, order_id = callback.data.split("_")
    try:
        await bot.send_message(int(target_user_id), f"🎉 Пополнение средств прошло успешно!\n\n📋 Номер заказа: #{order_id}\nСпасибо за покупку! Приходите к нам ещё! 🍵")
    except:
        pass
    await callback.message.edit_text(callback.message.text + f"\n\n✅ Заказ #{order_id} выполнен!")

@dp.callback_query(F.data.startswith("error_"))
async def admin_error(callback: types.CallbackQuery):
    _, target_user_id, order_id = callback.data.split("_")
    try:
        await bot.send_message(int(target_user_id), f"❌ Возникла ошибка с вашим заказом #{order_id}.\n\nПожалуйста, обратитесь в поддержку {ADMIN}")
    except:
        pass
    await callback.message.edit_text(callback.message.text + f"\n\n❌ Заказ #{order_id} — ошибка!")

@dp.message(F.text == "🔄 Перезапустить бота")
async def restart_bot(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

@dp.message(F.text == "🔑 Админ-панель")
async def open_admin_panel(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        return
    await state.clear()
    await state.set_state(Purchase.choosing_product)
    await message.answer("Админ-панель:", reply_markup=get_admin_keyboard(user_id))

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if is_blacklisted(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    data = get_user_data(user_id)
    data[user_id]["username"] = message.from_user.username or ""
    save_data(data)

    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref"):
        ref_id = args[1][3:]
        if ref_id != user_id and ref_id in data:
            if user_id not in data[ref_id]["refs"]:
                data[ref_id]["refs"].append(user_id)
                data[user_id]["invited_by"] = ref_id
                save_data(data)
                try:
                    await bot.send_message(
                        int(ref_id),
                        f"🎉 По вашей реферальной ссылке зарегистрировался новый пользователь!\nТеперь у вас {len(data[ref_id]['refs'])} рефералов"
                    )
                except:
                    pass

    await state.clear()
    await state.set_state(Purchase.choosing_product)

    if not await check_subscription(message.from_user.id):
        await message.answer_photo(
            photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg",
            caption="🔔 Для использования бота необходимо подписаться на наш канал!\n\nПодпишитесь и нажмите кнопку проверки подписки ниже",
            reply_markup=get_sub_keyboard()
        )
        return

    data[user_id]["ref_link"] = f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"
    save_data(data)

    await message.answer_photo(
        photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg",
        caption="🍵 TeaTeam Shop\n\n✨ Добро пожаловать в наш магазин!\nЗдесь вы можете приобрести Telegram Stars и TON Coins по выгодным ценам\n\n🎁 Приглашайте друзей и получайте Tea Coin с их покупок!\n\nВыберите нужный раздел ниже:",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("giveadmin"))
async def cmd_giveadmin(message: types.Message):
    user_id = str(message.from_user.id)
    if int(user_id) == OWNER_ID or int(user_id) in admin_ids():
        await message.answer("🔑 Ваша админ-панель активирована!\n\nНажмите кнопку снизу для входа в админ-панель", reply_markup=get_main_reply_keyboard(user_id))

@dp.message(F.text == "🔙 Выйти из админ-панели")
async def exit_admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(str(message.from_user.id)):
        return
    await state.clear()
    await state.set_state(Purchase.choosing_product)
    await message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="🍵 TeaTeam Shop\n\nВыберите нужный раздел ниже:", reply_markup=get_main_keyboard())

@dp.message(F.text == "⭐ Изменить цену Stars")
async def admin_change_stars_price(message: types.Message, state: FSMContext):
    if not is_admin(str(message.from_user.id)):
        return
    await state.set_state(AdminStates.changing_stars_price)
    await message.answer(f"Текущая цена Stars: {STARS_PRICE_PER_ONE} руб за 1 звезду\n\nВведите новую цену за 1 звезду:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.changing_stars_price)
async def process_change_stars_price(message: types.Message, state: FSMContext):
    try:
        new_price = float(message.text.strip())
    except:
        await message.answer("❌ Введите число")
        return
    old_price = STARS_PRICE_PER_ONE
    cfg = load_config()
    cfg["stars_price_per_one"] = new_price
    save_config(cfg)
    reload_config()
    await state.clear()
    await message.answer(f"✅ Цена Stars изменена!\n\nСтарая цена: {old_price} руб/звезда\nНовая цена: {new_price} руб/звезда", reply_markup=get_admin_keyboard(str(message.from_user.id)))
    await broadcast_message(f"🔔 Обновление цен!\n\n⭐ Новая цена Telegram Stars: {new_price} руб за 1 звезду\nСтарая цена: {old_price} руб/звезда")

@dp.message(F.text == "💎 Изменить цену TON")
async def admin_change_ton_price(message: types.Message, state: FSMContext):
    if not is_admin(str(message.from_user.id)):
        return
    await state.set_state(AdminStates.changing_ton_price)
    await message.answer(f"Текущая цена TON: {TON_PRICE} руб за 1 TON\n\nВведите новую цену за 1 TON:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.changing_ton_price)
async def process_change_ton_price(message: types.Message, state: FSMContext):
    try:
        new_price = float(message.text.strip())
    except:
        await message.answer("❌ Введите число")
        return
    old_price = TON_PRICE
    cfg = load_config()
    cfg["ton_price"] = new_price
    save_config(cfg)
    reload_config()
    await state.clear()
    await message.answer(f"✅ Цена TON изменена!\n\nСтарая цена: {old_price} руб/TON\nНовая цена: {new_price} руб/TON", reply_markup=get_admin_keyboard(str(message.from_user.id)))
    await broadcast_message(f"🔔 Обновление цен!\n\n💎 Новая цена TON Coins: {new_price} руб за 1 TON\nСтарая цена: {old_price} руб/TON")

@dp.message(F.text == "🔗 Изменить % реферальной программы")
async def admin_change_ref_percent(message: types.Message, state: FSMContext):
    if not is_admin(str(message.from_user.id)):
        return
    await state.set_state(AdminStates.changing_ref_percent)
    await message.answer(f"Текущий процент реферальной программы: {load_config()['ref_percent']}%\n\nВведите новый процент:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.changing_ref_percent)
async def process_change_ref_percent(message: types.Message, state: FSMContext):
    try:
        new_percent = float(message.text.strip())
    except:
        await message.answer("❌ Введите число")
        return
    old_percent = load_config()["ref_percent"]
    cfg = load_config()
    cfg["ref_percent"] = new_percent
    save_config(cfg)
    reload_config()
    await state.clear()
    await message.answer(f"✅ Процент реферальной программы изменен!\n\nСтарый процент: {old_percent}%\nНовый процент: {new_percent}%", reply_markup=get_admin_keyboard(str(message.from_user.id)))
    await broadcast_message(f"🔔 Обновление реферальной программы!\n\n🔗 Новый процент с покупок рефералов: {new_percent}%\nСтарый процент: {old_percent}%")

@dp.message(F.text == "👑 Выдать админку")
async def admin_give_admin_start(message: types.Message, state: FSMContext):
    if not is_owner(str(message.from_user.id)):
        return
    await state.set_state(AdminStates.giving_admin)
    await message.answer("Введите ID пользователя которому хотите выдать админку:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.giving_admin)
async def admin_give_admin_process(message: types.Message, state: FSMContext):
    target_id = message.text.strip()
    if not target_id.isdigit():
        await message.answer("❌ Введите корректный ID")
        return
    cfg = load_config()
    if "admin_ids" not in cfg:
        cfg["admin_ids"] = [OWNER_ID]
    if int(target_id) not in cfg["admin_ids"]:
        cfg["admin_ids"].append(int(target_id))
        save_config(cfg)
        await state.clear()
        await message.answer(f"✅ Пользователю {target_id} выдана админка!\n\nПусть он напишет /giveadmin для активации", reply_markup=get_admin_keyboard(str(message.from_user.id)))
        try:
            await bot.send_message(int(target_id), f"👑 Вам выданы права администратора!\n\nНапишите /giveadmin для активации админ-панели")
        except:
            pass
    else:
        await state.clear()
        await message.answer("❌ Этот пользователь уже админ", reply_markup=get_admin_keyboard(str(message.from_user.id)))

@dp.message(F.text == "🗑 Забрать админку")
async def admin_remove_admin_start(message: types.Message, state: FSMContext):
    if not is_owner(str(message.from_user.id)):
        return
    await state.set_state(AdminStates.removing_admin)
    await message.answer("Введите ID пользователя у которого хотите забрать админку:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.removing_admin)
async def admin_remove_admin_process(message: types.Message, state: FSMContext):
    target_id = message.text.strip()
    if not target_id.isdigit():
        await message.answer("❌ Введите корректный ID")
        return
    if int(target_id) == OWNER_ID:
        await message.answer("❌ Нельзя забрать админку у владельца")
        return
    cfg = load_config()
    if int(target_id) in cfg.get("admin_ids", []):
        cfg["admin_ids"].remove(int(target_id))
        save_config(cfg)
        await state.clear()
        await message.answer(f"✅ У пользователя {target_id} забрана админка!", reply_markup=get_admin_keyboard(str(message.from_user.id)))
        try:
            await bot.send_message(int(target_id), "🗑 У вас забрали права администратора")
        except:
            pass
    else:
        await state.clear()
        await message.answer("❌ Этот пользователь не админ", reply_markup=get_admin_keyboard(str(message.from_user.id)))

@dp.message(F.text == "💰 Выдать баланс пользователю")
async def admin_give_balance_start(message: types.Message, state: FSMContext):
    if not is_owner(str(message.from_user.id)):
        await message.answer("❌ Только владелец может выдавать баланс")
        return
    await state.set_state(AdminStates.giving_balance_user)
    await message.answer("Введите ID или @username пользователя:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.giving_balance_user)
async def admin_give_balance_user(message: types.Message, state: FSMContext):
    target = message.text.strip().replace("@", "")
    target_id = None
    if target.isdigit():
        target_id = target
    else:
        data = load_data()
        for uid, user_data in data.items():
            if user_data.get("username", "").lower() == target.lower():
                target_id = uid
                break
    if not target_id:
        await message.answer("❌ Пользователь не найден")
        return
    await state.update_data(give_target=target_id)
    await state.set_state(AdminStates.giving_balance_amount)
    await message.answer(f"Пользователь: {target_id}\n\nВведите сумму в рублях для начисления:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.giving_balance_amount)
async def admin_give_balance_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
    except:
        await message.answer("❌ Введите число")
        return
    data = await state.get_data()
    target_id = data.get("give_target")
    target_data = get_user_data(target_id)
    target_data[target_id]["balance"] = target_data[target_id].get("balance", 0) + amount
    save_data(target_data)
    await state.clear()
    await message.answer(f"✅ Пользователю {target_id} начислено {amount} руб", reply_markup=get_admin_keyboard(str(message.from_user.id)))
    try:
        await bot.send_message(int(target_id), f"💰 На ваш баланс начислено {amount} руб!\n\nТекущий баланс: {target_data[target_id].get('balance', 0)} руб\nБаланс Tea Coin: {target_data[target_id].get('balance_tea', 0.0)} TC")
    except:
        pass

@dp.message(F.text == "📢 Рассылка всем пользователям")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if not is_admin(str(message.from_user.id)):
        return
    await state.set_state(AdminStates.sending_broadcast)
    await message.answer("Введите текст рассылки:", reply_markup=get_admin_back_keyboard())

@dp.message(AdminStates.sending_broadcast)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    text = message.text.strip()
    await broadcast_message(f"📢 Рассылка:\n\n{text}")
    await state.clear()
    await message.answer("✅ Рассылка отправлена всем пользователям!", reply_markup=get_admin_keyboard(str(message.from_user.id)))

@dp.message(F.text == "📋 Список админов")
async def admin_list(message: types.Message):
    if not is_owner(str(message.from_user.id)):
        return
    cfg = load_config()
    admin_list = cfg.get("admin_ids", [])
    admins_text = "📋 Список администраторов:\n\n"
    for i, aid in enumerate(admin_list, 1):
        data = load_data()
        user_info = data.get(str(aid), {})
        username = user_info.get("username", "нет")
        owner_mark = " 👑" if aid == OWNER_ID else ""
        admins_text += f"{i}. ID: {aid} (@{username}){owner_mark}\n"
    await message.answer(admins_text)

@dp.message(F.text == "🔙 Назад в админ-панель")
async def back_to_admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(str(message.from_user.id)):
        return
    await state.clear()
    await state.set_state(Purchase.choosing_product)
    await message.answer("Админ-панель:", reply_markup=get_admin_keyboard(str(message.from_user.id)))

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        return
    await state.set_state(Purchase.choosing_product)
    user_id = str(callback.from_user.id)
    user = get_user_data(user_id)[user_id]
    ref_count = len(user.get("refs", []))
    await callback.message.answer(f"👤 Ваш профиль\n\n💰 Баланс: {user.get('balance', 0)} руб\n🍵 Баланс Tea Coin: {user.get('balance_tea', 0.0)} TC\n👥 Рефералов: {ref_count}\n\nВыберите действие:", reply_markup=get_profile_keyboard())

@dp.callback_query(F.data == "referral")
async def show_referral(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        return
    await state.set_state(Purchase.choosing_product)
    user_id = str(callback.from_user.id)
    data = get_user_data(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"
    data[user_id]["ref_link"] = ref_link
    save_data(data)
    ref_count = len(data[user_id].get("refs", []))
    await callback.message.answer(f"🔗 Реферальная программа\n\nПриглашайте друзей и получайте {load_config()['ref_percent']}% с каждой их покупки в Tea Coin!\n\n👥 Ваших рефералов: {ref_count}\n🍵 Баланс Tea Coin: {data[user_id].get('balance_tea', 0.0)} TC\n\nВаша реферальная ссылка:\n{ref_link}", reply_markup=get_ref_keyboard(ref_link))

@dp.callback_query(F.data == "copy_ref")
async def copy_ref(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    ref_link = get_user_data(user_id)[user_id].get("ref_link", "")
    await callback.message.answer(f"📋 Ваша реферальная ссылка:\n\n{ref_link}\n\nНажмите на ссылку и скопируйте её")
    await callback.answer("Ссылка отправлена ниже", show_alert=True)

@dp.callback_query(F.data == "documents")
async def show_documents(callback: types.CallbackQuery):
    if not await check_subscription(callback.from_user.id):
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        return
    await callback.message.answer("📄 Документы:\n\nОзнакомьтесь с документами:", reply_markup=get_documents_keyboard())

@dp.callback_query(F.data == "withdraw")
async def start_withdraw(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        return
    await state.set_state(Purchase.choosing_product)
    user_id = str(callback.from_user.id)
    data = get_user_data(user_id)
    if data[user_id].get("balance_tea", 0.0) < MIN_WITHDRAW:
        await callback.message.answer(f"❌ Минимальная сумма вывода: {MIN_WITHDRAW} TC\n\nВаш баланс: {data[user_id].get('balance_tea', 0.0)} TC\nПродолжайте приглашать друзей чтобы накопить нужную сумму!")
        return
    await state.set_state(Withdraw.waiting_amount)
    await callback.message.answer(f"💸 Вывод средств\n\n🍵 Ваш баланс Tea Coin: {data[user_id].get('balance_tea', 0.0)} TC\nМинимальная сумма вывода: {MIN_WITHDRAW} TC\n1 TC = 100 руб\n\nВведите сумму для вывода в TC:", reply_markup=get_back_keyboard())

@dp.message(Withdraw.waiting_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = get_user_data(user_id)
    try:
        amount = float(message.text.strip())
    except:
        await message.answer("❌ Введите число")
        return
    if amount < MIN_WITHDRAW:
        await message.answer(f"❌ Минимальная сумма вывода: {MIN_WITHDRAW} TC")
        return
    if amount > data[user_id].get("balance_tea", 0.0):
        await message.answer(f"❌ Недостаточно средств на балансе\nВаш баланс: {data[user_id].get('balance_tea', 0.0)} TC")
        return
    await state.update_data(withdraw_amount=amount)
    await state.set_state(Withdraw.waiting_details)
    await message.answer(f"💸 Сумма вывода: {amount} TC ({int(amount * 100)} руб)\n\nВведите реквизиты для вывода:\n📌 Номер карты (16 цифр)\n📌 Или номер телефона (начиная с +7 или 8)\n📌 Или название банка и номер", reply_markup=get_back_keyboard())

@dp.message(Withdraw.waiting_details)
async def process_withdraw_details(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    details = message.text.strip()
    req_type = validate_requisites(details)
    if req_type == "unknown":
        await message.answer("❌ Неверный формат реквизитов\n\nПринимаются:\n📌 Номер карты (16 цифр подряд)\n📌 Номер телефона (+7... или 8...)\n📌 Название банка и реквизиты\n\nПопробуйте ещё раз:", reply_markup=get_back_keyboard())
        return
    if req_type in ("card_16", "card_other"):
        digits = re.sub(r'\D', '', details)
        if len(digits) != 16:
            await message.answer("❌ Номер карты должен содержать ровно 16 цифр\n\nПопробуйте ещё раз:", reply_markup=get_back_keyboard())
            return
        found_banks = [bank for bank in RUSSIAN_BANKS if bank.lower() in details.lower()]
        bank_note = f"\n🏛 Определён банк: {', '.join(found_banks[:3])}" if found_banks else ""
    elif req_type in ("phone", "phone_text"):
        digits = re.sub(r'\D', '', details)
        if len(digits) not in (11, 12):
            await message.answer("❌ Номер телефона указан некорректно\n\nПопробуйте ещё раз в формате +7XXXXXXXXXX:", reply_markup=get_back_keyboard())
            return
        bank_note = ""
    else:
        bank_note = ""
    user_data = get_user_data(user_id)
    user_data[user_id]["balance_tea"] = user_data[user_id].get("balance_tea", 0.0) - amount
    save_data(user_data)
    await state.clear()
    await state.set_state(Purchase.choosing_product)
    await message.answer(f"✅ Заявка на вывод создана!\n\n💵 Сумма: {amount} TC ({int(amount * 100)} руб)\n📋 Реквизиты: {details}{bank_note}\n\n⏳ Ожидайте обработки администратором", reply_markup=get_back_keyboard())
    await notify_admins(f"🔔 Новый запрос на вывод средств!\n\n👤 Пользователь: @{message.from_user.username or 'нет username'}\n🆔 ID: {user_id}\n💵 Сумма вывода: {amount} TC ({int(amount * 100)} руб)\n📋 Реквизиты: {details}{bank_note}\n\n💰 Остаток на балансе: {user_data[user_id].get('balance_tea', 0.0)} TC")

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery, state: FSMContext):
    if await check_subscription(callback.from_user.id):
        user_id = str(callback.from_user.id)
        data = get_user_data(user_id)
        data[user_id]["ref_link"] = f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"
        save_data(data)
        await state.clear()
        await state.set_state(Purchase.choosing_product)
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="🍵 TeaTeam Shop\n\n✨ Добро пожаловать в наш магазин!\nЗдесь вы можете приобрести Telegram Stars и TON Coins по выгодным ценам\n\n🎁 Приглашайте друзей и получайте Tea Coin с их покупок!\n\nВыберите нужный раздел ниже:", reply_markup=get_main_keyboard())
    else:
        await callback.answer("❌ Вы все еще не подписаны на канал", show_alert=True)

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        await state.clear()
        return
    await state.clear()
    await state.set_state(Purchase.choosing_product)
    await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="🍵 TeaTeam Shop\n\n✨ Добро пожаловать в наш магазин!\nЗдесь вы можете приобрести Telegram Stars и TON Coins по выгодным ценам\n\n🎁 Приглашайте друзей и получайте Tea Coin с их покупок!\n\nВыберите нужный раздел ниже:", reply_markup=get_main_keyboard())

@dp.callback_query(F.data.startswith("product_"))
async def choose_product(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        await state.clear()
        return
    product = callback.data.split("_")[1]
    await state.update_data(product=product)
    await state.set_state(Purchase.entering_amount)
    if product == "stars":
        photo = "https://i.ibb.co/xK5xhz0L/starsstars.jpg"
        caption = f"⭐ Вы выбрали товар: Telegram Stars\n\nВведите количество звезд от 50 до {MAX_STARS}\n\n💰 Цена: {STARS_PRICE_PER_ONE} руб за 1 звезду\n📌 Минимум: 50 звезд\n📊 Максимум: {MAX_STARS} звезд"
    else:
        photo = "https://i.ibb.co/mVZN1Xb6/tontontontotn.jpg"
        caption = f"💎 Вы выбрали товар: TON Coins\n\nВведите количество TON которое хотите приобрести\n\n💰 1 TON = {TON_PRICE} руб\n📊 Максимум: {MAX_TON} TON\n\n📌 Монеты поступят на ваш встроенный Telegram кошелёк"
    await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=get_back_keyboard())

@dp.message(Purchase.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        await message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        await state.clear()
        return
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Пожалуйста, введите целое число")
        return
    data = await state.get_data()
    product = data.get("product")
    if product == "stars":
        if amount < 50 or amount > MAX_STARS:
            await message.answer(f"❌ Неверное количество звезд\n\nМинимум: 50, максимум: {MAX_STARS}")
            return
        price = int(amount * STARS_PRICE_PER_ONE)
        item_name = f"{amount} звезд"
        user_data = get_user_data(str(message.from_user.id))
        username = user_data[str(message.from_user.id)].get("username", "")
        if not username:
            await state.set_state(Purchase.waiting_username)
            await state.update_data(amount=amount, price=price, item_name=item_name, product=product)
            await message.answer("⚠️ Для покупки Stars необходимо установить @username в Telegram.\n\nУстановите username в настройках Telegram и введите его сюда (без @):\nПример: ivanov123", reply_markup=get_back_keyboard())
            return
    else:
        if amount <= 0 or amount > MAX_TON:
            await message.answer(f"❌ Неверное количество TON\n\nМаксимум: {MAX_TON}")
            return
        price = int(amount * TON_PRICE)
        item_name = f"{amount} TON"
    await state.update_data(amount=amount, price=price, item_name=item_name, product=product)
    await state.set_state(Purchase.choosing_payment)
    await message.answer(f"📦 Вы ввели: {item_name}\n\n💵 Цена: {price} руб\n\nВыберите способ оплаты:", reply_markup=get_payment_method_keyboard())

@dp.message(Purchase.waiting_username)
async def process_username(message: types.Message, state: FSMContext):
    username = message.text.strip().replace("@", "")
    if not username or len(username) < 5:
        await message.answer("❌ Введите корректный username (минимум 5 символов)")
        return
    user_id = str(message.from_user.id)
    user_data = get_user_data(user_id)
    user_data[user_id]["username"] = username
    save_data(user_data)
    data = await state.get_data()
    price = data.get("price")
    item_name = data.get("item_name")
    product = data.get("product")
    await state.update_data(product=product)
    await state.set_state(Purchase.choosing_payment)
    await message.answer(f"✅ Username установлен: @{username}\n\n📦 Товар: {item_name}\n💵 Цена: {price} руб\n\n⚠️ Не меняйте username до окончания оплаты!\n\nВыберите способ оплаты:", reply_markup=get_payment_method_keyboard())

@dp.callback_query(Purchase.choosing_payment, F.data.startswith("pay_"))
async def choose_payment(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await callback.message.answer_photo(photo="https://i.ibb.co/DHFkZkXk/tea-minecragt.jpg", caption="⚠️ Вы отписались от канала!\nПодпишитесь заново чтобы продолжить использовать бота", reply_markup=get_sub_keyboard())
        await state.clear()
        return
    payment = callback.data.split("_")[1]
    data = await state.get_data()
    price = data.get("price")
    item_name = data.get("item_name")
    product = data.get("product")
    user_id = str(callback.from_user.id)
    method_map = {"sbp": (2, "СБП"), "crypto": (13, "Криптовалюта")}
    pm, method_name = method_map.get(payment, (2, "СБП"))
    unique_tag = uuid.uuid4().hex[:12]
    description = f"{item_name} | TgId:{user_id} | {unique_tag}"
    platega_response = await create_platega_payment(price, description, pm)
    if platega_response and "redirect" in platega_response:
        payment_url = platega_response["redirect"]
        transaction_id = platega_response.get("transactionId", "")
        warning = ""
        if product == "stars":
            username = get_user_data(user_id)[user_id].get("username", "")
            warning = f"⚠️ Не меняйте username (@{username}) до окончания оплаты!\n\n"
        await callback.message.answer(f"💳 Ссылка на оплату готова!\n\n📦 Товар: {item_name}\n💵 Сумма: {price} руб\n\n💰 Способ оплаты: {method_name}\n{warning}⏳ Ожидайте подтверждения платежа...", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)], [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]]))
        if transaction_id:
            order_id = get_next_order_id()
            poll_key = f"{transaction_id}_{user_id}"
            ACTIVE_POLLS[poll_key] = True
            asyncio.create_task(poll_payment(transaction_id, user_id, item_name, price, callback.message.chat.id, method_name, product, order_id))
    else:
        await callback.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.", reply_markup=get_back_keyboard())

@dp.message(Purchase.waiting_ton_wallet)
async def process_ton_wallet(message: types.Message, state: FSMContext):
    wallet = message.text.strip()
    if not wallet or len(wallet) < 5:
        await message.answer("❌ Введите корректный TON кошелёк")
        return
    await state.update_data(ton_wallet=wallet)
    await state.set_state(Purchase.confirm_ton_wallet)
    await message.answer(f"💎 TON кошелёк: {wallet}\n\n⚠️ Вы подтверждаете, что не ошиблись в кошельке?\nВозврат средств невозможен!", reply_markup=get_confirm_wallet_keyboard())

@dp.callback_query(Purchase.confirm_ton_wallet, F.data == "wallet_confirm")
async def confirm_ton_wallet(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    wallet = data.get("ton_wallet")
    user_id = str(callback.from_user.id)
    order_data = USER_ORDER_DATA.pop(user_id, {})
    order_id = order_data.get("order_id", data.get("order_id"))
    ton_total = order_data.get("ton_total", data.get("ton_total"))
    ton_item = order_data.get("ton_item", data.get("ton_item"))
    ton_username = order_data.get("ton_username", data.get("ton_username"))

    await state.clear()
    await callback.message.answer(f"✅ Кошелёк подтверждён!\n\n💎 Кошелёк: {wallet}\n📦 Товар: {ton_item}\n💵 Сумма: {ton_total} руб\n🆔 Номер заказа: #{order_id}\n\nОжидайте пополнения на указанный кошелёк", reply_markup=get_back_keyboard())
    await notify_admins(f"✅ Платёж подтверждён! (TON)\n\n👤 Пользователь: @{ton_username}\n🆔 ID: {user_id}\n📦 Товар: {ton_item}\n💵 Сумма: {ton_total} руб\n💎 TON кошелёк: {wallet}\n📋 Номер заказа: #{order_id}\n\n💰 Зачислите TON на указанный кошелёк", reply_markup=get_admin_order_keyboard(user_id, order_id))

@dp.callback_query(Purchase.confirm_ton_wallet, F.data == "wallet_change")
async def change_ton_wallet(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Purchase.waiting_ton_wallet)
    await callback.message.answer("Введите новый TON кошелёк:", reply_markup=get_back_keyboard())

@dp.message()
async def catch_ton_wallet(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id in USER_ORDER_DATA:
        await state.set_state(Purchase.waiting_ton_wallet)
        await process_ton_wallet(message, state)

async def main():
    cfg = load_config()
    data = load_data()
    for uid in data.keys():
        if uid not in cfg.get("all_users_ids", []):
            cfg["all_users_ids"].append(uid)
    if "admin_ids" not in cfg:
        cfg["admin_ids"] = [OWNER_ID]
    save_config(cfg)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())