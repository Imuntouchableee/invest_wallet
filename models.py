from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime


Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    password = Column(String)
    balance = Column(Integer, default=0, nullable=True)
    
    # Дополнительные поля профиля
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    country = Column(String, nullable=True, default="Россия")
    full_name = Column(String, nullable=True)
    avatar_color = Column(String, nullable=True, default="#00d4ff")
    bio = Column(String, nullable=True, default="Инвестор криптовалют")
    
    # Аватар профиля
    avatar_type = Column(String, nullable=True, default="icon")  # "icon", "image", "initials"
    avatar_icon = Column(String, nullable=True, default="PERSON")  # Название иконки
    avatar_path = Column(String, nullable=True)  # Путь к загруженному изображению
    
    # Восстановление пароля
    recovery_code = Column(String, nullable=True)  # 6-значный код
    recovery_code_expires = Column(DateTime, nullable=True)  # Срок действия кода
    
    # Статистика
    registration_date = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, default=datetime.now)
    total_trades = Column(Integer, default=0)
    total_invested = Column(Float, default=0.0)
    total_profit = Column(Float, default=0.0)
    best_asset = Column(String, nullable=True)
    
    # Текущий объем портфеля (для расчета изменений)
    portfolio_value = Column(Float, default=0.0)
    previous_portfolio_value = Column(Float, default=0.0)
    
    # Настройки
    notification_enabled = Column(Integer, default=1)
    dark_theme = Column(Integer, default=1)
    two_factor_auth = Column(Integer, default=0)

    def __repr__(self):
        return f"User('{self.name}', balance={self.balance}, email='{self.email}')"


class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    coin_name = Column(String)
    quantity = Column(Integer)
    value_rub = Column(Integer)
    purchase_date = Column(DateTime, default=datetime.now)
    purchase_price = Column(Float, nullable=True)

    user = relationship("User")


class PortfolioHistory(Base):
    """История объема портфеля для отслеживания динамики"""
    __tablename__ = 'portfolio_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    timestamp = Column(DateTime, default=datetime.now)
    portfolio_value = Column(Float)  # Стоимость портфеля в USD
    change = Column(Float, default=0.0)  # Изменение от предыдущего значения
    daily_change = Column(Float, default=0.0)  # Изменение за день
    
    user = relationship("User")


engine = create_engine('sqlite:///database.db', connect_args={'check_same_thread': False}, pool_pre_ping=True, pool_recycle=3600)
Session = sessionmaker(bind=engine)
session = Session()

# Создаём таблицы если их нет
Base.metadata.create_all(engine)
