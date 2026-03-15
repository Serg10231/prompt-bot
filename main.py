import logging
import os
from typing import Dict, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

# Настройки логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== Конфигурация =====
TOKEN = "8147882773:AAF6MZupO9hYfk4zHcUPx9HQ7wZzyaxuR8A"
CURRENCY = "XTR"  # XTR - Telegram Stars
PRODUCTS_FILE = "products.txt"

# Твой бесплатный промпт (шикарный!)
FREE_PROMPT = (
    "Masterpiece cinematic shot from a high-end sci-fi film. "
    "A colossal, detailed exoplanet fills the left third of the frame, its surface a mesmerizing blend of velvet-dark dust and crystal-clear ice that glows from within as if lit by tiny suns. "
    "The planet's thin, elegant rings catch the light of a distant, unseen star, casting a soft prismatic glow. "
    "The right side of the image is the infinite deep cosmos, scattered with brilliant, sharp pinpricks of stars and the faint, colorful dust of a distant nebula. "
    "Extreme detail, 8k resolution, Unreal Engine 5 render, volumetric lighting, rich deep blues, vibrant magentas, and golden highlights. "
    "Vertical orientation, 9:16 aspect ratio, perfect for a phone wallpaper."
)

# ===== Данные =====
PRODUCTS: Dict[str, Tuple[str, int]] = {}  # название -> (имя_файла.pdf, цена)

def load_products(file_path: str) -> List[Tuple[str, str, int]]:
    """Загружает товары из текстового файла."""
    products: List[Tuple[str, str, int]] = []
    if not os.path.exists(file_path):
        logger.error("Файл с товарами не найден: %s", file_path)
        return products
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) != 3:
                logger.warning("Неправильная строка в products.txt: %s", line)
                continue
            name, pdf_file, price_s = parts
            try:
                price = int(price_s)
            except ValueError:
                logger.warning("Неверная цена для товара %s: %s", name, price_s)
                continue
            products.append((name.strip(), pdf_file.strip(), price))
    return products

def load_all_products():
    """Обновляет глобальный словарь товаров."""
    global PRODUCTS
    items = load_products(PRODUCTS_FILE)
    PRODUCTS = {name: (pdf, price) for (name, pdf, price) in items}

# ===== Обработчики =====

async def start(update: Update, context: CallbackContext) -> None:
    """Команда /start: показывает приветствие и кнопки товаров."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Загружаем актуальные товары из файла
    load_all_products()

    if not PRODUCTS:
        await context.bot.send_message(
            chat_id=chat_id, 
            text="📦 Товары временно недоступны. Попробуйте позже."
        )
        return

    # Создаем кнопки для каждого товара
    keyboard = []
    row = []
    
    for i, name in enumerate(sorted(PRODUCTS.keys()), 1):
        btn = InlineKeyboardButton(
            text=f"{name} — {PRODUCTS[name][1]} ⭐", 
            callback_data=f"BUY::{name}"
        )
        row.append(btn)
        if i % 2 == 0:  # по 2 кнопки в ряд
            keyboard.append(row)
            row = []
    
    if row:  # добавляем последний ряд, если остались кнопки
        keyboard.append(row)

    # Добавляем кнопку с бесплатным промптом
    keyboard.append([
        InlineKeyboardButton(text="🎁 Бесплатный промпт", callback_data="PROMPT::FREE")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✨ Добро пожаловать, {user.first_name}!\n\n"
             "🎨 Здесь ты можешь купить готовые промпты для создания красивых обоев.\n"
             "👇 Выбери тему:",
        reply_markup=reply_markup
    )

async def button(update: Update, context: CallbackContext) -> None:
    """Обрабатывает нажатия на инлайн-кнопки."""
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat.id

    # ----- Обработка покупки -----
    if data.startswith("BUY::"):
        item_name = data.split("::", 1)[1]
        
        if item_name not in PRODUCTS:
            await query.edit_message_text("❌ Такого товара нет.")
            return
        
        pdf_file, price = PRODUCTS[item_name]
        
        # Создаем счет для оплаты Stars
        prices = [LabeledPrice(label=item_name, amount=price * 100)]  # Stars принимает в копейках (1 руб = 100)
        
        # Кнопка для оплаты
        keyboard = [[InlineKeyboardButton("⭐ Оплатить Stars", pay=True)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_invoice(
                chat_id=chat_id,
                title=item_name,
                description=f"Набор промптов на тему: {item_name}",
                payload=f"PAYLOAD_{item_name}",
                provider_token="",  # Пустой токен = оплата через Stars
                currency=CURRENCY,
                prices=prices,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.exception("Ошибка отправки счета: %s", e)
            await query.edit_message_text("❌ Не удалось создать счет. Попробуйте позже.")
        
        return

    # ----- Обработка бесплатного промпта -----
    if data.startswith("PROMPT::"):
        prompt_key = data.split("::", 1)[1]
        if prompt_key == "FREE":
            await query.edit_message_text("🎁 Вот твой бесплатный промпт:")
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"```\n{FREE_PROMPT}\n```",
                parse_mode="Markdown"
            )
            
            # Возвращаем клавиатуру с товарами
            await start(update, context)
        else:
            await query.edit_message_text("❌ Неизвестный промпт.")
        return

async def precheckout(update: Update, context: CallbackContext) -> None:
    """Проверка перед оплатой (обязательно для Stars)."""
    query = update.pre_checkout_query
    await query.answer(ok=True)  # Всегда отвечаем ok для Stars

async def successful_payment(update: Update, context: CallbackContext) -> None:
    """Отправляет PDF после успешной оплаты."""
    chat_id = update.effective_chat.id
    payload = update.message.successful_payment.invoice_payload
    
    # Извлекаем название товара из payload
    if payload.startswith("PAYLOAD_"):
        item_name = payload.replace("PAYLOAD_", "")
    else:
        item_name = list(PRODUCTS.keys())[0]  # fallback на первый товар
    
    # Отправляем файл
    try:
        if item_name in PRODUCTS:
            pdf_file, _ = PRODUCTS[item_name]
            file_path = os.path.join(os.getcwd(), pdf_file)
            
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=pdf_file,
                        caption=f"✅ Спасибо за покупку!\nВот твой набор промптов: **{item_name}**",
                        parse_mode="Markdown"
                    )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ Оплата прошла, но файл временно недоступен. Мы уже чиним это!"
                )
                logger.error(f"Файл не найден: {pdf_file}")
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Оплата прошла успешно! Спасибо за покупку."
            )
    except Exception as e:
        logger.exception("Ошибка отправки PDF: %s", e)
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ Оплата прошла, но произошла ошибка при отправке файла. Напиши @твой_юзернейм"
        )

def error_handler(update: object, context: CallbackContext) -> None:
    """Глобальная обработка ошибок."""
    logger.exception("Ошибка: %s", context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Произошла ошибка. Попробуйте еще раз или позже."
            )
    except:
        pass

# ===== Запуск =====
def main():
    """Главная функция запуска бота."""
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.StatusUpdate.PAYMENT, successful_payment))
    app.add_pre_checkout_query_handler(precheckout)
    app.add_error_handler(error_handler)

    # Запускаем бота
    logger.info("🚀 Бот @PromptScreenBot запущен!")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")