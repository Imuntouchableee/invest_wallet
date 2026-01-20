"""
UI модули приложения Invest Wallet
"""
from ui.config import *
from ui.components import show_snack_bar, get_user_level
from ui.auth import show_login_screen, show_register_screen, show_forgot_password_screen
from ui.dialogs import (
    show_logout_confirm_dialog,
    show_add_exchange_dialog,
    show_exchange_settings_dialog,
    show_edit_profile_dialog,
)
from ui.trading import show_trading_dialog
from ui.profile import show_profile_page
from ui.main_screen import show_main_screen, show_no_exchanges_screen

__all__ = [
    # Config
    'DARK_BG', 'CARD_BG', 'PRIMARY_COLOR', 'SECONDARY_COLOR', 'ACCENT_COLOR',
    'TEXT_PRIMARY', 'TEXT_SECONDARY', 'BORDER_COLOR', 'SUCCESS_COLOR', 'WARNING_COLOR',
    'EXCHANGE_COLORS', 'EXCHANGE_NAMES',
    # Components
    'show_snack_bar', 'get_user_level',
    # Auth
    'show_login_screen', 'show_register_screen', 'show_forgot_password_screen',
    # Dialogs
    'show_logout_confirm_dialog', 'show_add_exchange_dialog', 'show_exchange_settings_dialog',
    'show_trading_dialog', 'show_edit_profile_dialog',
    # Screens
    'show_profile_page', 'show_main_screen', 'show_no_exchanges_screen',
]
