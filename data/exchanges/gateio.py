"""GATEIO Exchange API"""
import ccxt

try:
    from data.config import QUOTE_CURRENCY
except ImportError:
    from config import QUOTE_CURRENCY


class GateiоExchange:
    def __init__(self, api_key, api_secret, uid=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.uid = uid
        self.exchange_name = 'gateio'
        self.ccxt_exchange = None
        self.is_connected = False
    
    def connect(self):
        """Подключение к Gate.io"""
        try:
            config = {
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
            }
            if self.uid:
                config['uid'] = self.uid
            
            self.ccxt_exchange = ccxt.gateio(config)
            self.ccxt_exchange.fetch_balance()
            self.is_connected = True
            print("✓ GATEIO подключена")
            return True
        except Exception as e:
            self.is_connected = False
            print(f"✗ GATEIO ошибка: {e}")
            return False
    
    def get_all_symbols(self):
        """Получить все доступные USDT символы"""
        try:
            self.ccxt_exchange.load_markets()
            symbols = [s for s in self.ccxt_exchange.markets.keys() if QUOTE_CURRENCY in s]
            return set(symbols)
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
                usdt_symbols = [s for s in symbols if s in tickers]
            
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
                    
                    pairs_data[symbol] = {
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
            
            print(f"✓ GATEIO: получены данные по {len(pairs_data)} парам")
            return pairs_data
            
        except Exception as e:
            print(f"✗ GATEIO ошибка получения данных: {e}")
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
