"""
Главный экран с портфелем
"""
import flet as ft
import threading
import logging
from datetime import datetime

from ui.config import (
    DARK_BG, CARD_BG, PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    EXCHANGE_COLORS, EXCHANGE_NAMES,
)
from ui.components import get_user_level
from backend.models import ExchangeAPIKey, session
from backend.api import fetch_user_portfolio

logger = logging.getLogger(__name__)


def _make_trade_handler(show_trading_callback, asset=None, exchange_name=None,
                        side=None):
    """Фиксирует параметры открытия торгового окна без проблем замыканий."""

    frozen_asset = dict(asset) if isinstance(asset, dict) else asset

    def handler(e):
        show_trading_callback(
            asset=frozen_asset,
            exchange_name=exchange_name,
            side=side,
        )

    return handler


def show_no_exchanges_screen(page: ft.Page, show_add_exchange_callback, logout_callback):
    """Экран, когда нет подключенных бирж"""
    page.controls.clear()
    
    page.add(
        ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.LINK_OFF, size=80, color=TEXT_SECONDARY),
                ft.Container(height=20),
                ft.Text("Нет подключенных бирж", size=24, weight="bold", color=TEXT_PRIMARY),
                ft.Container(height=10),
                ft.Text(
                    "Добавьте API ключи для подключения к биржам",
                    size=14, color=TEXT_SECONDARY, text_align="center"
                ),
                ft.Container(height=30),
                ft.ElevatedButton(
                    text="ПОДКЛЮЧИТЬ БИРЖУ",
                    icon=ft.icons.ADD,
                    style=ft.ButtonStyle(
                        bgcolor=PRIMARY_COLOR,
                        color=DARK_BG,
                        padding=ft.padding.symmetric(horizontal=40, vertical=15),
                    ),
                    on_click=lambda e: show_add_exchange_callback(),
                ),
                ft.Container(height=20),
                ft.TextButton(
                    text="Выйти из аккаунта",
                    style=ft.ButtonStyle(color=ACCENT_COLOR),
                    on_click=lambda e: logout_callback(),
                ),
            ], alignment="center", horizontal_alignment="center"),
            expand=True,
            alignment=ft.alignment.center,
        )
    )
    page.update()


