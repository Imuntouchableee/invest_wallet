"""Работа с базой данных PostgreSQL"""
import psycopg2
from psycopg2.extras import execute_values
from config import DATABASE


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
            print("✓ Подключение к БД успешно")
            return True
        except Exception as e:
            print(f"✗ Ошибка подключения к БД: {e}")
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
                    ask_price DECIMAL(20, 8),
                    ask_volume DECIMAL(20, 8),
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
                    ask_price DECIMAL(20, 8),
                    ask_volume DECIMAL(20, 8),
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
                    ask_price DECIMAL(20, 8),
                    ask_volume DECIMAL(20, 8),
                    quotes_1h TEXT,
                    taker_fee DECIMAL(10, 6),
                    min_order_amount DECIMAL(20, 8),
                    lot_size DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для баланса MEXC
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS mexc_balance (
                    id SERIAL PRIMARY KEY,
                    asset VARCHAR(50),
                    free DECIMAL(20, 8),
                    locked DECIMAL(20, 8),
                    total DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для баланса BYBIT
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS bybit_balance (
                    id SERIAL PRIMARY KEY,
                    asset VARCHAR(50),
                    free DECIMAL(20, 8),
                    locked DECIMAL(20, 8),
                    total DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для баланса GATEIO
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS gateio_balance (
                    id SERIAL PRIMARY KEY,
                    asset VARCHAR(50),
                    free DECIMAL(20, 8),
                    locked DECIMAL(20, 8),
                    total DECIMAL(20, 8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.conn.commit()
            print("✓ Таблицы созданы/проверены")
            return True
        except Exception as e:
            print(f"✗ Ошибка создания таблиц: {e}")
            return False
    
    def save_pairs(self, exchange, pairs_data):
        """Сохранение данных по парам в БД"""
        try:
            table_name = f'{exchange}_pairs'
            print(f"  💾 Сохраняю пары в БД...", end=' ')
            
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
                    data.get('ask_price'),
                    data.get('ask_volume'),
                    data.get('quotes_1h'),
                ))
            
            if values:
                execute_values(
                    self.cursor,
                    f"""
                    INSERT INTO {table_name} 
                    (symbol, current_price, change_24h_percent, change_24h_absolute,
                     high_24h, low_24h, volume_24h, maker_fee, taker_fee, 
                     min_order_amount, lot_size, ask_price, ask_volume, quotes_1h)
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
                        quotes_1h = EXCLUDED.quotes_1h,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    values
                )
                self.conn.commit()
                print(f"✓ {len(pairs_data)} пар сохранено")
        except Exception as e:
            print(f"✗ Ошибка сохранения: {e}")
    
    def save_balance(self, exchange, balance_data):
        """Сохранение баланса в БД"""
        try:
            table_name = f'{exchange}_balance'
            print(f"  💾 Сохраняю баланс в БД...", end=' ')
            
            # Очистка старых записей
            self.cursor.execute(f"DELETE FROM {table_name}")
            
            values = []
            for asset, data in balance_data.items():
                values.append((
                    asset,
                    data.get('free'),
                    data.get('locked'),
                    data.get('total'),
                ))
            
            if values:
                execute_values(
                    self.cursor,
                    f"""
                    INSERT INTO {table_name} (asset, free, locked, total)
                    VALUES %s
                    """,
                    values
                )
                self.conn.commit()
                print(f"✓ {len(balance_data)} активов сохранено")
        except Exception as e:
            print(f"✗ Ошибка сохранения: {e}")
