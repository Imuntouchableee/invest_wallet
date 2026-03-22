"""Главный скрипт для сбора данных с бирж."""
import logging
import time
from datetime import datetime

try:
    from data.config import EXCHANGES
    from data.database import DatabaseManager
    from data.exchanges.mexc import MEXCExchange
    from data.exchanges.bybit import BybitExchange
    from data.exchanges.gateio import GateiоExchange
except ImportError:
    from config import EXCHANGES
    from database import DatabaseManager
    from exchanges.mexc import MEXCExchange
    from exchanges.bybit import BybitExchange
    from exchanges.gateio import GateiоExchange

from backend.models import ExchangeAPIKey, SessionLocal


logger = logging.getLogger(__name__)
REFRESH_INTERVAL_SECONDS = 10
STABLE_CURRENCIES = {'USDT', 'USDC', 'USD', 'BUSD', 'DAI'}


def _create_exchange_client(exchange_name, api_key, api_secret):
    if exchange_name == 'mexc':
        return MEXCExchange(api_key, api_secret)
    if exchange_name == 'bybit':
        return BybitExchange(api_key, api_secret)
    if exchange_name == 'gateio':
        return GateiоExchange(api_key, api_secret)
    raise ValueError(f'Неизвестная биржа: {exchange_name}')


def _load_active_user_keys():
    db_session = SessionLocal()
    try:
        keys = db_session.query(ExchangeAPIKey).filter_by(is_active=True).all()
        return [
            {
                'id': key.id,
                'user_id': key.user_id,
                'exchange_name': key.exchange_name,
                'api_key': key.api_key,
                'secret_key': key.secret_key,
                'passphrase': key.passphrase,
            }
            for key in keys
        ]
    finally:
        db_session.close()


def _update_last_sync(key_id):
    db_session = SessionLocal()
    try:
        key = db_session.get(ExchangeAPIKey, key_id)
        if key:
            key.last_sync = datetime.now()
            db_session.commit()
    except Exception as e:
        logger.error(
            f"[DATA] Не удалось обновить last_sync "
            f"для ключа {key_id}: {e}"
        )
        db_session.rollback()
    finally:
        db_session.close()


def _sync_user_balances(db: DatabaseManager):
    tracked_symbols = set()
    active_keys = _load_active_user_keys()

    for key in active_keys:
        exchange_name = key['exchange_name']
        try:
            client = _create_exchange_client(
                exchange_name,
                key['api_key'],
                key['secret_key'],
            )
            if not client.connect():
                logger.warning(
                    f"[DATA] Не удалось подключиться к {exchange_name} "
                    f"для user_id={key['user_id']}"
                )
                continue

            balance = client.get_balance()
            if not balance:
                logger.warning(
                    f"[DATA] Пустой баланс {exchange_name} "
                    f"для user_id={key['user_id']}"
                )
                continue

            db.save_balance(exchange_name, balance, user_id=key['user_id'])
            _update_last_sync(key['id'])

            for asset in balance.keys():
                asset_name = str(asset).upper()
                if asset_name not in STABLE_CURRENCIES:
                    tracked_symbols.add(f"{asset_name}/USDT")
        except Exception as e:
            logger.error(
                f"[DATA] Ошибка синхронизации баланса {exchange_name} "
                f"для user_id={key['user_id']}: {e}"
            )

    return tracked_symbols


def _create_market_clients():
    return {
        'mexc': MEXCExchange(
            EXCHANGES['mexc']['api_key'],
            EXCHANGES['mexc']['api_secret'],
        ),
        'bybit': BybitExchange(
            EXCHANGES['bybit']['api_key'],
            EXCHANGES['bybit']['api_secret'],
        ),
        'gateio': GateiоExchange(
            EXCHANGES['gateio']['api_key'],
            EXCHANGES['gateio']['api_secret'],
        ),
    }


def _connect_market_clients(clients):
    for name, client in clients.items():
        if not client.connect():
            logger.error(f"[DATA] Не удалось подключить market-клиент {name}")
            return False
    return True


