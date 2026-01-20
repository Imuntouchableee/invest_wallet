"""
Backend модули приложения Invest Wallet
"""
from backend.models import User, ExchangeAPIKey, PortfolioHistory, session, engine, Base
from backend.api import (
    get_exchange_instance,
    test_exchange_connection,
    fetch_user_portfolio,
    fetch_balance_for_exchange,
    calculate_portfolio_value,
    fetch_coin_prices,
    get_available_trading_pairs,
    get_current_price,
    create_order,
)
from backend.email_service import (
    generate_recovery_code,
    send_recovery_email_mock,
    verify_recovery_code,
    get_code_expiry_time,
)

__all__ = [
    # Models
    'User', 'ExchangeAPIKey', 'PortfolioHistory', 'session', 'engine', 'Base',
    # API
    'get_exchange_instance', 'test_exchange_connection', 'fetch_user_portfolio',
    'fetch_balance_for_exchange', 'calculate_portfolio_value', 'fetch_coin_prices',
    'get_available_trading_pairs', 'get_current_price', 'create_order',
    # Email
    'generate_recovery_code', 'send_recovery_email_mock', 'verify_recovery_code',
    'get_code_expiry_time',
]
