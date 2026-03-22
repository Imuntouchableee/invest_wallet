"""Работа с базой данных PostgreSQL"""
import psycopg2
from psycopg2.extras import Json, execute_values

from data.config import DATABASE


class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Подключение к БД"""
        try:
            self.conn = psycopg2.connect(
                host=DATABASE['host'],
                port=DATABASE['port'],
                database=DATABASE['database'],
                user=DATABASE['user'],
                password=DATABASE['password']
            )
            self.cursor = self.conn.cursor()
            print("DB connection successful")
            return True
        except Exception as e:
            print(f"DB connection error: {e}")
            return False
    
    def close(self):
        """Закрытие соединения"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def create_tables(self):
        """Создание таблиц для каждой биржи"""
        try:
            # Таблица для MEXC
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS mexc_pairs (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(100) UNIQUE,
                    current_price DECIMAL(20, 8),
                    change_24h_percent DECIMAL(10, 4),
                    change_24h_absolute DECIMAL(20, 8),
                    high_24h DECIMAL(20, 8),
                    low_24h DECIMAL(20, 8),
                    volume_24h DECIMAL(20, 2),
                    maker_fee DECIMAL(10, 6),
                    taker_fee DECIMAL(10, 6),
                    min_order_amount DECIMAL(20, 8),
                    lot_size DECIMAL(20, 8),
                    ask_price JSONB,
                    ask_volume JSONB,
                    bid_price JSONB,
                    bid_volume JSONB,
                    quotes_1h TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для BYBIT
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS bybit_pairs (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(100) UNIQUE,
                    current_price DECIMAL(20, 8),
                    change_24h_percent DECIMAL(10, 4),
                    change_24h_absolute DECIMAL(20, 8),
                    high_24h DECIMAL(20, 8),
                    low_24h DECIMAL(20, 8),
                    volume_24h DECIMAL(20, 2),
                    maker_fee DECIMAL(10, 6),
                    taker_fee DECIMAL(10, 6),
                    min_order_amount DECIMAL(20, 8),
                    lot_size DECIMAL(20, 8),
                    ask_price JSONB,
                    ask_volume JSONB,
                    bid_price JSONB,
                    bid_volume JSONB,
                    quotes_1h TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для GATEIO
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS gateio_pairs (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(100) UNIQUE,
                    current_price DECIMAL(20, 8),
                    change_24h_percent DECIMAL(10, 4),
                    change_24h_absolute DECIMAL(20, 8),
                    high_24h DECIMAL(20, 8),
                    low_24h DECIMAL(20, 8),
                    volume_24h DECIMAL(20, 2),
                    maker_fee DECIMAL(10, 6),
                    ask_price JSONB,
                    ask_volume JSONB,
                    bid_price JSONB,
                    bid_volume JSONB,
                    quotes_1h TEXT,
                    taker_fee DECIMAL(10, 6),
                    min_order_amount DECIMAL(20, 8),
                    lot_size DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self._ensure_pairs_schema('mexc_pairs')
            self._ensure_pairs_schema('bybit_pairs')
            self._ensure_pairs_schema('gateio_pairs')
            
            # Таблица для баланса MEXC
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS mexc_balance (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    asset VARCHAR(50),
                    free DECIMAL(20, 8),
                    locked DECIMAL(20, 8),
                    total DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для баланса BYBIT
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS bybit_balance (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    asset VARCHAR(50),
                    free DECIMAL(20, 8),
                    locked DECIMAL(20, 8),
                    total DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для баланса GATEIO
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS gateio_balance (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    asset VARCHAR(50),
                    free DECIMAL(20, 8),
                    locked DECIMAL(20, 8),
                    total DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self._ensure_balance_schema('mexc_balance')
            self._ensure_balance_schema('bybit_balance')
            self._ensure_balance_schema('gateio_balance')

            self.conn.commit()
            print("Tables created/checked")
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"Table creation error: {e}")
            return False

    def _ensure_pairs_schema(self, table_name):
        """Приводит схему таблиц пар к актуальному виду."""
        jsonb_columns = ('ask_price', 'ask_volume', 'bid_price', 'bid_volume')

        for column_name in jsonb_columns:
            self.cursor.execute(
                f"ALTER TABLE {table_name} "
                f"ADD COLUMN IF NOT EXISTS {column_name} JSONB"
            )

        for column_name in ('ask_price', 'ask_volume'):
            self.cursor.execute(
                f"ALTER TABLE {table_name} "
                f"ALTER COLUMN {column_name} TYPE JSONB "
                f"USING CASE "
                f"WHEN {column_name} IS NULL THEN '[]'::jsonb "
                f"WHEN jsonb_typeof(to_jsonb({column_name})) = 'number' "
                f"THEN jsonb_build_array({column_name}) "
                f"ELSE to_jsonb({column_name}) END"
            )

        for column_name in ('bid_price', 'bid_volume'):
            self.cursor.execute(
                f"UPDATE {table_name} "
                f"SET {column_name} = '[]'::jsonb "
                f"WHERE {column_name} IS NULL"
            )

    def _ensure_balance_schema(self, table_name):
        """Приводит схему таблиц баланса к актуальному виду."""
        self.cursor.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN IF NOT EXISTS user_id INTEGER"
        )
        self.cursor.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )
        self.cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user_asset "
            f"ON {table_name} (user_id, asset)"
        )
    
    def save_pairs(self, exchange, pairs_data):
        """Сохранение данных по парам в БД"""
        try:
            table_name = f'{exchange}_pairs'
            print("  Saving pairs to DB...", end=' ')
            
            values = []
            for symbol, data in pairs_data.items():
                values.append((
                    symbol,
                    data.get('current_price'),
                    data.get('change_24h_percent'),
                    data.get('change_24h_absolute'),
                    data.get('high_24h'),
                    data.get('low_24h'),
                    data.get('volume_24h'),
                    data.get('maker_fee'),
                    data.get('taker_fee'),
                    data.get('min_order_amount'),
                    data.get('lot_size'),
                    Json(data.get('ask_price') or []),
                    Json(data.get('ask_volume') or []),
                    Json(data.get('bid_price') or []),
                    Json(data.get('bid_volume') or []),
                    data.get('quotes_1h'),
                ))
            
            if values:
                execute_values(
                    self.cursor,
                    f"""
                    INSERT INTO {table_name} 
                    (symbol, current_price, change_24h_percent, change_24h_absolute,
                     high_24h, low_24h, volume_24h, maker_fee, taker_fee, 
                     min_order_amount, lot_size, ask_price, ask_volume,
                     bid_price, bid_volume, quotes_1h)
                    VALUES %s
                    ON CONFLICT (symbol) DO UPDATE SET
                        current_price = EXCLUDED.current_price,
                        change_24h_percent = EXCLUDED.change_24h_percent,
                        change_24h_absolute = EXCLUDED.change_24h_absolute,
                        high_24h = EXCLUDED.high_24h,
                        low_24h = EXCLUDED.low_24h,
                        volume_24h = EXCLUDED.volume_24h,
                        maker_fee = EXCLUDED.maker_fee,
                        taker_fee = EXCLUDED.taker_fee,
                        min_order_amount = EXCLUDED.min_order_amount,
                        lot_size = EXCLUDED.lot_size,
                        ask_price = EXCLUDED.ask_price,
                        ask_volume = EXCLUDED.ask_volume,
                        bid_price = EXCLUDED.bid_price,
                        bid_volume = EXCLUDED.bid_volume,
                        quotes_1h = EXCLUDED.quotes_1h,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    values
                )
            self.conn.commit()
            if values:
                print(f"OK: {len(pairs_data)} pairs saved")
        except Exception as e:
            self.conn.rollback()
            print(f"Save error: {e}")
    
    def save_balance(self, exchange, balance_data, user_id=None):
        """Сохранение баланса в БД"""
        try:
            table_name = f'{exchange}_balance'
            print("  Saving balance to DB...", end=' ')
            
            if user_id is None:
                self.cursor.execute(
                    f"DELETE FROM {table_name} WHERE user_id IS NULL"
                )
            else:
                self.cursor.execute(
                    f"DELETE FROM {table_name} WHERE user_id = %s",
                    (user_id,),
                )
            
            values = []
            for asset, data in balance_data.items():
                values.append((
                    user_id,
                    asset,
                    data.get('free'),
                    data.get('locked'),
                    data.get('total'),
                ))
            
            if values:
                execute_values(
                    self.cursor,
                    f"""
                    INSERT INTO {table_name} (user_id, asset, free, locked, total, updated_at)
                    VALUES %s
                    """,
                    values,
                    template="(%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)"
                )
            self.conn.commit()
            if values:
                print(f"OK: {len(balance_data)} assets saved")
        except Exception as e:
            self.conn.rollback()
            print(f"Save error: {e}")

    def get_pairs(self, exchange):
        """Возвращает список торговых пар биржи."""
        table_name = f'{exchange}_pairs'
        self.cursor.execute(
            f"SELECT symbol FROM {table_name} ORDER BY symbol"
        )
        return [row[0] for row in self.cursor.fetchall()]

    def get_pair_info(self, exchange, symbol):
        """Возвращает информацию по торговой паре."""
        table_name = f'{exchange}_pairs'
        self.cursor.execute(
            f"""
            SELECT symbol, current_price, change_24h_percent, change_24h_absolute,
                   high_24h, low_24h, volume_24h, maker_fee, taker_fee,
                   min_order_amount, lot_size, ask_price, ask_volume,
                   bid_price, bid_volume, quotes_1h, updated_at
            FROM {table_name}
            WHERE symbol = %s
            """,
            (symbol,),
        )
        row = self.cursor.fetchone()
        if not row:
            return None

        keys = [
            'symbol', 'current_price', 'change_24h_percent', 'change_24h_absolute',
            'high_24h', 'low_24h', 'volume_24h', 'maker_fee', 'taker_fee',
            'min_order_amount', 'lot_size', 'ask_price', 'ask_volume',
            'bid_price', 'bid_volume', 'quotes_1h', 'updated_at'
        ]
        return dict(zip(keys, row))

    def get_coin_prices(self, coin_name):
        """Возвращает цены монеты на всех биржах из БД."""
        result = {}
        symbol = f"{coin_name.upper()}/USDT"
        for exchange in ('bybit', 'gateio', 'mexc'):
            pair_info = self.get_pair_info(exchange, symbol)
            if pair_info:
                result[exchange] = {
                    'price': float(pair_info.get('current_price') or 0),
                    'change_24h': float(pair_info.get('change_24h_percent') or 0),
                    'high_24h': float(pair_info.get('high_24h') or 0),
                    'low_24h': float(pair_info.get('low_24h') or 0),
                    'volume_24h': float(pair_info.get('volume_24h') or 0),
                    'updated_at': pair_info.get('updated_at'),
                }
            else:
                result[exchange] = None
        return result

    def get_balances(self, exchange, user_id=None):
        """Возвращает все балансы пользователя для указанной биржи."""
        table_name = f'{exchange}_balance'
        if user_id is None:
            self.cursor.execute(
                f"""
                SELECT asset, free, locked, total, COALESCE(updated_at, created_at)
                FROM {table_name}
                WHERE user_id IS NULL
                ORDER BY asset
                """
            )
        else:
            self.cursor.execute(
                f"""
                SELECT asset, free, locked, total, COALESCE(updated_at, created_at)
                FROM {table_name}
                WHERE user_id = %s
                ORDER BY asset
                """,
                (user_id,),
            )

        rows = self.cursor.fetchall()
        balances = {}
        for asset, free, locked, total, updated_at in rows:
            balances[asset] = {
                'free': float(free or 0),
                'locked': float(locked or 0),
                'total': float(total or 0),
                'updated_at': updated_at,
            }
        return balances

    def get_balance(self, exchange, asset, user_id=None):
        """Возвращает баланс конкретного актива пользователя."""
        balances = self.get_balances(exchange, user_id=user_id)
        asset_upper = str(asset or '').upper()
        for asset_name, balance in balances.items():
            if str(asset_name).upper() == asset_upper:
                return balance
        return None

    def get_latest_pairs_update(self, exchange):
        """Возвращает время последнего обновления цен по бирже."""
        table_name = f'{exchange}_pairs'
        self.cursor.execute(
            f"SELECT MAX(updated_at) FROM {table_name}"
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_latest_balance_update(self, exchange, user_id=None):
        """Возвращает время последнего обновления баланса пользователя."""
        table_name = f'{exchange}_balance'
        if user_id is None:
            self.cursor.execute(
                f"SELECT MAX(COALESCE(updated_at, created_at)) FROM {table_name} WHERE user_id IS NULL"
            )
        else:
            self.cursor.execute(
                f"SELECT MAX(COALESCE(updated_at, created_at)) FROM {table_name} WHERE user_id = %s",
                (user_id,),
            )
        row = self.cursor.fetchone()
        return row[0] if row else None

