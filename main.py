import requests
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8798963962:AAEfjHv-Rm4fpWcc9PNsS-DOU6N02HN0cQY"  
CHANNEL_ID = "-1003964096231"             
THRESHOLD_PERCENT = 0.5                # Порог разницы в процентах
CHECK_INTERVAL = 300                   # Пауза между проверками (300 секунд = 5 минут)
DAILY_INTERVAL = 86400                 # 24 часа в секундах (для суточного отчета)
# =============================================

bot = telebot.TeleBot(BOT_TOKEN)

def get_bybit_opportunities():
    """Получает данные с биржи и ищет связки, где Индексная цена > Маркировочной"""
    url = "https://api.bybit.com/v5/market/tickers"
    params = {"category": "linear"}
    opportunities = []

    try:
        response = requests.get(url, params=params).json()
        if response.get("retCode") == 0:
            for ticker in response["result"]["list"]:
                mark_price = float(ticker["markPrice"])
                index_price = float(ticker["indexPrice"])
                
                if mark_price == 0:
                    continue
                
                if index_price > mark_price:
                    diff_percent = ((index_price - mark_price) / mark_price) * 100
                    
                    if diff_percent > THRESHOLD_PERCENT:
                        opportunities.append({
                            "symbol": ticker["symbol"],
                            "mark": mark_price,
                            "index": index_price,
                            "diff": diff_percent
                        })
    except Exception as e:
        print(f"Ошибка при запросе к Bybit: {e}")
        
    opportunities.sort(key=lambda x: x["diff"], reverse=True)
    return opportunities

def send_telegram_message(pairs, is_daily=False):
    """Формирует и отправляет сообщение со списком переданных связок"""
    if not pairs:
        return

    # Разные заголовки для суточного отчета и для новых находок
    if is_daily:
        text = f"🗓 **СУТОЧНЫЙ ОТЧЕТ: Все текущие расхождения (> {THRESHOLD_PERCENT}%)** 🗓\n\n"
    else:
        text = f"🚨 **НОВЫЕ СВЯЗКИ (Индекс > Маркировки > {THRESHOLD_PERCENT}%)** 🚨\n\n"
    
    markup = InlineKeyboardMarkup()
    buttons = []

    # Берем топ-15 связок
    for p in pairs[:15]:
        symbol = p["symbol"]
        text += f"🔹 **{symbol}**\n"
        text += f"Маркировочная: `{p['mark']}`\n"
        text += f"Индексная: `{p['index']}`\n"
        text += f"Разница: 🔴 **{p['diff']:.2f}%**\n\n"
        
        trade_url = f"https://www.bybit.com/trade/usdt/{symbol}"
        buttons.append(InlineKeyboardButton(text=f"📊 Торговать {symbol}", url=trade_url))

    markup.add(*buttons)
    text += "⏱ _Данные обновлены_"

    try:
        bot.send_message(
            chat_id=CHANNEL_ID, 
            text=text, 
            parse_mode="Markdown", 
            reply_markup=markup,
            disable_web_page_preview=True
        )
        report_type = "Суточный отчет" if is_daily else "Новые связки"
        print(f"[{report_type}] Отправлено {len(pairs[:15])} пар в канал.")
    except Exception as e:
        print(f"Ошибка при отправке в Telegram: {e}")

if __name__ == "__main__":
    print("Бот запущен. Умный режим активирован.")
    
    known_symbols = set() # Здесь храним монеты, о которых уже сообщили
    last_daily_report = 0 # Время последней суточной рассылки (0 = отправит сразу при запуске)
    
    while True:
        try:
            print("Проверяю рынок Bybit...")
            current_time = time.time()
            all_current_pairs = get_bybit_opportunities()
            
            # Собираем только названия монет из текущего запроса
            current_symbols = {p["symbol"] for p in all_current_pairs}
            
            # Проверяем, прошло ли 24 часа с момента последнего суточного отчета
            if current_time - last_daily_report >= DAILY_INTERVAL:
                if all_current_pairs:
                    send_telegram_message(all_current_pairs, is_daily=True)
                last_daily_report = current_time
            else:
                # Ищем монеты, которых не было в прошлом списке (новые)
                new_symbols = current_symbols - known_symbols
                
                if new_symbols:
                    # Отфильтровываем из всех пар только новые
                    new_pairs = [p for p in all_current_pairs if p["symbol"] in new_symbols]
                    send_telegram_message(new_pairs, is_daily=False)
                else:
                    print("Новых связок не найдено. Ждем...")

            # Обновляем память бота актуальными монетами
            known_symbols = current_symbols

        except Exception as e:
            print(f"Системная ошибка в главном цикле: {e}")
            
        # Спим 5 минут до следующей проверки
        time.sleep(CHECK_INTERVAL)