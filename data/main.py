"""Главный скрипт для сбора данных с бирж"""
from config import EXCHANGES
from database import DatabaseManager
from exchanges.mexc import MEXCExchange
from exchanges.bybit import BybitExchange
from exchanges.gateio import GateiоExchange


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
    print("\n" + "="*60)
    print("🚀 ЗАПУСК СБОРА ДАННЫХ ПО КРИПТОВАЛЮТАМ")
    print("="*60 + "\n")
    
    # Инициализация БД
    print("🗄️  ПОДКЛЮЧЕНИЕ К БД")
    db = DatabaseManager()
    if not db.connect():
        return
    
    db.create_tables()
    
    # Инициализация бирж
    print("\n🔗 ПОДКЛЮЧЕНИЕ К БИРЖАМ")
    mexc = MEXCExchange(EXCHANGES['mexc']['api_key'], EXCHANGES['mexc']['api_secret'])
    bybit = BybitExchange(EXCHANGES['bybit']['api_key'], EXCHANGES['bybit']['api_secret'])
    gateio = GateiоExchange(EXCHANGES['gateio']['api_key'], EXCHANGES['gateio']['api_secret'])
    
    if not mexc.connect() or not bybit.connect() or not gateio.connect():
        return
    
    # Получаем топ 20 общих пар
    top_20_symbols = get_top_20_common_symbols(mexc, bybit, gateio)
    
    # MEXC
    print("\n" + "="*60)
    print("📊 MEXC")
    print("="*60)
    pairs = mexc.get_usdt_pairs(symbols=top_20_symbols)
    if pairs:
        db.save_pairs('mexc', pairs)
    balance = mexc.get_balance()
    if balance:
        db.save_balance('mexc', balance)
    
    # BYBIT
    print("\n" + "="*60)
    print("📊 BYBIT")
    print("="*60)
    pairs = bybit.get_usdt_pairs(symbols=top_20_symbols)
    if pairs:
        db.save_pairs('bybit', pairs)
    balance = bybit.get_balance()
    if balance:
        db.save_balance('bybit', balance)
    
    # GATEIO
    print("\n" + "="*60)
    print("📊 GATEIO")
    print("="*60)
    pairs = gateio.get_usdt_pairs(symbols=top_20_symbols)
    if pairs:
        db.save_pairs('gateio', pairs)
    balance = gateio.get_balance()
    if balance:
        db.save_balance('gateio', balance)
    
    db.close()
    print("\n" + "="*60)
    print("✅ ГОТОВО")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
