"""
API модуль для работы с криптобиржами
Получение балансов и данных с Bybit, Gate.io, MEXC
"""
import ccxt
from datetime import datetime


def get_exchange_instance(exchange_name: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Создает экземпляр биржи с авторизацией
    """
    config = {
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,
    }
    
    if exchange_name == 'bybit':
        config['options'] = {
            'recvWindow': 120000,  # Увеличиваем окно приема до 120 секунд
            'adjustForTimeDifference': True,  # Автоматическая синхронизация времени
            'defaultType': 'spot',  # Указываем тип рынка
        }
        exchange = ccxt.bybit(config)
        # Принудительная загрузка рынков и синхронизация времени
        try:
            exchange.load_markets()
        except:
            pass
        return exchange
    elif exchange_name == 'gateio':
        return ccxt.gateio(config)
    elif exchange_name == 'mexc':
        return ccxt.mexc(config)
    else:
        raise ValueError(f"Неизвестная биржа: {exchange_name}")


def test_exchange_connection(exchange_name: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Проверяет подключение к бирже
    Возвращает (success: bool, message: str)
    """
    try:
        exchange = get_exchange_instance(exchange_name, api_key, secret_key, passphrase)
        balance = exchange.fetch_balance()
        return True, "Подключение успешно"
    except ccxt.AuthenticationError:
        return False, "Ошибка авторизации - проверьте ключи"
    except ccxt.NetworkError:
        return False, "Ошибка сети - проверьте интернет"
    except Exception as e:
        return False, f"Ошибка: {str(e)[:100]}"


def fetch_balance_for_exchange(exchange_name: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Получает баланс с одной биржи
    Возвращает словарь с активами
    """
    try:
        exchange = get_exchange_instance(exchange_name, api_key, secret_key, passphrase)
        balance = exchange.fetch_balance()
        
        # Фильтруем ненулевые балансы
        assets = {}
        for currency, data in balance.items():
            if isinstance(data, dict) and data.get('total', 0) > 0:
                assets[currency] = {
                    'free': float(data.get('free', 0) or 0),
                    'used': float(data.get('used', 0) or 0),
                    'total': float(data.get('total', 0) or 0),
                }
        
        return {
            'status': 'success',
            'assets': assets,
            'error': None,
            'timestamp': datetime.now(),
        }
        
    except ccxt.AuthenticationError:
        return {
            'status': 'error',
            'assets': {},
            'error': 'Ошибка авторизации',
            'timestamp': datetime.now(),
        }
    except Exception as e:
        return {
            'status': 'error',
            'assets': {},
            'error': str(e)[:100],
            'timestamp': datetime.now(),
        }


def get_asset_price_usd(currency: str, exchange=None):
    """
    Получает цену актива в USD
    """
    if currency in ['USDT', 'USDC', 'USD', 'BUSD', 'DAI']:
        return 1.0
    
    try:
        if exchange is None:
            exchange = ccxt.bybit({
                'enableRateLimit': True,
                'options': {
                    'recvWindow': 120000,
                    'adjustForTimeDifference': True,
                    'defaultType': 'spot',
                }
            })
            try:
                exchange.load_markets()
            except:
                pass
        
        # Пробуем разные пары
        for quote in ['USDT', 'USDC', 'USD']:
            try:
                ticker = exchange.fetch_ticker(f"{currency}/{quote}")
                return ticker['last']
            except:
                continue
        return 0.0
    except:
        return 0.0


def calculate_portfolio_value(assets: dict, exchange=None):
    """
    Рассчитывает общую стоимость портфеля в USD
    """
    if exchange is None:
        exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {
                'recvWindow': 120000,
                'adjustForTimeDifference': True,
                'defaultType': 'spot',
            }
        })
        try:
            exchange.load_markets()
        except:
            pass
    
    total_usd = 0.0
    asset_details = []
    
    for currency, data in assets.items():
        if currency in ['info', 'timestamp', 'datetime', 'free', 'used', 'total']:
            continue
        
        amount = data['total']
        if amount <= 0:
            continue
        
        price = get_asset_price_usd(currency, exchange)
        usd_value = amount * price
        
        if usd_value >= 0.01:  # Игнорируем пыль
            asset_details.append({
                'currency': currency,
                'amount': amount,
                'free': data['free'],
                'used': data['used'],
                'price_usd': price,
                'value_usd': usd_value,
            })
            total_usd += usd_value
    
    return {
        'total_usd': total_usd,
        'assets': sorted(asset_details, key=lambda x: x['value_usd'], reverse=True),
    }


def fetch_user_portfolio(user_exchange_keys: list):
    """
    Получает полный портфель пользователя со всех подключенных бирж
    
    user_exchange_keys: список объектов ExchangeAPIKey из БД
    """
    portfolio = {
        'total_usd': 0.0,
        'exchanges': {},
        'all_assets': [],
        'timestamp': datetime.now(),
    }
    
    price_exchange = ccxt.bybit({
        'enableRateLimit': True,
        'options': {
            'recvWindow': 120000,
            'adjustForTimeDifference': True,
            'defaultType': 'spot',
        }
    })
    try:
        price_exchange.load_markets()
    except:
        pass
    
    for key in user_exchange_keys:
        if not key.is_active:
            continue
        
        exchange_name = key.exchange_name
        
        # Получаем баланс
        balance_data = fetch_balance_for_exchange(
            exchange_name,
            key.api_key,
            key.secret_key,
            key.passphrase
        )
        
        if balance_data['status'] == 'success':
            # Рассчитываем стоимость
            calc = calculate_portfolio_value(balance_data['assets'], price_exchange)
            
            portfolio['exchanges'][exchange_name] = {
                'status': 'success',
                'total_usd': calc['total_usd'],
                'assets': calc['assets'],
                'asset_count': len(calc['assets']),
            }
            
            portfolio['total_usd'] += calc['total_usd']
            
            # Добавляем в общий список с указанием биржи
            for asset in calc['assets']:
                asset['exchange'] = exchange_name
                portfolio['all_assets'].append(asset)
        else:
            portfolio['exchanges'][exchange_name] = {
                'status': 'error',
                'error': balance_data['error'],
                'total_usd': 0,
                'assets': [],
                'asset_count': 0,
            }
    
    # Сортируем общий список по стоимости
    portfolio['all_assets'] = sorted(portfolio['all_assets'], key=lambda x: x['value_usd'], reverse=True)
    
    return portfolio


def fetch_coin_prices(coin_name: str):
    """
    Получает цены монеты на всех биржах
    """
    bybit_exchange = ccxt.bybit({
        'enableRateLimit': True,
        'options': {
            'recvWindow': 120000,
            'adjustForTimeDifference': True,
            'defaultType': 'spot',
        }
    })
    try:
        bybit_exchange.load_markets()
    except:
        pass
    
    exchanges = {
        'bybit': bybit_exchange,
        'gateio': ccxt.gateio(),
        'mexc': ccxt.mexc(),
    }
    
    prices = {}
    symbol = f"{coin_name.upper()}/USDT"
    
    for name, exchange in exchanges.items():
        try:
            ticker = exchange.fetch_ticker(symbol)
            prices[name] = {
                'price': ticker['last'],
                'change_24h': ticker.get('percentage', 0),
                'high_24h': ticker.get('high', 0),
                'low_24h': ticker.get('low', 0),
                'volume_24h': ticker.get('quoteVolume', 0),
            }
        except:
            prices[name] = None
    
    return prices


def get_available_trading_pairs(exchange_name: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Получает список доступных торговых пар на бирже
    Возвращает отсортированный список пар /USDT
    """
    try:
        exchange = get_exchange_instance(exchange_name, api_key, secret_key, passphrase)
        exchange.load_markets()
        
        # Фильтруем только пары USDT и сортируем по алфавиту
        usdt_pairs = []
        for symbol in exchange.symbols:
            if symbol.endswith('USDT'):
                # Проверяем что пара активна для торговли
                market = exchange.markets.get(symbol, {})
                if market.get('active', True):
                    usdt_pairs.append(symbol)
        
        # Сортируем по алфавиту и возвращаем до 100 пар
        return True, sorted(usdt_pairs)[:100]
    except Exception as e:
        return False, f"Ошибка получения пар: {str(e)[:100]}"


def get_current_price(exchange_name: str, symbol: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Получает текущую цену для символа
    """
    try:
        exchange = get_exchange_instance(exchange_name, api_key, secret_key, passphrase)
        ticker = exchange.fetch_ticker(symbol)
        return True, {
            'last': ticker.get('last', 0),
            'bid': ticker.get('bid', 0),
            'ask': ticker.get('ask', 0),
            'high': ticker.get('high', 0),
            'low': ticker.get('low', 0),
        }
    except Exception as e:
        return False, f"Ошибка получения цены: {str(e)[:100]}"


def create_order(exchange_name: str, symbol: str, side: str, order_type: str, amount: float, 
                price: float = None, api_key: str = "", secret_key: str = "", passphrase: str = None):
    """
    Создает ордер на бирже
    side: 'buy' или 'sell'
    order_type: 'market' или 'limit'
    
    Возвращает (success: bool, result: dict или сообщение об ошибке)
    """
    try:
        # Валидация параметров
        if not symbol or '/' not in symbol:
            return False, f"Неверный формат символа: {symbol}. Используйте формат: BTC/USDT"
        
        if side not in ['buy', 'sell']:
            return False, f"Неверная сторона ордера: {side}"
        
        if amount <= 0:
            return False, f"Количество должно быть > 0, получено: {amount}"
        
        if order_type == 'limit':
            if not price or price <= 0:
                return False, f"Для лимитного ордера требуется цена > 0, получено: {price}"
        
        exchange = get_exchange_instance(exchange_name, api_key, secret_key, passphrase)
        
        # Загружаем рынки и проверяем доступность символа
        try:
            exchange.load_markets()
            if symbol not in exchange.symbols:
                return False, f"Символ {symbol} не доступен на бирже {exchange_name}. Используйте доступные пары."
        except Exception as e:
            return False, f"Ошибка загрузки рынков: {str(e)[:100]}"
        
        if order_type == 'market':
            # Для некоторых бирж (Gate.io, MEXC) при market-buy требуется
            # передать цену или стоимость, чтобы корректно рассчитать сумму.
            # Если price не задан, попытаемся получить текущую цену через API.
            if side == 'buy' and exchange_name in ('gateio', 'mexc'):
                # если цена не передана, попробуем определить её
                if not price or price <= 0:
                    succ, res = get_current_price(exchange_name, symbol, api_key, secret_key, passphrase)
                    if not succ:
                        return False, f"Невозможно получить текущую цену для {exchange_name}: {res}"
                    price = float(res.get('last', 0) or 0)
                    if price <= 0:
                        return False, f"Некорректная текущая цена: {price}"

                if exchange_name == 'gateio':
                    # Gate.io использует параметр cost (общая стоимость в квоте)
                    params = {'cost': amount * price}
                    order = exchange.create_order(symbol, 'market', side, amount, price, params)
                else:  # mexc
                    # MEXC требует quoteOrderQty (стоимость в USDT) для рыночных покупок
                    params = {'quoteOrderQty': amount * price}
                    order = exchange.create_order(symbol, 'market', side, amount, None, params)
            else:
                # для прочих бирж используем стандартный market вызов
                order = exchange.create_market_order(symbol, side, amount)
        else:
            order = exchange.create_limit_order(symbol, side, amount, price)
        
        return True, {
            'order_id': order.get('id', ''),
            'symbol': order.get('symbol', symbol),
            'side': side,
            'amount': amount,
            'price': price,
            'timestamp': datetime.now().isoformat(),
            'status': order.get('status', 'pending'),
        }
    except (ccxt.InsufficientFunds, ccxt.InvalidOrder, ccxt.AuthenticationError, ccxt.NetworkError) as e:
        error_type = type(e).__name__
        error_msg = str(e)
        
        if 'Insufficient' in error_type or 'Balance' in error_msg:
            return False, "Недостаточно средств на счете"
        elif 'symbol not support' in error_msg.lower():
            return False, f"Символ {symbol} не поддерживается на {exchange_name}. Проверьте доступные торговые пары."
        elif 'Invalid' in error_type:
            return False, f"Неверные параметры: {error_msg[:100]}"
        elif 'Authentication' in error_type:
            return False, "Ошибка аутентификации на бирже"
        elif 'Network' in error_type:
            return False, "Ошибка соединения с биржей"
        else:
            return False, f"Ошибка биржи: {error_msg[:100]}"
    except Exception as e:
        error_msg = str(e)
        return False, f"Ошибка создания ордера: {error_msg[:150]}"
