import ccxt
from ml import predict_future_price

# Функции для получения рынков
def get_bybit_markets():
    return list(bybit_markets)


def get_okx_markets():
    return list(okx_markets)


def get_mexc_markets():
    return list(mexc_markets)


# Функция для получения цены актива
def fetch_price(exchange, coin):
    ticker = exchange.fetch_ticker(coin)
    return ticker['last']


# Генерация данных о рынках
def generate_market_data(coins, exchanges):
    market_data = {}
    for coin in coins:
        prices = [fetch_price(exchange, coin) for exchange in exchanges.values()]
        market_data[coin] = dict(zip(exchanges.keys(), prices))
    return market_data


def fetch_last_20_prices(pair):
    """
    Получает последние 20 значений 'close' цены актива с минимальным таймфреймом.
    """
    exchange = exchanges['bybit']
    try:
        # fetch_ohlcv возвращает список свечей [timestamp, open, high, low, close, volume]
        ohlcv = exchange.fetch_ohlcv(pair, timeframe='5m', limit=20)
        return [candle[4] for candle in ohlcv]  # берем только цены закрытия (close)
    except Exception as e:
        print(f"Ошибка при получении данных для {pair} с {exchange.name}: {e}")
        return []


# Главная функция
def mainn():
    return generate_market_data(top_25_expensive_coins, exchanges)


# Инициализация бирж
exchanges = {
    'bybit': ccxt.bybit(),
    'okx': ccxt.okx(),
    'mexc': ccxt.mexc()
}

# Топ-25 монет
top_25_expensive_coins = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'TON/USDT',
    'LTC/USDT', 'BCH/USDT', 'DOT/USDT', 'LINK/USDT', 'AAVE/USDT',
    'ATOM/USDT', 'FIL/USDT', 'NEAR/USDT', 'SOL/USDT', 'AVAX/USDT',
    'ALGO/USDT', 'MANA/USDT', 'SAND/USDT',
    'XTZ/USDT', 'ICP/USDT', 'GRT/USDT', 'EGLD/USDT'
]

# Загрузка рынков для каждой биржи
bybit = ccxt.bybit()
okx = ccxt.okx()
mexc = ccxt.mexc()

bybit_markets = bybit.load_markets()
okx_markets = okx.load_markets()
mexc_markets = mexc.load_markets()