def _sync_pairs(db: DatabaseManager, tracked_symbols=None):
    clients = _create_market_clients()
    if not _connect_market_clients(clients):
        return False

    top_symbols = set(
        get_top_20_common_symbols(
            clients['mexc'],
            clients['bybit'],
            clients['gateio'],
        )
    )
    tracked_symbols = set(tracked_symbols or [])
    symbols_to_sync = sorted(top_symbols | tracked_symbols)

    if not symbols_to_sync:
        logger.warning('[DATA] Нет символов для синхронизации пар')
        return False

    logger.info(
        f"[DATA] Синхронизация {len(symbols_to_sync)} символов "
        f"по всем биржам"
    )

    for exchange_name, client in clients.items():
        try:
            pairs = client.get_usdt_pairs(symbols=symbols_to_sync)
            if pairs:
                db.save_pairs(exchange_name, pairs)
            else:
                logger.warning(f"[DATA] Биржа {exchange_name} не вернула пары")
        except Exception as e:
            logger.error(
                f"[DATA] Ошибка синхронизации пар для {exchange_name}: {e}"
            )
    return True


def get_top_20_common_symbols(mexc, bybit, gateio):
    """Получить топ 20 символов по объёму, которые есть на всех трёх биржах"""
    print("\n🔍 ПОИСК ОБЩИХ ПАР НА ВСЕХ БИРЖАХ")
    print("="*60)
    
    # Получаем символы с каждой биржи
    print("  📥 Получаю символы MEXC...", end=' ')
    mexc_symbols = mexc.get_all_symbols()
    print(f"✓ {len(mexc_symbols)}")
    
    print("  📥 Получаю символы BYBIT...", end=' ')
    bybit_symbols = bybit.get_all_symbols()
    print(f"✓ {len(bybit_symbols)}")
    
    print("  📥 Получаю символы GATEIO...", end=' ')
    gateio_symbols = gateio.get_all_symbols()
    print(f"✓ {len(gateio_symbols)}")
    
    # Находим пересечение
    common_symbols = mexc_symbols & bybit_symbols & gateio_symbols
    print(f"\n  🎯 Общих пар на всех трёх биржах: {len(common_symbols)}")
    
    # DEBUG: выводим первые 10 общих символов
    if common_symbols:
        common_list = sorted(list(common_symbols))[:10]
        print(f"     Примеры: {', '.join(common_list)}")
    
    # Получаем тикеры со всех бирж и проверяем реальную доступность
    print("  📊 Получаю объёмы торгов и проверяю доступность...", end=' ')
    try:
        mexc.ccxt_exchange.load_markets()
        mexc_tickers = mexc.ccxt_exchange.fetch_tickers()
        
        bybit.ccxt_exchange.load_markets()
        bybit_tickers = bybit.ccxt_exchange.fetch_tickers()
        # Нормализуем ключи BYBIT для поиска
        bybit_tickers_normalized = {k.replace(':USDT', '').replace(':BUSD', ''): v 
                                     for k, v in bybit_tickers.items()}
        
        gateio.ccxt_exchange.load_markets()
        gateio_tickers = gateio.ccxt_exchange.fetch_tickers()
        
        # Фильтруем общие символы по реальной доступности и собираем объемы
        volumes = {}
        for symbol in common_symbols:
            # Проверяем наличие на всех трех биржах
            in_mexc = symbol in mexc_tickers
            in_bybit = symbol in bybit_tickers_normalized
            in_gateio = symbol in gateio_tickers
            
            if in_mexc and in_bybit and in_gateio:
                # Берем объем из MEXC (как репрезентативный)
                volume = mexc_tickers[symbol].get('quoteVolume', 0)
                volumes[symbol] = volume
        
        print(f"✓ {len(volumes)} символов доступны на всех трях")
        
        # Сортируем по объёму и берём топ 20
        sorted_symbols = sorted(volumes.items(), key=lambda x: x[1], reverse=True)
        top_20 = [symbol for symbol, _ in sorted_symbols[:20]]
        
        print(f"  🏆 Топ 20 по объёму (доступны на всех трех биржах):")
        for i, (symbol, volume) in enumerate(sorted_symbols[:20], 1):
            print(f"    {i:2d}. {symbol:12s} - ${volume:,.0f}")
        
        return top_20
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        return list(common_symbols)[:20] if common_symbols else []


def main():
    logger.info('[DATA] Запуск фонового обновления данных')

    while True:
        db = DatabaseManager()
        if not db.connect():
            logger.error(
                '[DATA] Не удалось подключиться к БД, повтор через 10 секунд'
            )
            time.sleep(REFRESH_INTERVAL_SECONDS)
            continue

        try:
            db.create_tables()
            tracked_symbols = _sync_user_balances(db)
            _sync_pairs(db, tracked_symbols=tracked_symbols)
            logger.info('[DATA] Цикл синхронизации завершен')
        except Exception as e:
            logger.exception(f'[DATA] Ошибка цикла синхронизации: {e}')
        finally:
            db.close()

        time.sleep(REFRESH_INTERVAL_SECONDS)


if __name__ == '__main__':
    main()
