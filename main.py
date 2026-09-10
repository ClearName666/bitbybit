import requests
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8798963962:AAEfjHv-Rm4fpWcc9PNsS-DOU6N02HN0cQY"  # Обязательно перевыпусти токен в BotFather!
CHANNEL_ID = "-1003964096231"             
THRESHOLD_PERCENT = 0.5                # Порог разницы в процентах (Индекс > Маркировка)
MIN_GROWTH_PERCENT = 5               # Минимальный рост монеты в % для отправки
GROWTH_TIME_WINDOW = 300              # Окно времени для расчета роста (в секундах, 3600 = 1 час)
CHECK_INTERVAL = 300                   # Пауза между проверками (300 секунд = 5 минут)
DAILY_INTERVAL = 86400                 # 24 часа в секундах (для суточного отчета)
# =============================================

bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для хранения истории цен: { "BTCUSDT": [(timestamp, price), ...] }
price_history = {}

def get_bybit_opportunities(current_time):
    """Получает данные с биржи и ищет связки, где Индекс > Маркировки, а монета растет"""
    url = "https://api.bybit.com/v5/market/tickers"
    params = {"category": "linear"}
    opportunities = []

    try:
        response = requests.get(url, params=params).json()
        if response.get("retCode") == 0:
            tickers = response["result"]["list"]

            # 1. Сначала обновляем историю цен для всех монет
            for ticker in tickers:
                symbol = ticker["symbol"]
                mark_price = float(ticker["markPrice"])
                
                if mark_price == 0:
                    continue
                
                if symbol not in price_history:
                    price_history[symbol] = []
                    
                # Записываем текущую цену
                price_history[symbol].append((current_time, mark_price))
                
                # Очищаем старые данные, оставляем только цены за последний час (GROWTH_TIME_WINDOW)
                price_history[symbol] = [(t, p) for t, p in price_history[symbol] if current_time - t <= GROWTH_TIME_WINDOW]

            # 2. Ищем подходящие возможности
            for ticker in tickers:
                mark_price = float(ticker["markPrice"])
                index_price = float(ticker["indexPrice"])
                symbol = ticker["symbol"]
                
                if mark_price == 0:
                    continue
                
                if index_price > mark_price:
                    diff_percent = ((index_price - mark_price) / mark_price) * 100
                    
                    if diff_percent > THRESHOLD_PERCENT:
                        # Получаем самую старую цену за последний час из нашей истории
                        history = price_history[symbol]
                        oldest_price = history[0][1] 
                        
                        if oldest_price > 0:
                            growth_percent = ((mark_price - oldest_price) / oldest_price) * 100
                        else:
                            growth_percent = 0
                            
                        # ФИЛЬТР: Монета должна вырасти как минимум на MIN_GROWTH_PERCENT
                        if growth_percent >= MIN_GROWTH_PERCENT:
                            opportunities.append({
                                "symbol": symbol,
                                "mark": mark_price,
                                "index": index_price,
                                "diff": diff_percent,
                                "growth": growth_percent # Добавили показатель роста, чтобы вывести в телеграм
                            })
    except Exception as e:
        print(f"Ошибка при запросе к Bybit: {e}")
        
    opportunities.sort(key=lambda x: x["diff"], reverse=True)
    return opportunities

def send_telegram_message(pairs, is_daily=False):
    """Формирует и отправляет сообщение со списком переданных связок"""
    if not pairs:
        return

    if is_daily:
        text = f"🗓 **СУТОЧНЫЙ ОТЧЕТ: Все текущие расхождения (> {THRESHOLD_PERCENT}%)** 🗓\n\n"
    else:
        text = f"🚨 **НОВЫЕ СВЯЗКИ (Индекс > Маркировки > {THRESHOLD_PERCENT}%)** 🚨\n\n"
    
    markup = InlineKeyboardMarkup()
    buttons = []

    for p in pairs[:15]:
        symbol = p["symbol"]
        text += f"🔹 **{symbol}**\n"
        text += f"Маркировочная: `{p['mark']}`\n"
        text += f"Индексная: `{p['index']}`\n"
        # Немного обновил текст вывода, чтобы ты видел, насколько выросла монета за час
        text += f"Разница: 🔴 **{p['diff']:.2f}%** | Рост (1ч): 📈 **{p['growth']:.2f}%**\n\n"
        
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
    print("Бот запущен. Умный режим (с фильтром роста) активирован.")
    
    known_symbols = set() 
    last_daily_report = 0 
    
    while True:
        try:
            print("Проверяю рынок Bybit...")
            current_time = time.time()
            
            # Теперь передаем текущее время внутрь функции для расчетов
            all_current_pairs = get_bybit_opportunities(current_time)
            
            current_symbols = {p["symbol"] for p in all_current_pairs}
            
            if current_time - last_daily_report >= DAILY_INTERVAL:
                if all_current_pairs:
                    send_telegram_message(all_current_pairs, is_daily=True)
                last_daily_report = current_time
            else:
                new_symbols = current_symbols - known_symbols
                
                if new_symbols:
                    new_pairs = [p for p in all_current_pairs if p["symbol"] in new_symbols]
                    send_telegram_message(new_pairs, is_daily=False)
                else:
                    print("Новых подходящих связок не найдено. Ждем...")

            known_symbols = current_symbols

        except Exception as e:
            print(f"Системная ошибка в главном цикле: {e}")
            
        time.sleep(CHECK_INTERVAL)