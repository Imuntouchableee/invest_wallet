"""
API модуль для работы с криптобиржами
Получение балансов и данных с Bybit, Gate.io, MEXC
"""
import ccxt
from datetime import datetime

from backend.models import ExchangeAPIKey, session
from data.database import DatabaseManager


BYBIT_RECV_WINDOW = 5000
STABLE_CURRENCIES = {'USDT', 'USDC', 'USD', 'BUSD', 'DAI'}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _get_db():
    db = DatabaseManager()
    if not db.connect():
        return None
    return db


def _get_asset_price_from_db(db: DatabaseManager, currency: str, preferred_exchange: str = None):
    if currency in STABLE_CURRENCIES:
        return 1.0

    symbol = f"{currency}/USDT"
    exchanges = []
    if preferred_exchange:
        exchanges.append(preferred_exchange)
    exchanges.extend(exchange for exchange in ('bybit', 'gateio', 'mexc') if exchange != preferred_exchange)

    for exchange in exchanges:
        pair_info = db.get_pair_info(exchange, symbol)
        if pair_info and pair_info.get('current_price') is not None:
            return _safe_float(pair_info.get('current_price'))
    return 0.0


def _calculate_portfolio_value_from_db(db: DatabaseManager, exchange_name: str, assets: dict):
    total_usd = 0.0
    asset_details = []

    for currency, data in assets.items():
        amount = _safe_float(data.get('total'))
        if amount <= 0:
            continue

        price = _get_asset_price_from_db(db, currency, preferred_exchange=exchange_name)
        usd_value = amount * price
        if usd_value < 0.01:
            continue

        asset_details.append({
            'currency': currency,
            'amount': amount,
            'free': _safe_float(data.get('free')),
            'used': _safe_float(data.get('locked')),
            'price_usd': price,
            'value_usd': usd_value,
        })
        total_usd += usd_value

    return {
        'total_usd': total_usd,
        'assets': sorted(asset_details, key=lambda item: item['value_usd'], reverse=True),
    }


def _normalize_order_values(exchange, symbol: str, amount: float, price: float = None):
    """Нормализует количество/цену под правила биржи и рынка."""
    market = exchange.market(symbol)

    normalized_amount = _safe_float(exchange.amount_to_precision(symbol, amount))
    normalized_price = None
    if price is not None:
        normalized_price = _safe_float(exchange.price_to_precision(symbol, price))

    amount_min = _safe_float((market.get('limits') or {}).get('amount', {}).get('min'))
    cost_min = _safe_float((market.get('limits') or {}).get('cost', {}).get('min'))

    if amount_min and normalized_amount < amount_min:
        return False, None, None, (
            f"Количество меньше минимального: {normalized_amount} < {amount_min}"
        )

    if normalized_price is not None and cost_min:
        order_cost = normalized_amount * normalized_price
        if order_cost < cost_min:
            return False, None, None, (
                f"Сумма ордера меньше минимальной: {order_cost:.8f} < {cost_min}"
            )

    return True, normalized_amount, normalized_price, None


def _persist_exchange_balance(exchange_name: str, assets: dict):
    """Синхронизирует live-баланс биржи с локальной БД."""
    db = DatabaseManager()
    if not db.connect():
        return

    try:
        balance_data = {
            asset_name: {
                'free': asset_info.get('free', 0),
                'locked': asset_info.get('used', 0),
                'total': asset_info.get('total', 0),
            }
            for asset_name, asset_info in assets.items()
            if isinstance(asset_info, dict)
        }
        db.save_balance(exchange_name, balance_data)
    except Exception:
        pass
    finally:
        db.close()


def _sync_exchange_clock(exchange):
    """Синхронизирует локальное время с сервером биржи для signed-запросов."""
    try:
        exchange.load_time_difference()
    except Exception:
        pass
    return exchange


def _create_bybit_exchange(api_key: str = None, secret_key: str = None):
    config = {
        'enableRateLimit': True,
        'options': {
            'recvWindow': BYBIT_RECV_WINDOW,
            'adjustForTimeDifference': True,
            'defaultType': 'spot',
        },
    }
    if api_key:
        config['apiKey'] = api_key
    if secret_key:
        config['secret'] = secret_key

    exchange = ccxt.bybit(config)
    return _sync_exchange_clock(exchange)


