"""
Независимый скрипт для сбора спотовых котировок с бирж
Получает данные с Bybit, Gate.io, MEXC используя API ключи из базы данных
и записывает в JSON файл

Использование:
    python exchange_price_fetcher.py

Зависимости:
    pip install ccxt sqlalchemy
"""
import ccxt
import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Подключаемся к БД
engine = create_engine('sqlite:///database.db', connect_args={'check_same_thread': False})
Session = sessionmaker(bind=engine)
session = Session()

# Импортируем модель после создания движка
from backend.models import ExchangeAPIKey


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
            'recvWindow': 120000,
            'adjustForTimeDifference': True,
            'defaultType': 'spot',
        }
        exchange = ccxt.bybit(config)
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


def fetch_all_exchange_prices():
    """
    Получает котировки со всех бирж используя API ключи из БД
    и записывает в JSON файл
    """
    
    print("[INFO] Получаем API ключи из базы данных...\n")
    
    # Получаем все активные API ключи
    exchange_keys = session.query(ExchangeAPIKey).filter_by(is_active=True).all()
    
    if not exchange_keys:
        print("[ERROR] В базе данных не найдено активных API ключей!")
        return
    
    print(f"[INFO] Найдено активных ключей: {len(exchange_keys)}\n")
    
    # Результаты
    all_data = {
        'timestamp': datetime.now().isoformat(),
        'exchanges': {}
    }
    
    # Группируем ключи по биржам
    exchanges_by_name = {}
    for key in exchange_keys:
        if key.exchange_name not in exchanges_by_name:
            exchanges_by_name[key.exchange_name] = []
        exchanges_by_name[key.exchange_name].append(key)
    
    print(f"[INFO] Начинаем сбор котировок...\n")
    
    for exchange_name, keys in exchanges_by_name.items():
        print(f"[{exchange_name.upper()}] Найдено ключей: {len(keys)}")
        
        # Используем первый ключ для подключения
        key = keys[0]
        
        try:
            print(f"[{exchange_name.upper()}] Подключаемся с использованием API ключа...")
            exchange = get_exchange_instance(exchange_name, key.api_key, key.secret_key, key.passphrase)
            
            # Загружаем список доступных пар
            exchange.load_markets()
            
            # Фильтруем только пары с USDT и берем первые 10
            usdt_pairs = [symbol for symbol in exchange.symbols if symbol.endswith('USDT')][:10]
            
            print(f"[{exchange_name.upper()}] Выбрано пар USDT: {len(usdt_pairs)} из доступных")
            print(f"[{exchange_name.upper()}] Получаем котировки... (это может занять время)")
            
            exchange_data = {
                'status': 'success',
                'total_pairs': len(usdt_pairs),
                'tickers': {}
            }
            
            # Получаем котировки для каждой пары
            for i, symbol in enumerate(usdt_pairs):
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    # Сохраняем данные в точно том виде, как они пришли из API
                    exchange_data['tickers'][symbol] = ticker
                    
                    if (i + 1) % 5 == 0:
                        print(f"[{exchange_name.upper()}] Обработано {i + 1}/{len(usdt_pairs)} пар...")
                
                except Exception as e:
                    # Если ошибка для одной пары, продолжаем
                    print(f"[{exchange_name.upper()}] Ошибка для {symbol}: {str(e)[:50]}")
                    exchange_data['tickers'][symbol] = {
                        'error': str(e)[:100]
                    }
            
            print(f"[{exchange_name.upper()}] ✓ Завершено. Получено {len(exchange_data['tickers'])} котировок\n")
            all_data['exchanges'][exchange_name] = exchange_data
            
        except Exception as e:
            print(f"[{exchange_name.upper()}] ✗ Ошибка подключения: {str(e)[:100]}\n")
            all_data['exchanges'][exchange_name] = {
                'status': 'error',
                'error': str(e)[:100]
            }
    
    # Записываем в JSON файл
    json_filename = f"exchange_prices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    print(f"[INFO] Записываем JSON-данные: {json_filename}")
    
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"[INFO] ✓ JSON файл успешно создан: {json_filename}")
    print(f"\n[ЗАВЕРШЕНО] Сбор данных окончен!")
    
    # Закрываем сессию БД
    session.close()


if __name__ == '__main__':
    try:
        fetch_all_exchange_prices()
    except KeyboardInterrupt:
        print("\n[INFO] Сбор прерван пользователем")
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {str(e)}")

