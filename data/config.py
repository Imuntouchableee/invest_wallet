"""Конфигурация подключений к API и БД"""


EXCHANGES = {
    'mexc': {
        'api_key': 'mx0vglWQFjtAzExj2B',
        'api_secret': 'e09120ab22174fda9672db6aeb40adc3',
    },
    'bybit': {
        'api_key': 'Y6eE25XhZXCz6iHbhx',
        'api_secret': 'AXrAlyWcoSbBqBzt1IypRlNGlUSfsjcAGYMt',
    },
    'gateio': {
        'api_key': '785b0ee3075ee61ee7b0682e2a26f747',
        'api_secret': '9e39c9b89d88b22227fbf7f6af021263abdd7f501e69a4290e753e9408b49bd2',
    }
}

DATABASE = {
    'host': 'localhost',
    'port': 5432,
    'database': 'crypto_trader',
    'user': 'postgres',
    'password': 'Sasa.123321',
}

# Параметры
QUOTE_CURRENCY = 'USDT'
