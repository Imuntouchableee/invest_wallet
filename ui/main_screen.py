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
from ui.slippage import show_slippage_analysis_dialog
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


def _make_slippage_handler(page, asset=None):
    """Открывает окно анализа проскальзывания для выбранного актива."""

    frozen_asset = dict(asset) if isinstance(asset, dict) else asset

    def handler(e):
        show_slippage_analysis_dialog(page, frozen_asset)

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

    total_value_text = ft.Text(
        "$0.00",
        size=32,
        weight="w700",
        color=TEXT_PRIMARY,
    )
    level_chip_text = ft.Text("", size=10, weight="bold", color=DARK_BG)
    user_name_text = ft.Text(
        user.name,
        size=18,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    connected_exchanges_text = ft.Text(
        str(len(user_keys)),
        size=16,
        color=TEXT_PRIMARY,
        weight="bold",
    )
    assets_count_text = ft.Text(
        "0",
        size=16,
        color=TEXT_PRIMARY,
        weight="bold",
    )
    balance_caption_text = ft.Text(
        "Совокупная стоимость",
        size=11,
        color=TEXT_SECONDARY,
    )
    update_time_text = ft.Text(
        "Обновлено только что",
        size=10,
        color=TEXT_SECONDARY,
    )
    reserve_text = ft.Text(
        "$0",
        size=16,
        color=TEXT_PRIMARY,
        weight="bold",
    )
    sync_status_text = ft.Text(
        "Синхронизация активна",
        size=9,
        color=PRIMARY_COLOR,
        weight="bold",
    )
    sync_status_chip = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.SYNC, size=12, color=PRIMARY_COLOR),
            sync_status_text,
        ], spacing=6, vertical_alignment="center"),
        padding=ft.padding.symmetric(horizontal=8, vertical=5),
        border_radius=999,
        bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
        border=ft.border.all(
            1,
            ft.colors.with_opacity(0.25, PRIMARY_COLOR),
        ),
    )
    level_chip = ft.Container(
        content=level_chip_text,
        bgcolor=PRIMARY_COLOR,
        padding=ft.padding.symmetric(horizontal=9, vertical=3),
        border_radius=999,
    )

    def create_info_cell(title: str, value_control, accent_color: str):
        return ft.Container(
            content=ft.Column([
                ft.Text(title, size=8, color=TEXT_SECONDARY),
                ft.Row([
                    ft.Container(
                        width=6,
                        height=6,
                        border_radius=999,
                        bgcolor=accent_color,
                    ),
                    value_control,
                ], spacing=8, vertical_alignment="center"),
            ], spacing=4),
            padding=ft.padding.symmetric(horizontal=12, vertical=9),
            border_radius=14,
            bgcolor=ft.colors.with_opacity(0.18, "#0b1119"),
            border=ft.border.all(1, ft.colors.with_opacity(0.44, BORDER_COLOR)),
            expand=True,
        )

    header_divider = ft.Container(
        width=1,
        height=74,
        bgcolor=ft.colors.with_opacity(0.65, BORDER_COLOR),
        border_radius=999,
    )

    profile_panel = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.CircleAvatar(
                    content=ft.Text(
                        user.name[0].upper(),
                        size=20,
                        weight="bold",
                        color=DARK_BG,
                    ),
                    radius=22,
                    bgcolor=user.avatar_color or PRIMARY_COLOR,
                ),
                padding=3,
                border_radius=999,
                border=ft.border.all(
                    1,
                    ft.colors.with_opacity(0.35, PRIMARY_COLOR),
                ),
            ),
            ft.Column([
                ft.Text(
                    "ПРОФИЛЬ",
                    size=8,
                    weight="bold",
                    color=TEXT_SECONDARY,
                ),
                ft.Row([
                    user_name_text,
                    level_chip,
                ], spacing=6, vertical_alignment="center"),
            ], spacing=3, alignment="center"),
        ], spacing=12, vertical_alignment="center"),
        width=250,
        on_click=lambda e: show_profile_callback(),
        ink=True,
    )

    value_panel = ft.Container(
        content=ft.Row([
            ft.Container(
                width=4,
                height=58,
                border_radius=999,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_center,
                    end=ft.alignment.bottom_center,
                    colors=[PRIMARY_COLOR, SECONDARY_COLOR],
                ),
            ),
            ft.Container(width=14),
            ft.Column([
                ft.Row([
                    ft.Text(
                        "КОНСОЛИДИРОВАННЫЙ ПОРТФЕЛЬ",
                        size=9,
                        weight="bold",
                        color=TEXT_SECONDARY,
                    ),
                    ft.Container(expand=True),
                    sync_status_chip,
                ], vertical_alignment="center"),
                total_value_text,
                ft.Row([
                    balance_caption_text,
                    ft.Text("•", size=10, color=BORDER_COLOR),
                    update_time_text,
                ], spacing=8, vertical_alignment="center"),
            ], spacing=3, expand=True),
        ], spacing=0, vertical_alignment="center"),
        expand=True,
        height=120,
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        border_radius=18,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=["#101824", "#0c141e", "#0b1018"],
        ),
        border=ft.border.all(
            1,
            ft.colors.with_opacity(0.56, PRIMARY_COLOR),
        ),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=18,
            color=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
            offset=ft.Offset(0, 8),
        ),
    )

    def apply_portfolio_summary(portfolio_data: dict):
        level_name, level_color, _level_icon = get_user_level(portfolio_data['total_usd'])
        level_chip_text.value = level_name
        level_chip.bgcolor = level_color
        total_value_text.value = f"${portfolio_data['total_usd']:,.2f}"
        assets_count_text.value = (
            str(len(portfolio_data['all_assets']))
        )
        stable_value = sum(
            asset['value_usd']
            for asset in portfolio_data['all_assets']
            if asset['currency'].upper() in ('USDT', 'USDC', 'BUSD', 'DAI')
        )
        reserve_text.value = f"${stable_value:,.0f}"
        if any(
            exchange_data['status'] == 'loading'
            for exchange_data in portfolio_data['exchanges'].values()
        ):
            sync_status_text.value = "Часть данных обновляется"
            sync_status_text.color = WARNING_COLOR
            sync_status_chip.content.controls[0].color = WARNING_COLOR
            sync_status_chip.bgcolor = ft.colors.with_opacity(0.12, WARNING_COLOR)
            sync_status_chip.border = ft.border.all(
                1,
                ft.colors.with_opacity(0.25, WARNING_COLOR),
            )
        else:
            sync_status_text.value = "Синхронизация активна"
            sync_status_text.color = PRIMARY_COLOR
            sync_status_chip.content.controls[0].color = PRIMARY_COLOR
            sync_status_chip.bgcolor = ft.colors.with_opacity(0.12, PRIMARY_COLOR)
            sync_status_chip.border = ft.border.all(
                1,
                ft.colors.with_opacity(0.25, PRIMARY_COLOR),
            )

        last_update = portfolio_cache.get("timestamp") or datetime.now()
        update_time_text.value = (
            f"Обновлено: {last_update.strftime('%H:%M:%S')}"
        )
    
    # ============ HEADER ============
    header = ft.Container(
        content=ft.Container(
            content=ft.Row([
                profile_panel,
                ft.Container(width=14),
                header_divider,
                ft.Container(width=14),
                value_panel,
                ft.Container(width=14),
                header_divider,
                ft.Container(width=14),
                ft.Container(
                    width=290,
                    content=ft.Column([
                        ft.Row([
                            create_info_cell(
                                "БИРЖИ",
                                connected_exchanges_text,
                                PRIMARY_COLOR,
                            ),
                            create_info_cell(
                                "АКТИВЫ",
                                assets_count_text,
                                SECONDARY_COLOR,
                            ),
                        ], spacing=8),
                        ft.Row([
                            create_info_cell(
                                "РЕЗЕРВ",
                                reserve_text,
                                WARNING_COLOR,
                            ),
                        ], spacing=8),
                    ], spacing=8),
                ),
            ], spacing=0, vertical_alignment="center"),
            padding=12,
            border_radius=22,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=["#151a25", "#0f141d", "#0b1017"],
            ),
            border=ft.border.all(
                1,
                ft.colors.with_opacity(0.62, BORDER_COLOR),
            ),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=16,
                color=ft.colors.with_opacity(0.20, "#000000"),
                offset=ft.Offset(0, 8),
            ),
        ),
        height=150,
        padding=ft.padding.only(left=18, top=6, right=18, bottom=4),
        bgcolor=DARK_BG,
    )
    
    # ============ ВКЛАДКИ БИРЖ ============
    def create_exchange_tab(exchange_name: str, data: dict):
        """Создает вкладку для биржи"""
        color = EXCHANGE_COLORS.get(exchange_name, PRIMARY_COLOR)
        name = EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())
        # кнопки покупки/продажи — стили согласованы с trading.py
        BUY_COLOR = "#00C853"
        SELL_COLOR = "#FF5252"

        if data['status'] == 'loading':
            return ft.Container(
                content=ft.Column([
                    ft.ProgressRing(color=color, width=48, height=48),
                    ft.Container(height=10),
                    ft.Text(
                        f"Синхронизация данных {name}",
                        size=18,
                        color=color,
                    ),
                    ft.Text(
                        data.get('error', 'Ожидание данных из базы данных'),
                        size=14,
                        color=TEXT_SECONDARY,
                    ),
                ], alignment="center", horizontal_alignment="center"),
                expand=True,
                alignment=ft.alignment.center,
            )
        
        if data['status'] == 'error':
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.ERROR_OUTLINE, size=64, color=ACCENT_COLOR),
                    ft.Container(height=10),
                    ft.Text(f"Ошибка данных {name}", size=18, color=ACCENT_COLOR),
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
                                    content=ft.Icon(
                                        ft.icons.SHOW_CHART,
                                        size=18,
                                        color=PRIMARY_COLOR,
                                    ),
                                    width=36,
                                    height=36,
                                    border_radius=8,
                                    bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                                    alignment=ft.alignment.center,
                                    on_click=_make_slippage_handler(page, asset),
                                    ink=True,
                                    tooltip="Анализ проскальзывания",
                                ),
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
    
    def build_tabs(portfolio_data: dict):
        tabs = []
        tab_ids = ["all"]
        for exchange_name, data in portfolio_data['exchanges'].items():
            color = EXCHANGE_COLORS.get(exchange_name, PRIMARY_COLOR)
            name = EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())

            if data['status'] == 'success':
                status_icon = ft.icons.CHECK_CIRCLE
                status_color = SUCCESS_COLOR
            elif data['status'] == 'loading':
                status_icon = ft.icons.SYNC
                status_color = WARNING_COLOR
            else:
                status_icon = ft.icons.ERROR
                status_color = ACCENT_COLOR

            tabs.append(
                ft.Tab(
                    tab_content=ft.Row([
                        ft.Icon(status_icon, size=14, color=status_color),
                        ft.Text(name, color=color, weight="bold"),
                        ft.Text(
                            f"${data['total_usd']:,.0f}",
                            size=12,
                            color=TEXT_SECONDARY,
                        ) if data['status'] == 'success' else ft.Container(),
                    ], spacing=8),
                    content=create_exchange_tab(exchange_name, data),
                )
            )
            tab_ids.append(exchange_name)

        all_assets_content = ft.Column(spacing=8, scroll="adaptive", expand=True)
        tradable_all_assets = [
            asset for asset in portfolio_data['all_assets']
            if asset['currency'].upper() not in ('USDT', 'USDC', 'BUSD', 'DAI')
        ]

        for asset in tradable_all_assets:
            exchange_color = EXCHANGE_COLORS.get(asset['exchange'], PRIMARY_COLOR)
            all_assets_content.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text(
                                asset['currency'][:4],
                                size=12,
                                weight="bold",
                                color=DARK_BG,
                                text_align="center",
                            ),
                            width=45,
                            height=45,
                            border_radius=10,
                            bgcolor=exchange_color,
                            alignment=ft.alignment.center,
                        ),
                        ft.Column([
                            ft.Text(asset['currency'], size=16, weight="bold", color=TEXT_PRIMARY),
                            ft.Row([
                                ft.Container(
                                    content=ft.Text(
                                        EXCHANGE_NAMES.get(asset['exchange'], asset['exchange']),
                                        size=10,
                                        color=DARK_BG,
                                    ),
                                    bgcolor=exchange_color,
                                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                    border_radius=6,
                                ),
                                ft.Text(
                                    f"Кол-во: {asset['amount']:.6f}",
                                    size=11,
                                    color=TEXT_SECONDARY,
                                ),
                            ], spacing=8),
                        ], spacing=4, expand=True),
                        ft.Column([
                            ft.Text(f"${asset['value_usd']:.2f}", size=16, weight="bold", color=SUCCESS_COLOR),
                            ft.Text(f"${asset['price_usd']:.4f}", size=11, color=TEXT_SECONDARY),
                        ], spacing=2, horizontal_alignment="end"),
                        ft.Row([
                            ft.Container(
                                content=ft.Icon(
                                    ft.icons.SHOW_CHART,
                                    size=18,
                                    color=PRIMARY_COLOR,
                                ),
                                width=36,
                                height=36,
                                border_radius=8,
                                bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                                alignment=ft.alignment.center,
                                on_click=_make_slippage_handler(page, asset),
                                ink=True,
                                tooltip="Анализ проскальзывания",
                            ),
                            ft.Container(
                                content=ft.Icon(ft.icons.ARROW_DOWNWARD, size=18, color=DARK_BG),
                                width=36,
                                height=36,
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
                                width=36,
                                height=36,
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
                ft.Text(f"${portfolio_data['total_usd']:,.0f}", size=12, color=TEXT_SECONDARY),
            ], spacing=8),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.WALLET, size=24, color=PRIMARY_COLOR),
                            ft.Text("Все активы", size=20, weight="bold", color=PRIMARY_COLOR),
                            ft.Container(expand=True),
                            ft.Text(
                                f"Торгуемых: {len(tradable_all_assets)} активов",
                                size=14,
                                color=TEXT_SECONDARY,
                            ),
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
        return tabs, tab_ids
    
    tabs_container = ft.Tabs(
        tabs=[],
        animation_duration=300,
        expand=True,
        indicator_color=PRIMARY_COLOR,
        label_color=TEXT_PRIMARY,
        unselected_label_color=TEXT_SECONDARY,
    )

    portfolio_cache.setdefault("selected_tab_index", 0)
    portfolio_cache.setdefault("selected_tab_key", "all")
    portfolio_cache.setdefault("tabs_refreshing", False)
    portfolio_cache.setdefault("tab_ids", ["all"])

    def on_tabs_change(e):
        if portfolio_cache.get("tabs_refreshing"):
            return

        selected_index = e.control.selected_index or 0
        portfolio_cache["selected_tab_index"] = selected_index
        tab_ids = portfolio_cache.get("tab_ids", ["all"])
        if 0 <= selected_index < len(tab_ids):
            portfolio_cache["selected_tab_key"] = tab_ids[selected_index]

    tabs_container.on_change = on_tabs_change
    
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

    def render_portfolio(portfolio_data: dict):
        apply_portfolio_summary(portfolio_data)
        selected_key = portfolio_cache.get("selected_tab_key", "all")
        tabs, tab_ids = build_tabs(portfolio_data)
        tabs_container.tabs = tabs
        portfolio_cache["tab_ids"] = tab_ids
        selected_index = 0

        for index, tab_id in enumerate(tab_ids):
            if tab_id == selected_key:
                selected_index = index
                break

        if tabs_container.tabs:
            portfolio_cache["tabs_refreshing"] = True
            tabs_container.selected_index = selected_index
            portfolio_cache["selected_tab_index"] = selected_index
            portfolio_cache["selected_tab_key"] = tab_ids[selected_index]
        page.update()
        portfolio_cache["tabs_refreshing"] = False

    render_portfolio(portfolio)
    page.update()
    
    # Автообновление каждые 10 секунд только из БД
    def auto_refresh():
        import time
        time.sleep(10)
        while current_user["user"] is not None:
            try:
                user_keys_refresh = session.query(ExchangeAPIKey).filter_by(user_id=current_user["user"].id, is_active=True).all()
                if user_keys_refresh:
                    portfolio_new = fetch_user_portfolio(user_keys_refresh)
                    portfolio_cache["data"] = portfolio_new
                    portfolio_cache["timestamp"] = datetime.now()
                    render_portfolio(portfolio_new)
                    logger.info(f"[OK] Портфель обновлён. Общая стоимость: ${portfolio_new['total_usd']:,.2f}")
            except Exception as e:
                logger.error(f"[ERROR] Ошибка обновления портфеля: {str(e)[:100]}")
            time.sleep(10)

    refresh_thread = portfolio_cache.get("refresh_thread")
    if not refresh_thread or not refresh_thread.is_alive():
        refresh_thread = threading.Thread(target=auto_refresh, daemon=True)
        refresh_thread.start()
        portfolio_cache["refresh_thread"] = refresh_thread
        logger.info("[START] Автообновление портфеля запущено (интервал: 10 сек)")
