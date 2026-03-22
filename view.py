"""
Invest Wallet - Приложение для отслеживания криптопортфеля
Подключение к биржам Bybit, Gate.io, MEXC через API

Главный файл приложения с точкой входа.
UI модули вынесены в папку ui/
"""
import flet as ft
import logging
import threading
from datetime import datetime

from backend.models import User, ExchangeAPIKey, session
from data.main import main as run_data_updater

# Импорт UI модулей
from ui.config import DARK_BG, PRIMARY_COLOR
from ui.auth import show_login_screen, show_register_screen, show_forgot_password_screen
from ui.dialogs import (
    show_logout_confirm_dialog,
    show_add_exchange_dialog,
    show_exchange_settings_dialog,
    show_edit_profile_dialog,
)
from ui.trading import show_trading_dialog
from ui.profile import show_profile_page
from ui.assets_page import show_assets_page
from ui.main_screen import show_main_screen, show_no_exchanges_screen


# ============ ЛОГИРОВАНИЕ ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('invest_wallet.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

_data_updater_thread = None


def start_data_updater():
    global _data_updater_thread
    if _data_updater_thread and _data_updater_thread.is_alive():
        return

    _data_updater_thread = threading.Thread(
        target=run_data_updater,
        name='data-updater',
        daemon=True,
    )
    _data_updater_thread.start()
    logger.info('[START] Фоновый updater данных запущен')


def main(page: ft.Page):
    """Главная функция приложения"""
    page.title = "Invest Wallet"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = DARK_BG
    page.window.maximized = True
    page.padding = 0
    
    # Глобальное состояние
    current_user = {"user": None}
    portfolio_cache = {"data": None, "timestamp": None}
    
    # ============ CALLBACKS ============
    def _show_login():
        show_login_screen(
            page=page,
            current_user=current_user,
            show_main_screen_callback=_show_main,
            show_register_callback=_show_register,
            show_forgot_password_callback=_show_forgot_password,
        )
    
    def _show_register():
        show_register_screen(
            page=page,
            current_user=current_user,
            show_login_callback=_show_login,
            show_main_screen_callback=_show_main,
        )
    
    def _show_forgot_password():
        show_forgot_password_screen(
            page=page,
            show_login_callback=_show_login,
        )
    
    def _show_main():
        show_main_screen(
            page=page,
            current_user=current_user,
            portfolio_cache=portfolio_cache,
            show_login_callback=_show_login,
            show_profile_callback=_show_profile,
            show_trading_callback=_show_trading,
            show_logout_confirm_callback=_show_logout_confirm,
            show_exchange_settings_callback=_show_exchange_settings,
            show_no_exchanges_callback=_show_no_exchanges,
            show_assets_page_callback=_show_assets_page,
        )

    def _show_assets_page():
        show_assets_page(
            page=page,
            current_user=current_user,
            portfolio_cache=portfolio_cache,
            show_main_screen_callback=_show_main,
            show_trading_callback=_show_trading,
        )
    
    def _show_no_exchanges():
        show_no_exchanges_screen(
            page=page,
            show_add_exchange_callback=_show_add_exchange,
            logout_callback=_logout,
        )
    
    def _show_profile():
        show_profile_page(
            page=page,
            current_user=current_user,
            portfolio_cache=portfolio_cache,
            show_main_screen_callback=_show_main,
            show_exchange_settings_callback=_show_exchange_settings,
            show_logout_confirm_callback=_show_logout_confirm,
            show_edit_profile_callback=_show_edit_profile,
        )
    
    def _show_edit_profile():
        show_edit_profile_dialog(
            page=page,
            current_user=current_user,
            show_profile_callback=_show_profile,
        )
    
    def _show_trading(asset=None, exchange_name=None, side=None):
        user = current_user["user"]
        user_keys = session.query(ExchangeAPIKey).filter_by(user_id=user.id, is_active=True).all()
        show_trading_dialog(
            page=page,
            current_user=current_user,
            user_keys=user_keys,
            asset=asset,
            exchange_name=exchange_name,
            side=side,
        )
    
    def _show_logout_confirm():
        show_logout_confirm_dialog(
            page=page,
            logout_callback=_logout,
        )
    
    def _show_add_exchange(preselected_exchange=None):
        show_add_exchange_dialog(
            page=page,
            current_user=current_user,
            show_main_screen_callback=_show_main,
            preselected_exchange=preselected_exchange,
        )
    
    def _show_exchange_settings():
        show_exchange_settings_dialog(
            page=page,
            current_user=current_user,
            show_main_screen_callback=_show_main,
            show_add_exchange_callback=_show_add_exchange,
        )
    
    def _logout():
        current_user["user"] = None
        portfolio_cache["data"] = None
        _show_login()
    
    # ============ СТАРТ ============
    logger.info("[START] Приложение Invest Wallet запущено")
    _show_login()


if __name__ == "__main__":
    start_data_updater()
    ft.app(target=main)
