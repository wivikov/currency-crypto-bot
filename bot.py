from http.client import responses
import telebot
import os
from dotenv import load_dotenv
import requests
from telebot import types
import time
from db import Session, Conversion

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)
user_history = {}

#/start
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('/rates')
    btn2 = types.KeyboardButton('/convert')
    btn3 = types.KeyboardButton('/crypto')
    btn4 = types.KeyboardButton('/history')
    markup.add(btn1, btn2, btn3, btn4)

    bot.send_message(
        message.chat.id,
        "Hello! 👋\nI’m a bot for currency and cryptocurrency exchange.\n\n"
        "Commands are also available via the buttons ⬇️",
    reply_markup=markup
    )




def get_exchange_rates(base_currency='USD'):
    url = f'https://open.er-api.com/v6/latest/{base_currency}'
    response = requests.get(url)
    data = response.json()

    rates = data.get("rates", {})
    return rates

#/rates
@bot.message_handler(commands=['rates'])
def send_rates(message):
    rates = get_exchange_rates()

    text = "Current exchange rates (against USD):\n"
    for currency in ['UAH', 'EUR', 'GBP']:
        rate = rates.get(currency)
        if rate:
            text += f"1 USD → {rate:.2f} {currency}\n"

    bot.send_message(message.chat.id, text)


def convert_currency(amount, from_currency, to_currency):
    rates = get_exchange_rates(base_currency=from_currency)

    to_rate = rates.get(to_currency)

    if to_rate is None:
        return None

    result = amount * to_rate
    return result

#/convert
@bot.message_handler(commands=['convert'])
def convert_command_start(message):
    markup = types.InlineKeyboardMarkup()
    currencies = ['USD', 'EUR', 'UAH', 'GBP', 'BTC', 'ETH']
    for currency in currencies:
        btn = types.InlineKeyboardButton(currency, callback_data=f"convert_from_{currency}")
        markup.add(btn)

    bot.send_message(
        message.chat.id,
        "💱 Select the currency to convert from:",
        reply_markup=markup
    )

cached_rates = {}
rates_timestamp = 0
CACHE_TIME = 300
def get_cached_exchange_rates(base_currency='USD'):
    global cached_rates, rates_timestamp
    if time.time() - rates_timestamp > CACHE_TIME:
        print("🔄 Updating rates from the API...")
        url = f'https://open.er-api.com/v6/latest/{base_currency}'
        response = requests.get(url)
        data = response.json()
        cached_rates = data.get("rates", {})
        rates_timestamp = time.time()
    else:
        print("✅ Using cached rates.")

    return cached_rates