def get_exchange_instance(exchange_name: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Создает экземпляр биржи с авторизацией
    """
    config = {
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,
        'options': {
            'adjustForTimeDifference': True,
            'defaultType': 'spot',
        },
    }

    if exchange_name == 'bybit':
        exchange = _create_bybit_exchange(api_key, secret_key)
    elif exchange_name == 'gateio':
        exchange = ccxt.gateio(config)
    elif exchange_name == 'mexc':
        config['options']['recvWindow'] = 5000
        exchange = ccxt.mexc(config)
    else:
        raise ValueError(f"Неизвестная биржа: {exchange_name}")

    try:
        exchange.load_markets()
    except Exception:
        pass
    return exchange


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
    Получает баланс с одной биржи из локальной БД
    Возвращает словарь с активами
    """
    db = _get_db()
    if not db:
        return {
            'status': 'error',
            'assets': {},
            'error': 'Не удалось подключиться к базе данных',
            'timestamp': datetime.now(),
        }

    try:
        key = session.query(ExchangeAPIKey).filter_by(
            exchange_name=exchange_name,
            api_key=api_key,
            secret_key=secret_key,
            is_active=True,
        ).first()
        if not key:
            return {
                'status': 'error',
                'assets': {},
                'error': 'Для этих ключей нет сохраненного баланса в базе данных',
                'timestamp': datetime.now(),
            }

        assets = db.get_balances(exchange_name, user_id=key.user_id)
        if not assets:
            return {
                'status': 'error',
                'assets': {},
                'error': 'Баланс еще не синхронизирован в базу данных',
                'timestamp': datetime.now(),
            }

        return {
            'status': 'success',
            'assets': {
                currency: {
                    'free': data.get('free', 0),
                    'used': data.get('locked', 0),
                    'total': data.get('total', 0),
                }
                for currency, data in assets.items()
            },
            'error': None,
            'timestamp': datetime.now(),
        }
    except Exception as e:
        return {
            'status': 'error',
            'assets': {},
            'error': str(e)[:100],
            'timestamp': datetime.now(),
        }
    finally:
        db.close()


def get_asset_price_usd(currency: str, exchange=None):
    """
    Получает цену актива в USD
    """
    db = _get_db()
    if not db:
        return 0.0

    try:
        return _get_asset_price_from_db(db, currency)
    finally:
        db.close()


def calculate_portfolio_value(assets: dict, exchange=None):
    """
    Рассчитывает общую стоимость портфеля в USD
    """
    db = _get_db()
    if not db:
        return {'total_usd': 0.0, 'assets': []}

    try:
        return _calculate_portfolio_value_from_db(db, 'bybit', assets)
    finally:
        db.close()


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
    db = _get_db()
    if not db:
        for key in user_exchange_keys:
            if key.is_active:
                portfolio['exchanges'][key.exchange_name] = {
                    'status': 'error',
                    'error': 'Не удалось подключиться к базе данных',
                    'total_usd': 0,
                    'assets': [],
                    'asset_count': 0,
                }
        return portfolio
    
    try:
        for key in user_exchange_keys:
            if not key.is_active:
                continue

            exchange_name = key.exchange_name
            balances = db.get_balances(exchange_name, user_id=key.user_id)
            latest_pairs_update = db.get_latest_pairs_update(exchange_name)
            latest_balance_update = db.get_latest_balance_update(exchange_name, user_id=key.user_id)

            if not balances:
                portfolio['exchanges'][exchange_name] = {
                    'status': 'loading',
                    'error': 'Идет синхронизация данных из базы данных',
                    'total_usd': 0,
                    'assets': [],
                    'asset_count': 0,
                    'last_pairs_update': latest_pairs_update,
                    'last_balance_update': latest_balance_update,
                }
                continue

            calc = _calculate_portfolio_value_from_db(db, exchange_name, balances)
            portfolio['exchanges'][exchange_name] = {
                'status': 'success',
                'total_usd': calc['total_usd'],
                'assets': calc['assets'],
                'asset_count': len(calc['assets']),
                'last_pairs_update': latest_pairs_update,
                'last_balance_update': latest_balance_update,
            }

            portfolio['total_usd'] += calc['total_usd']

            for asset in calc['assets']:
                asset['exchange'] = exchange_name
                portfolio['all_assets'].append(asset)

        portfolio['all_assets'] = sorted(
            portfolio['all_assets'],
            key=lambda item: item['value_usd'],
            reverse=True,
        )
        return portfolio
    finally:
        db.close()


def fetch_coin_prices(coin_name: str):
    """
    Получает цены монеты на всех биржах
    """
    db = _get_db()
    if not db:
        return {'bybit': None, 'gateio': None, 'mexc': None}

    try:
        return db.get_coin_prices(coin_name)
    finally:
        db.close()


def get_available_trading_pairs(exchange_name: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Получает список доступных торговых пар на бирже
    Возвращает отсортированный список пар /USDT
    """
    db = _get_db()
    if not db:
        return False, 'Ошибка подключения к базе данных'

    try:
        pairs = db.get_pairs(exchange_name)
        return True, pairs[:100]
    except Exception as e:
        return False, f"Ошибка получения пар: {str(e)[:100]}"
    finally:
        db.close()


def get_current_price(exchange_name: str, symbol: str, api_key: str, secret_key: str, passphrase: str = None):
    """
    Получает текущую цену для символа
    """
    db = _get_db()
    if not db:
        return False, 'Ошибка подключения к базе данных'

    try:
        ticker = db.get_pair_info(exchange_name, symbol)
        if not ticker:
            return False, f"Цена для {symbol} еще не загружена в базу данных"
        return True, {
            'last': _safe_float(ticker.get('current_price')),
            'bid': _safe_float((ticker.get('bid_price') or [0])[0] if ticker.get('bid_price') else 0),
            'ask': _safe_float((ticker.get('ask_price') or [0])[0] if ticker.get('ask_price') else 0),
            'high': _safe_float(ticker.get('high_24h')),
            'low': _safe_float(ticker.get('low_24h')),
            'updated_at': ticker.get('updated_at'),
        }
    except Exception as e:
        return False, f"Ошибка получения цены: {str(e)[:100]}"
    finally:
        db.close()


def create_order(exchange_name: str, symbol: str, side: str, order_type: str, amount: float, 
                price: float = None, api_key: str = "", secret_key: str = "", passphrase: str = None):
    """
    Создает ордер на бирже
    side: 'buy' или 'sell'
    order_type: 'market', 'limit' или 'stop-limit'
    
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

        normalized_price = price
        if price is not None and price > 0:
            normalized_price = _safe_float(price)

        ok, normalized_amount, normalized_price, validation_error = _normalize_order_values(
            exchange,
            symbol,
            amount,
            normalized_price,
        )
        if not ok:
            return False, validation_error

        market_price = normalized_price
        if order_type in ('market', 'stop-limit') and (market_price is None or market_price <= 0):
            succ, res = get_current_price(
                exchange_name,
                symbol,
                api_key,
                secret_key,
                passphrase,
            )
            if succ:
                market_price = _safe_float(res.get('last'))

        if order_type == 'stop-limit':
            # unified stop-limit поддерживается не всеми биржами одинаково,
            # поэтому используем limit c параметром stopPrice где возможно.
            if not normalized_price or normalized_price <= 0:
                return False, "Для стоп-лимит ордера требуется цена"
            params = {'stopPrice': normalized_price}
            order = exchange.create_order(
                symbol,
                'limit',
                side,
                normalized_amount,
                normalized_price,
                params,
            )
        elif order_type == 'market':
            # Для некоторых бирж рыночная покупка требует стоимость в валюте котировки.
            if side == 'buy' and exchange_name in ('gateio', 'mexc'):
                if not market_price or market_price <= 0:
                    return False, f"Невозможно получить текущую цену для {exchange_name}"

                cost_value = normalized_amount * market_price
                if exchange_name == 'gateio':
                    cost_value = _safe_float(exchange.cost_to_precision(symbol, cost_value))
                    params = {'cost': cost_value}
                    order = exchange.create_order(
                        symbol,
                        'market',
                        side,
                        normalized_amount,
                        None,
                        params,
                    )
                else:  # mexc
                    cost_value = _safe_float(exchange.cost_to_precision(symbol, cost_value))
                    params = {'quoteOrderQty': cost_value}
                    order = exchange.create_order(
                        symbol,
                        'market',
                        side,
                        normalized_amount,
                        None,
                        params,
                    )
            else:
                order = exchange.create_market_order(symbol, side, normalized_amount)
        else:
            if not normalized_price or normalized_price <= 0:
                return False, "Для лимитного ордера требуется цена"
            order = exchange.create_limit_order(
                symbol,
                side,
                normalized_amount,
                normalized_price,
            )
        
        return True, {
            'order_id': order.get('id', ''),
            'symbol': order.get('symbol', symbol),
            'side': side,
            'amount': normalized_amount,
            'price': normalized_price,
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
