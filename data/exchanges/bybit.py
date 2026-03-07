"""BYBIT Exchange API"""
import ccxt
from config import QUOTE_CURRENCY


class BybitExchange:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange_name = 'bybit'
        self.ccxt_exchange = None
        self.is_connected = False
    
    def connect(self):
        """Подключение к Bybit"""
        try:
            self.ccxt_exchange = ccxt.bybit({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
            })
            self.ccxt_exchange.fetch_balance()
            self.is_connected = True
            print("✓ BYBIT подключена")
            return True
        except Exception as e:
            self.is_connected = False
            print(f"✗ BYBIT ошибка: {e}")
            return False
    
    def get_all_symbols(self):
        """Получить все доступные USDT символы"""
        try:
            self.ccxt_exchange.load_markets()
            # BYBIT использует формат BTC/USDT:USDT, конвертируем в BTC/USDT
            symbols = set()
            for symbol in self.ccxt_exchange.markets.keys():
                # Удаляем :USDT если есть (BYBIT специфичное)
                normalized_symbol = symbol.replace(':USDT', '').replace(':BUSD', '')
                if QUOTE_CURRENCY in normalized_symbol:
                    symbols.add(normalized_symbol)
            return symbols
        except Exception as e:
            print(f"  ✗ Ошибка получения символов: {e}")
            return set()
    
    def get_order_book_data(self, symbol):
        """Получить первые 5 уровней стакана для символа."""
        try:
            orderbook = self.ccxt_exchange.fetch_order_book(symbol, limit=5)
            asks = orderbook.get('asks') or []
            bids = orderbook.get('bids') or []
            return {
                'ask_price': [level[0] for level in asks[:5]],
                'ask_volume': [level[1] for level in asks[:5]],
                'bid_price': [level[0] for level in bids[:5]],
                'bid_volume': [level[1] for level in bids[:5]],
            }
        except Exception:
            pass
        return {
            'ask_price': [],
            'ask_volume': [],
            'bid_price': [],
            'bid_volume': [],
        }
    
    def get_quotes_1h(self, symbol):
        """Получить котировки за последний час (12 свечей по 5 минут)"""
        try:
            if '5m' in self.ccxt_exchange.timeframes:
                ohlcv = self.ccxt_exchange.fetch_ohlcv(symbol, '5m', limit=12)
                quotes = [candle[4] for candle in ohlcv]  # Берём close price
                return str(quotes)
        except Exception:
            pass
        return '[]'
    
    def get_usdt_pairs(self, symbols=None):
        """Получить все данные по USDT парам (опционально только для указанных символов)"""
        pairs_data = {}
        
        try:
            print("  📥 Загружаю markets...")
            self.ccxt_exchange.load_markets()
            print("  ✓ Markets загружены")
            
            print("  📥 Получаю все tickers...")
            tickers = self.ccxt_exchange.fetch_tickers()
            print(f"  ✓ Получено {len(tickers)} тикеров")
            
            if symbols is None:
                usdt_symbols = [s for s in tickers.keys() if QUOTE_CURRENCY in s]
            else:
                # BYBIT использует формат BTC/USDT:USDT, нормализуем запрошенные символы
                usdt_symbols = []
                not_found = []
                for symbol in symbols:
                    # Пробуем нормализованный символ (BTC/USDT)
                    if symbol in tickers:
                        usdt_symbols.append(symbol)
                    else:
                        # Пробуем с :USDT (BTC/USDT:USDT)
                        bybit_symbol = symbol.replace('/USDT', '/USDT:USDT')
                        if bybit_symbol in tickers:
                            usdt_symbols.append(bybit_symbol)
                        else:
                            not_found.append(symbol)
                
                if not_found:
                    print(f"  ⚠️  Не найдены на BYBIT: {', '.join(not_found)}")
            
            print(f"  📊 Обрабатываю {len(usdt_symbols)} пар")
            
            for idx, symbol in enumerate(usdt_symbols, 1):
                try:
                    ticker = tickers[symbol]
                    current_price = ticker.get('last')
                    if not current_price or current_price == 0:
                        continue
                    
                    market = self.ccxt_exchange.markets.get(symbol)
                    if not market:
                        continue
                    
                    print(f"    [{idx}/{len(usdt_symbols)}] {symbol} - получаю стакан и котировки...", end=' ')
                    
                    # Получаем данные из стакана и котировки
                    orderbook_data = self.get_order_book_data(symbol)
                    quotes = self.get_quotes_1h(symbol)
                    
                    # Нормализуем имя символа для хранения в БД
                    normalized_symbol = symbol.replace(':USDT', '').replace(':BUSD', '')
                    
                    pairs_data[normalized_symbol] = {
                        'current_price': current_price,
                        'change_24h_percent': ticker.get('percentage', 0),
                        'change_24h_absolute': ticker.get('change', 0),
                        'high_24h': ticker.get('high', 0),
                        'low_24h': ticker.get('low', 0),
                        'volume_24h': ticker.get('quoteVolume', 0),
                        'maker_fee': market.get('maker', 0),
                        'taker_fee': market.get('taker', 0),
                        'min_order_amount': market.get('limits', {}).get('amount', {}).get('min', 0),
                        'lot_size': market.get('precision', {}).get('amount', 0),
                        'ask_price': orderbook_data['ask_price'],
                        'ask_volume': orderbook_data['ask_volume'],
                        'bid_price': orderbook_data['bid_price'],
                        'bid_volume': orderbook_data['bid_volume'],
                        'quotes_1h': quotes,
                    }
                    print("✓")
                except Exception as e:
                    print(f"✗ {e}")
                    continue
            
            print(f"✓ BYBIT: получены данные по {len(pairs_data)} парам")
            return pairs_data
            
        except Exception as e:
            print(f"✗ BYBIT ошибка получения данных: {e}")
            return {}
    
    def get_balance(self):
        """Получить баланс"""
        try:
            print("  💰 Получаю баланс...")
            balance = self.ccxt_exchange.fetch_balance()
            balance_data = {}
            
            for asset, info in balance.items():
                if asset not in ['free', 'used', 'total', 'free_funding', 'used_funding']:
                    try:
                        total = info.get('total', 0) if isinstance(info, dict) else 0
                        if total and total > 0:
                            balance_data[asset] = {
                                'free': info.get('free', 0),
                                'locked': info.get('used', 0),
                                'total': total,
                            }
                    except Exception:
                        continue
            
            print(f"  ✓ Получен баланс {len(balance_data)} активов")
            return balance_data
        except Exception as e:
            print(f"  ✗ Ошибка баланса: {e}")
            return {}
