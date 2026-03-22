from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from data.config import DATABASE


Base = declarative_base()


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    password = Column(String)
    
    # Профиль
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    country = Column(String, nullable=True, default="Россия")
    full_name = Column(String, nullable=True)
    
    # Аватар
    avatar_type = Column(String, nullable=True, default="icon")
    avatar_icon = Column(String, nullable=True, default="PERSON")
    avatar_color = Column(String, nullable=True, default="#00d4ff")
    
    # Восстановление пароля
    recovery_code = Column(String, nullable=True)
    recovery_code_expires = Column(DateTime, nullable=True)
    
    # Даты
    registration_date = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, default=datetime.now)
    
    # Связи
    exchange_keys = relationship(
        "ExchangeAPIKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    portfolio_history = relationship(
        "PortfolioHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    trade_decisions = relationship(
        "TradeDecisionHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"User('{self.name}', email='{self.email}')"


class ExchangeAPIKey(Base):
    """API ключи пользователя для бирж"""
    __tablename__ = 'exchange_api_keys'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    exchange_name = Column(String)  # 'bybit', 'gateio', 'mexc'
    api_key = Column(String)
    secret_key = Column(String)
    passphrase = Column(String, nullable=True)  # Не используется
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    last_sync = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="exchange_keys")
    
    def __repr__(self):
        return (
            f"ExchangeAPIKey(user={self.user_id}, "
            f"exchange='{self.exchange_name}')"
        )


class PortfolioHistory(Base):
    """История портфеля для графиков"""
    __tablename__ = 'portfolio_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    timestamp = Column(DateTime, default=datetime.now)
    
    # Общие данные
    total_value_usd = Column(Float, default=0.0)
    
    # По биржам
    bybit_value = Column(Float, default=0.0)
    gateio_value = Column(Float, default=0.0)
    mexc_value = Column(Float, default=0.0)
    
    user = relationship("User", back_populates="portfolio_history")


class TradeDecisionHistory(Base):
    """История качества торговых решений пользователя."""
    __tablename__ = 'trade_decision_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    actual_exchange = Column(String, nullable=False)
    actual_price = Column(Float, default=0.0)
    amount = Column(Float, default=0.0)
    notional_usdt = Column(Float, default=0.0)

    best_exchange = Column(String, nullable=True)
    best_possible_price = Column(Float, default=0.0)
    best_liquidity_exchange = Column(String, nullable=True)
    alternative_prices = Column(Text, nullable=True)

    avoidable_loss = Column(Float, default=0.0)
    avoidable_loss_pct = Column(Float, default=0.0)
    execution_quality_score = Column(Float, default=0.0)
    liquidity_alignment_score = Column(Float, default=0.0)

    user = relationship("User", back_populates="trade_decisions")


def build_postgres_url() -> str:
    """Собирает SQLAlchemy URL для PostgreSQL из общего конфига."""
    return (
        f"postgresql+psycopg2://{DATABASE['user']}:{DATABASE['password']}"
        f"@{DATABASE['host']}:{DATABASE['port']}/{DATABASE['database']}"
    )


SQLALCHEMY_DATABASE_URL = build_postgres_url()


# Подключение к БД
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
session = SessionLocal()

# Создаём таблицы
Base.metadata.create_all(engine)