@bot.callback_query_handler(func=lambda call: call.data.startswith('convert_from_'))
def handle_convert_from(call):
    from_currency = call.data.split('_')[-1]
    bot.answer_callback_query(call.id)



    markup = types.InlineKeyboardMarkup()
    currencies = ['USD', 'EUR','UAH','GBP','BTC','ETH']
    for currency in currencies:
        if currency != from_currency:
            btn = types.InlineKeyboardButton(currency, callback_data=f"convert_to_{from_currency}_{currency}")
            markup.add(btn)

    bot.send_message(
        call.message.chat.id,
        "Select the currency to convert to:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('convert_to_'))
def handle_convert_to(call):
    parts = call.data.split('_')
    from_currency = parts[-2]
    to_currency = parts[-1]
    bot.answer_callback_query(call.id)

    bot.send_message(call.message.chat.id, f"Chosen: {from_currency} → {to_currency}. Enter the amount to convert:")
    bot.register_next_step_handler(call.message, process_amount_input, from_currency, to_currency)

def process_amount_input(message, from_currency, to_currency):
    try:
        amount = float(message.text)
        crypto_currencies = ['BTC', 'ETH']

        if from_currency in crypto_currencies or to_currency in crypto_currencies:
            url = 'https://api.coingecko.com/api/v3/simple/price'
            ids_map = {'BTC': 'bitcoin', 'ETH': 'ethereum'}
            if from_currency in crypto_currencies:
                from_id = ids_map.get(from_currency)
                to_vs = to_currency.lower()
                params = {
                    'ids': from_id,
                    'vs_currencies': to_vs
                }
                response = requests.get(url, params=params)
                data = response.json()

                price = data.get(from_id, {}).get(to_vs)
                if price is None:
                    bot.send_message(message.chat.id, "❌ Failed to retrieve cryptocurrency rate.")
                    return

                result = amount * price
                reply_text = f"✅ {amount} {from_currency} = {result:.8f} {to_currency} 💱"

            else:
                # якщо BTC/ETH → фіат → використовуємо CoinGecko навпаки
                to_id = ids_map.get(to_currency)
                from_vs = from_currency.lower()
                params = {
                    'ids': to_id,
                    'vs_currencies': from_vs
                }
                response = requests.get(url, params=params)
                data = response.json()

                price = data.get(to_id, {}).get(from_vs)
                if price is None:
                    bot.send_message(message.chat.id, "❌ Failed to retrieve cryptocurrency rate.")
                    return

                result = amount / price
                reply_text = f"✅ {amount} {from_currency} = {result:.8f} {to_currency} 💱"

        else:
            rates = get_cached_exchange_rates(base_currency=from_currency)
            to_rate = rates.get(to_currency)

            if to_rate is None:
                bot.send_message(message.chat.id, "❌ Failed to retrieve currency rate. Please check the entered currencies.")
                return

            result = amount * to_rate
            reply_text = f"✅ {amount} {from_currency} = {result:.2f} {to_currency} 💱"

        # ОДИН раз відправляємо повідомлення + записуємо в history
        bot.send_message(message.chat.id, reply_text)

        chat_id = message.chat.id
        history = user_history.setdefault(chat_id, [])
        if from_currency in crypto_currencies or to_currency in crypto_currencies:
            formatted_result = f"{result:.8f}"
        else:
            formatted_result = f"{result:.2f}"

        history.append(f"{amount} {from_currency} → {formatted_result} {to_currency}")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ An error occurred: {str(e)}")


    session = Session()
    conversion = Conversion(
      user_id=chat_id,
      from_currency=from_currency,
      to_currency=to_currency,
      amount=amount,
      result=result
    )
    session.add(conversion)
    session.commit()
    session.close()

            
#/crypto
@bot.message_handler(commands=['crypto'])
def send_crypto_rates(message):
    url = 'https://api.coingecko.com/api/v3/simple/price'
    params = {
        'ids': "bitcoin,ethereum,ethereum,tether",
        'vs_currencies': 'usd,eur,uah'
    }
    response = requests.get(url, params=params)
    data = response.json()

    text = "💰 Current cryptocurrency rates:\n"
    btc = data.get('bitcoin', {})
    eth = data.get('ethereum', {})
    usdt = data.get('tether', {})

    text += "\n🪙 Bitcoin (BTC):\n"
    for cur, price in btc.items():
        text += f"1 BTC → {price} {cur.upper()}\n"
    text += "\n🪙 Ethereum (ETH):\n"
    for cur, price in eth.items():
        text += f"1 ETH → {price} {cur.upper()}\n"
    text += "\n🪙 Tether (USDT):\n"
    for cur, price in usdt.items():
        text += f"1 USDT → {price} {cur.upper()}\n"


    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['history'])
def send_history(message):
    chat_id = message.chat.id
    session = Session()
    conversions = (
        session.query(Conversion)
        .filter_by(user_id=chat_id)
        .order_by(Conversion.id.desc())
        .limit(10)
        .all()
    )
    session.close()

    if not conversions:
        bot.send_message(chat_id, "ℹ️ You don't have any conversion history in the database.")
    else:
        text = "📝 Your recent conversion history:\n\n"
        for c in conversions:
            formatted = f"{c.amount:.2f} {c.from_currency} → {c.result:.4f} {c.to_currency}"
            text += f"{formatted}\n"
        bot.send_message(chat_id, text)


print("Bot has been started...")
bot.infinity_polling(none_stop=True)