def show_main_screen(page: ft.Page, current_user: dict, portfolio_cache: dict,
                     show_login_callback, show_profile_callback, show_trading_callback,
                     show_logout_confirm_callback, show_exchange_settings_callback,
                     show_no_exchanges_callback):
    """Главный экран с портфелем"""
    user = current_user["user"]
    if not user:
        show_login_callback()
        return
    
    # Получаем API ключи пользователя
    user_keys = session.query(ExchangeAPIKey).filter_by(user_id=user.id, is_active=True).all()
    
    if not user_keys:
        show_no_exchanges_callback()
        return
    
    page.controls.clear()
    
    # Индикатор загрузки
    loading = ft.Container(
        content=ft.Column([
            ft.ProgressRing(color=PRIMARY_COLOR, width=50, height=50),
            ft.Container(height=20),
            ft.Text("Загрузка портфеля...", size=16, color=TEXT_SECONDARY),
        ], alignment="center", horizontal_alignment="center"),
        expand=True,
        alignment=ft.alignment.center,
    )
    page.add(loading)
    page.update()
    
    # Получаем данные портфеля
    portfolio = fetch_user_portfolio(user_keys)
    portfolio_cache["data"] = portfolio
    portfolio_cache["timestamp"] = datetime.now()
    
    page.controls.clear()
    
    # Определяем уровень
    level_name, level_color, level_icon = get_user_level(portfolio['total_usd'])
    
    # ============ HEADER ============
    header = ft.Container(
        content=ft.Row([
            # Профиль
            ft.Container(
                content=ft.Row([
                    ft.CircleAvatar(
                        content=ft.Text(user.name[0].upper(), size=24, weight="bold", color=DARK_BG),
                        radius=30,
                        bgcolor=user.avatar_color or PRIMARY_COLOR,
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(user.name, size=18, weight="bold", color=TEXT_PRIMARY),
                            ft.Container(
                                content=ft.Text(level_name, size=10, weight="bold", color=DARK_BG),
                                bgcolor=level_color,
                                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                border_radius=10,
                            ),
                        ], spacing=10, vertical_alignment="center"),
                        ft.Text(f"Подключено бирж: {len(user_keys)}", size=12, color=TEXT_SECONDARY),
                    ], spacing=2),
                ], spacing=15),
                on_click=lambda e: show_profile_callback(),
                ink=True,
            ),
            ft.Container(expand=True),
            # Общий баланс
            ft.Column([
                ft.Text("Общий портфель", size=12, color=TEXT_SECONDARY),
                ft.Text(f"${portfolio['total_usd']:,.2f}", size=28, weight="bold", color=SUCCESS_COLOR),
            ], spacing=2, horizontal_alignment="end"),
            # Выход
            ft.IconButton(
                icon=ft.icons.LOGOUT,
                icon_color=ACCENT_COLOR,
                tooltip="Выйти",
                on_click=lambda e: show_logout_confirm_callback(),
            ),
        ], alignment="spaceBetween", vertical_alignment="center"),
        padding=20,
        bgcolor=CARD_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR)),
    )
    
    # ============ ВКЛАДКИ БИРЖ ============
    def create_exchange_tab(exchange_name: str, data: dict):
        """Создает вкладку для биржи"""
        color = EXCHANGE_COLORS.get(exchange_name, PRIMARY_COLOR)
        name = EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())
        # кнопки покупки/продажи — стили согласованы с trading.py
        BUY_COLOR = "#00C853"
        SELL_COLOR = "#FF5252"
        
        if data['status'] == 'error':
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.ERROR_OUTLINE, size=64, color=ACCENT_COLOR),
                    ft.Container(height=10),
                    ft.Text(f"Ошибка подключения к {name}", size=18, color=ACCENT_COLOR),
                    ft.Text(data.get('error', 'Неизвестная ошибка'), size=14, color=TEXT_SECONDARY),
                ], alignment="center", horizontal_alignment="center"),
                expand=True,
                alignment=ft.alignment.center,
            )
        
        # Находим USDT баланс
        usdt_balance = 0.0
        tradable_assets = []
        for asset in data['assets']:
            if asset['currency'].upper() in ('USDT', 'USDC', 'BUSD', 'DAI'):
                usdt_balance += asset['value_usd']
            else:
                tradable_assets.append(asset)
        
        # USDT баланс (торговый баланс)
        usdt_info = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.icons.ATTACH_MONEY, size=20, color=DARK_BG),
                    width=40, height=40,
                    border_radius=10,
                    bgcolor="#26A17B",  # Цвет USDT
                    alignment=ft.alignment.center,
                ),
                ft.Column([
                    ft.Text("Торговый баланс", size=12, color=TEXT_SECONDARY),
                    ft.Text("USDT / Стейблкоины", size=10, color=TEXT_SECONDARY),
                ], spacing=2, expand=True),
                ft.Column([
                    ft.Text(f"${usdt_balance:,.2f}", size=18, weight="bold", color="#26A17B"),
                    ft.Text("Доступно для покупок", size=10, color=TEXT_SECONDARY),
                ], spacing=2, horizontal_alignment="end"),
            ], vertical_alignment="center", spacing=12),
            padding=15,
            bgcolor=ft.colors.with_opacity(0.1, "#26A17B"),
            border_radius=12,
            border=ft.border.all(1, ft.colors.with_opacity(0.3, "#26A17B")),
            margin=ft.margin.only(bottom=10),
        ) if usdt_balance > 0 else ft.Container()
        
        # Список активов (без стейблкоинов)
        asset_list = ft.Column(spacing=8, scroll="adaptive", expand=True)
        
        if tradable_assets:
            for asset in tradable_assets:
                asset_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Text(
                                    asset['currency'][:4], 
                                    size=12, weight="bold", 
                                    color=DARK_BG, text_align="center"
                                ),
                                width=45, height=45,
                                border_radius=10,
                                bgcolor=color,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column([
                                ft.Text(asset['currency'], size=16, weight="bold", color=TEXT_PRIMARY),
                                ft.Text(f"Кол-во: {asset['amount']:.6f}", size=12, color=TEXT_SECONDARY),
                            ], spacing=2, expand=True),
                            ft.Column([
                                ft.Text(f"${asset['value_usd']:.2f}", size=16, weight="bold", color=SUCCESS_COLOR),
                                ft.Text(f"${asset['price_usd']:.4f}", size=11, color=TEXT_SECONDARY),
                            ], spacing=2, horizontal_alignment="end"),
                            # Кнопки покупки/продажи
                            ft.Row([
                                ft.Container(
                                    content=ft.Icon(ft.icons.ARROW_DOWNWARD, size=18, color=DARK_BG),
                                    width=36, height=36,
                                    border_radius=8,
                                    bgcolor=SUCCESS_COLOR,
                                    alignment=ft.alignment.center,
                                    on_click=_make_trade_handler(
                                        show_trading_callback,
                                        asset=asset,
                                        exchange_name=exchange_name,
                                        side="buy",
                                    ),
                                    ink=True,
                                    tooltip="Купить",
                                ),
                                ft.Container(
                                    content=ft.Icon(ft.icons.ARROW_UPWARD, size=18, color=DARK_BG),
                                    width=36, height=36,
                                    border_radius=8,
                                    bgcolor=ACCENT_COLOR,
                                    alignment=ft.alignment.center,
                                    on_click=_make_trade_handler(
                                        show_trading_callback,
                                        asset=asset,
                                        exchange_name=exchange_name,
                                        side="sell",
                                    ),
                                    ink=True,
                                    tooltip="Продать",
                                ),
                            ], spacing=6),
                        ], vertical_alignment="center", spacing=12),
                        padding=15,
                        bgcolor=CARD_BG,
                        border_radius=12,
                        border=ft.border.all(1, BORDER_COLOR),
                    )
                )
        else:
            asset_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SAVINGS, size=48, color=TEXT_SECONDARY),
                        ft.Text("Нет торгуемых активов", size=16, color=TEXT_SECONDARY),
                        ft.Text("Используйте USDT для покупки криптовалют", size=12, color=TEXT_SECONDARY),
                    ], alignment="center", horizontal_alignment="center"),
                    padding=40,
                    alignment=ft.alignment.center,
                )
            )
        
        # Количество торгуемых активов (без стейблкоинов)
        tradable_count = len(tradable_assets)
        
        return ft.Container(
            content=ft.Column([
                # Заголовок биржи
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_BALANCE, size=24, color=color),
                        ft.Text(name, size=20, weight="bold", color=color),
                        ft.Container(expand=True),
                        ft.Column([
                            ft.Text("Общий баланс", size=11, color=TEXT_SECONDARY),
                            ft.Text(f"${data['total_usd']:,.2f}", size=18, weight="bold", color=SUCCESS_COLOR),
                        ], horizontal_alignment="end", spacing=2),
                        ft.Container(width=12),
                        # Всегда доступные кнопки Купить/Продать для этой биржи
                        ft.Row([
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.ARROW_DOWNWARD_ROUNDED, size=18, color=DARK_BG),
                                    ft.Container(width=8),
                                    ft.Text("Купить", size=13, weight="bold", color=DARK_BG),
                                ], alignment="center"),
                                padding=ft.padding.symmetric(horizontal=12),
                                height=40,
                                border_radius=8,
                                bgcolor=BUY_COLOR,
                                alignment=ft.alignment.center,
                                ink=True,
                                on_click=_make_trade_handler(
                                    show_trading_callback,
                                    exchange_name=exchange_name,
                                    side="buy",
                                ),
                            ),
                            ft.Container(width=8),
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.ARROW_UPWARD_ROUNDED, size=18, color=DARK_BG),
                                    ft.Container(width=8),
                                    ft.Text("Продать", size=13, weight="bold", color=DARK_BG),
                                ], alignment="center"),
                                padding=ft.padding.symmetric(horizontal=12),
                                height=40,
                                border_radius=8,
                                bgcolor=SELL_COLOR,
                                alignment=ft.alignment.center,
                                ink=True,
                                on_click=_make_trade_handler(
                                    show_trading_callback,
                                    exchange_name=exchange_name,
                                    side="sell",
                                ),
                            ),
                        ], spacing=6),
                    ], vertical_alignment="center"),
                    padding=15,
                    bgcolor=ft.colors.with_opacity(0.1, color),
                    border_radius=12,
                    margin=ft.margin.only(bottom=10),
                ),
                # USDT баланс (если есть)
                usdt_info,
                # Количество торгуемых активов
                ft.Text(f"Торгуемых активов: {tradable_count}", size=14, color=TEXT_SECONDARY),
                ft.Container(height=10),
                # Список активов
                asset_list,
            ], expand=True),
            padding=15,
            expand=True,
        )
    
    # Создаем вкладки
    tabs = []
    for exchange_name, data in portfolio['exchanges'].items():
        color = EXCHANGE_COLORS.get(exchange_name, PRIMARY_COLOR)
        name = EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())
        
        status_icon = ft.icons.CHECK_CIRCLE if data['status'] == 'success' else ft.icons.ERROR
        status_color = SUCCESS_COLOR if data['status'] == 'success' else ACCENT_COLOR
        
        tabs.append(
            ft.Tab(
                tab_content=ft.Row([
                    ft.Icon(status_icon, size=14, color=status_color),
                    ft.Text(name, color=color, weight="bold"),
                    ft.Text(f"${data['total_usd']:,.0f}", size=12, color=TEXT_SECONDARY) if data['status'] == 'success' else ft.Container(),
                ], spacing=8),
                content=create_exchange_tab(exchange_name, data),
            )
        )
    
    # Добавляем вкладку "Все активы"
    all_assets_content = ft.Column(spacing=8, scroll="adaptive", expand=True)
    
    # Фильтруем стейблкоины из общего списка
    tradable_all_assets = [a for a in portfolio['all_assets'] 
                           if a['currency'].upper() not in ('USDT', 'USDC', 'BUSD', 'DAI')]
    
    for asset in tradable_all_assets:
        exchange_color = EXCHANGE_COLORS.get(asset['exchange'], PRIMARY_COLOR)
        all_assets_content.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(
                            asset['currency'][:4], 
                            size=12, weight="bold", 
                            color=DARK_BG, text_align="center"
                        ),
                        width=45, height=45,
                        border_radius=10,
                        bgcolor=exchange_color,
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text(asset['currency'], size=16, weight="bold", color=TEXT_PRIMARY),
                        ft.Row([
                            ft.Container(
                                content=ft.Text(EXCHANGE_NAMES.get(asset['exchange'], asset['exchange']), 
                                               size=10, color=DARK_BG),
                                bgcolor=exchange_color,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                border_radius=6,
                            ),
                            ft.Text(f"Кол-во: {asset['amount']:.6f}", size=11, color=TEXT_SECONDARY),
                        ], spacing=8),
                    ], spacing=4, expand=True),
                    ft.Column([
                        ft.Text(f"${asset['value_usd']:.2f}", size=16, weight="bold", color=SUCCESS_COLOR),
                        ft.Text(f"${asset['price_usd']:.4f}", size=11, color=TEXT_SECONDARY),
                    ], spacing=2, horizontal_alignment="end"),
                    # Кнопки покупки/продажи
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.icons.ARROW_DOWNWARD, size=18, color=DARK_BG),
                            width=36, height=36,
                            border_radius=8,
                            bgcolor=SUCCESS_COLOR,
                            alignment=ft.alignment.center,
                            on_click=_make_trade_handler(
                                show_trading_callback,
                                asset=asset,
                                exchange_name=asset['exchange'],
                                side="buy",
                            ),
                            ink=True,
                            tooltip="Купить",
                        ),
                        ft.Container(
                            content=ft.Icon(ft.icons.ARROW_UPWARD, size=18, color=DARK_BG),
                            width=36, height=36,
                            border_radius=8,
                            bgcolor=ACCENT_COLOR,
                            alignment=ft.alignment.center,
                            on_click=_make_trade_handler(
                                show_trading_callback,
                                asset=asset,
                                exchange_name=asset['exchange'],
                                side="sell",
                            ),
                            ink=True,
                            tooltip="Продать",
                        ),
                    ], spacing=6),
                ], vertical_alignment="center"),
                padding=15,
                bgcolor=CARD_BG,
                border_radius=12,
                border=ft.border.all(1, BORDER_COLOR),
            )
        )
    
    tabs.insert(0, ft.Tab(
        tab_content=ft.Row([
            ft.Icon(ft.icons.ALL_INCLUSIVE, size=14, color=PRIMARY_COLOR),
            ft.Text("Все активы", color=PRIMARY_COLOR, weight="bold"),
            ft.Text(f"${portfolio['total_usd']:,.0f}", size=12, color=TEXT_SECONDARY),
        ], spacing=8),
        content=ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.WALLET, size=24, color=PRIMARY_COLOR),
                        ft.Text("Все активы", size=20, weight="bold", color=PRIMARY_COLOR),
                        ft.Container(expand=True),
                        ft.Text(f"Торгуемых: {len(tradable_all_assets)} активов", size=14, color=TEXT_SECONDARY),
                    ], vertical_alignment="center"),
                    padding=15,
                    bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                    border_radius=12,
                    margin=ft.margin.only(bottom=15),
                ),
                all_assets_content if tradable_all_assets else ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SAVINGS, size=64, color=TEXT_SECONDARY),
                        ft.Text("Нет активов", size=18, color=TEXT_SECONDARY),
                    ], alignment="center", horizontal_alignment="center"),
                    expand=True,
                    alignment=ft.alignment.center,
                ),
            ], expand=True),
            padding=15,
            expand=True,
        ),
    ))
    
    tabs_container = ft.Tabs(
        tabs=tabs,
        animation_duration=300,
        expand=True,
        indicator_color=PRIMARY_COLOR,
        label_color=TEXT_PRIMARY,
        unselected_label_color=TEXT_SECONDARY,
    )
    
    # ============ FOOTER ============
    footer = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=16, color=SECONDARY_COLOR),
                ft.Text("Invest Wallet", size=12, weight="bold", color=SECONDARY_COLOR),
                ft.Text("v2.0", size=11, color=TEXT_SECONDARY),
            ], spacing=8),
            ft.Container(expand=True),
            ft.TextButton(
                content=ft.Row([
                    ft.Icon(ft.icons.SETTINGS, size=14, color=TEXT_SECONDARY),
                    ft.Text("Настройки бирж", size=12, color=TEXT_SECONDARY),
                ], spacing=5),
                on_click=lambda e: show_exchange_settings_callback(),
            ),
            ft.Text("© 2024", size=11, color=TEXT_SECONDARY, italic=True),
        ], vertical_alignment="center"),
        padding=ft.padding.symmetric(horizontal=20, vertical=10),
        bgcolor=CARD_BG,
        border=ft.border.only(top=ft.BorderSide(1, BORDER_COLOR)),
    )
    
    # Собираем страницу
    page.add(
        ft.Column([
            header,
            ft.Container(content=tabs_container, expand=True, padding=10),
            footer,
        ], expand=True, spacing=0)
    )
    page.update()
    
    # Автообновление каждые 60 секунд
    def auto_refresh():
        import time
        time.sleep(60)
        while current_user["user"] is not None:
            try:
                user_keys_refresh = session.query(ExchangeAPIKey).filter_by(user_id=current_user["user"].id, is_active=True).all()
                if user_keys_refresh:
                    portfolio_new = fetch_user_portfolio(user_keys_refresh)
                    portfolio_cache["data"] = portfolio_new
                    portfolio_cache["timestamp"] = datetime.now()
                    logger.info(f"[OK] Портфель обновлён. Общая стоимость: ${portfolio_new['total_usd']:,.2f}")
            except Exception as e:
                logger.error(f"[ERROR] Ошибка обновления портфеля: {str(e)[:100]}")
            time.sleep(60)
    
    refresh_thread = threading.Thread(target=auto_refresh, daemon=True)
    refresh_thread.start()
    logger.info(f"[START] Автообновление портфеля запущено (интервал: 60 сек)")
