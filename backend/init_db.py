"""
Скрипт для создания тестовых данных
"""
from backend.models import User, ExchangeAPIKey, session, Base, engine
from datetime import datetime

# Пересоздаем таблицы
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

# Создаем тестового пользователя
test_user = User(
    name='test',
    password='1234',
    email='test@example.com',
    full_name='Test User',
    avatar_icon='ROCKET_LAUNCH',
    avatar_color='#00d4ff',
    registration_date=datetime.now(),
)
session.add(test_user)
session.commit()

# Добавляем API ключи
keys = [
    ExchangeAPIKey(
        user_id=test_user.id,
        exchange_name='mexc',
        api_key='mx0vglWQFjtAzExj2B',
        secret_key='e09120ab22174fda9672db6aeb40adc3',
        passphrase=None,
    ),
    ExchangeAPIKey(
        user_id=test_user.id,
        exchange_name='gateio',
        api_key='785b0ee3075ee61ee7b0682e2a26f747',
        secret_key='9e39c9b89d88b22227fbf7f6af021263abdd7f501e69a4290e753e9408b49bd2',
        passphrase=None,
    ),
    ExchangeAPIKey(
        user_id=test_user.id,
        exchange_name='bybit',
        api_key='Y6eE25XhZXCz6iHbhx',
        secret_key='AXrAlyWcoSbBqBzt1IypRlNGlUSfsjcAGYMt',
        passphrase=None,
    ),
]

for key in keys:
    session.add(key)

session.commit()

print('Database created!')
print('User: test / 1234')
print(f'Exchanges: {len(keys)}')
