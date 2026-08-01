import requests
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8798963962:AAEfjHv-Rm4fpWcc9PNsS-DOU6N02HN0cQY"  # Вставь сюда токен, который дал BotFather
CHANNEL_ID = "-1003964096231"             # Юзернейм твоего канала (например, @my_crypto_signals)
THRESHOLD_PERCENT = 0.5                # Порог разницы в процентах
CHECK_INTERVAL = 300                   # Пауза между проверками (300 секунд = 5 минут)
# =============================================

bot = telebot.TeleBot(BOT_TOKEN)

def get_bybit_opportunities():
    """Получает данные с биржи и возвращает список найденных связок"""
    url = "https://api.bybit.com/v5/market/tickers"
    params = {"category": "linear"}
    opportunities = []

    try:
        response = requests.get(url, params=params).json()
        if response.get("retCode") == 0:
            for ticker in response["result"]["list"]:
                last_price = float(ticker["lastPrice"])
                index_price = float(ticker["indexPrice"])
                
                if index_price == 0:
                    continue
                
                diff_percent = abs(last_price - index_price) / index_price * 100
                
                if diff_percent > THRESHOLD_PERCENT:
                    opportunities.append({
                        "symbol": ticker["symbol"],
                        "last": last_price,
                        "index": index_price,
                        "diff": diff_percent
                    })
    except Exception as e:
        print(f"Ошибка при запросе к Bybit: {e}")
        
    # Сортируем список по убыванию разницы (сначала самые жирные спреды)
    opportunities.sort(key=lambda x: x["diff"], reverse=True)
    return opportunities

def send_channel_update():
    """Формирует одно большое сообщение и отправляет в канал"""
    print("Проверяю рынок Bybit...")
    pairs = get_bybit_opportunities()
    
    if not pairs:
        print(f"Связок с разницей > {THRESHOLD_PERCENT}% не найдено. Ждем дальше.")
        return # Если ничего не нашли, сообщение не отправляем

    # Формируем заголовок сообщения
    text = f"🚨 **Обнаружены сильные расхождения цен (> {THRESHOLD_PERCENT}%)** 🚨\n\n"
    
    markup = InlineKeyboardMarkup()
    buttons = []

    # Берем топ-15 связок, чтобы не превысить лимит длины сообщения в Telegram
    for p in pairs[:15]:
        symbol = p["symbol"]
        text += f"🔹 **{symbol}**\n"
        text += f"Текущая: `{p['last']}`\n"
        text += f"Индексная: `{p['index']}`\n"
        text += f"Разница: 🔴 **{p['diff']:.2f}%**\n\n"
        
        # Создаем кнопку-ссылку для перехода прямо на торговую пару Bybit
        trade_url = f"https://www.bybit.com/trade/usdt/{symbol}"
        buttons.append(InlineKeyboardButton(text=f"📊 Торговать {symbol}", url=trade_url))

    # Добавляем кнопки в клавиатуру (по 2 в ряд)
    markup.add(*buttons)
    text += "⏱ _Данные обновлены_"

    try:
        # Отправляем сообщение в канал
        bot.send_message(
            chat_id=CHANNEL_ID, 
            text=text, 
            parse_mode="Markdown", 
            reply_markup=markup,
            disable_web_page_preview=True # Отключаем превью ссылок, чтобы не засорять чат
        )
        print(f"Отправлено большое сообщение с {len(pairs[:15])} парами в канал.")
    except Exception as e:
        print(f"Ошибка при отправке в Telegram: {e}")

if __name__ == "__main__":
    print("Бот запущен. Цикл обновления: 5 минут.")
    
    # Бесконечный цикл с задержкой 5 минут
    while True:
        send_channel_update()
        time.sleep(CHECK_INTERVAL)