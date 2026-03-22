import flet as ft

from ui.config import (
    ACCENT_COLOR,
    BORDER_COLOR,
    CARD_BG,
    DARK_BG,
    EXCHANGE_COLORS,
    EXCHANGE_NAMES,
    PRIMARY_COLOR,
    SUCCESS_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.slippage import show_slippage_analysis_dialog

STABLE_ASSETS = {'USDT', 'USDC', 'BUSD', 'DAI'}


def _make_trade_handler(show_trading_callback, asset=None, exchange_name=None, side=None):
    frozen_asset = dict(asset) if isinstance(asset, dict) else asset

    def handler(e):
        show_trading_callback(
            asset=frozen_asset,
            exchange_name=exchange_name,
            side=side,
        )

    return handler


def _make_slippage_handler(page, asset=None):
    frozen_asset = dict(asset) if isinstance(asset, dict) else asset

    def handler(e):
        show_slippage_analysis_dialog(page, frozen_asset)

    return handler


def show_assets_page(
    page: ft.Page,
    current_user: dict,
    portfolio_cache: dict,
    show_main_screen_callback,
    show_trading_callback,
):
    user = current_user.get('user')
    portfolio = portfolio_cache.get('data') or {}
    all_assets = portfolio.get('all_assets') or []

    filter_state = {'value': 'all'}
    filter_buttons = {}
    asset_list = ft.Column(spacing=10, scroll='adaptive', expand=True)
    active_filter_label = ft.Text('Все активы', size=12, color=TEXT_SECONDARY)
    total_assets_value = ft.Text('0', size=22, weight='bold', color=TEXT_PRIMARY)
    visible_volume_value = ft.Text('$0.00', size=22, weight='bold', color=SUCCESS_COLOR)

    page.controls.clear()

    def build_asset_card(asset):
        exchange_name = asset.get('exchange')
        exchange_color = EXCHANGE_COLORS.get(exchange_name, PRIMARY_COLOR)
        currency = asset.get('currency', '')
        available_actions = currency.upper() not in STABLE_ASSETS

        action_controls = []
        if available_actions:
            action_controls = [
                ft.Container(
                    content=ft.Icon(
                        ft.icons.SHOW_CHART,
                        size=18,
                        color=PRIMARY_COLOR,
                    ),
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                    alignment=ft.alignment.center,
                    on_click=_make_slippage_handler(page, asset),
                    ink=True,
                    tooltip='Анализ ликвидности',
                ),
                ft.Container(
                    content=ft.Icon(
                        ft.icons.ARROW_DOWNWARD,
                        size=18,
                        color=DARK_BG,
                    ),
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor=SUCCESS_COLOR,
                    alignment=ft.alignment.center,
                    on_click=_make_trade_handler(
                        show_trading_callback,
                        asset=asset,
                        exchange_name=exchange_name,
                        side='buy',
                    ),
                    ink=True,
                    tooltip='Купить',
                ),
                ft.Container(
                    content=ft.Icon(
                        ft.icons.ARROW_UPWARD,
                        size=18,
                        color=DARK_BG,
                    ),
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor=ACCENT_COLOR,
                    alignment=ft.alignment.center,
                    on_click=_make_trade_handler(
                        show_trading_callback,
                        asset=asset,
                        exchange_name=exchange_name,
                        side='sell',
                    ),
                    ink=True,
                    tooltip='Продать',
                ),
            ]

        return ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=CARD_BG,
            border=ft.border.all(1, BORDER_COLOR),
            content=ft.Row([
                ft.Container(
                    width=48,
                    height=48,
                    border_radius=12,
                    bgcolor=exchange_color,
                    alignment=ft.alignment.center,
                    content=ft.Text(
                        currency[:4],
                        size=12,
                        weight='bold',
                        color=DARK_BG,
                    ),
                ),
                ft.Container(width=14),
                ft.Column([
                    ft.Row([
                        ft.Text(
                            currency,
                            size=16,
                            weight='bold',
                            color=TEXT_PRIMARY,
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border_radius=999,
                            bgcolor=ft.colors.with_opacity(0.16, exchange_color),
                            content=ft.Text(
                                EXCHANGE_NAMES.get(exchange_name, exchange_name),
                                size=10,
                                weight='bold',
                                color=exchange_color,
                            ),
                        ),
                    ], spacing=8),
                    ft.Text(
                        f"Кол-во: {asset.get('amount', 0.0):.6f}",
                        size=11,
                        color=TEXT_SECONDARY,
                    ),
                ], spacing=4, expand=True),
                ft.Column([
                    ft.Text(
                        f"${asset.get('value_usd', 0.0):,.2f}",
                        size=17,
                        weight='bold',
                        color=SUCCESS_COLOR,
                    ),
                    ft.Text(
                        f"${asset.get('price_usd', 0.0):,.4f}",
                        size=11,
                        color=TEXT_SECONDARY,
                    ),
                ], spacing=4, horizontal_alignment='end'),
                ft.Container(width=12),
                ft.Row(action_controls, spacing=6),
            ], vertical_alignment='center'),
        )

    def get_filtered_assets():
        filter_value = filter_state['value']
        if filter_value == 'all':
            return all_assets
        return [
            asset for asset in all_assets
            if asset.get('exchange') == filter_value
        ]

    def update_filter_buttons():
        for filter_name, control in filter_buttons.items():
            active = filter_name == filter_state['value']
            accent = PRIMARY_COLOR if active else BORDER_COLOR
            control.bgcolor = (
                ft.colors.with_opacity(0.16, PRIMARY_COLOR)
                if active else ft.colors.with_opacity(0.06, '#ffffff')
            )
            control.border = ft.border.all(1, accent)
            control.content.controls[0].color = PRIMARY_COLOR if active else TEXT_SECONDARY
            control.content.controls[1].color = TEXT_PRIMARY if active else TEXT_SECONDARY

    def apply_filter(filter_name):
        filter_state['value'] = filter_name
        visible_assets = get_filtered_assets()
        asset_list.controls = []

        if filter_name == 'all':
            active_filter_label.value = 'Все активы'
        else:
            active_filter_label.value = EXCHANGE_NAMES.get(filter_name, filter_name)

        total_assets_value.value = str(len(visible_assets))
        visible_volume_value.value = (
            f"${sum(asset.get('value_usd', 0.0) for asset in visible_assets):,.2f}"
        )

        if visible_assets:
            asset_list.controls = [build_asset_card(asset) for asset in visible_assets]
        else:
            asset_list.controls = [
                ft.Container(
                    padding=30,
                    border_radius=16,
                    bgcolor=CARD_BG,
                    border=ft.border.all(1, BORDER_COLOR),
                    content=ft.Column([
                        ft.Icon(ft.icons.SAVINGS, size=46, color=TEXT_SECONDARY),
                        ft.Container(height=10),
                        ft.Text(
                            'Нет активов для выбранного фильтра',
                            size=16,
                            color=TEXT_SECONDARY,
                        ),
                    ], horizontal_alignment='center'),
                )
            ]

        update_filter_buttons()
        page.update()

    def create_filter_button(filter_name, title, accent_color):
        button = ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            border_radius=999,
            border=ft.border.all(1, BORDER_COLOR),
            bgcolor=ft.colors.with_opacity(0.06, '#ffffff'),
            ink=True,
            on_click=lambda e, current=filter_name: apply_filter(current),
            content=ft.Row([
                ft.Container(
                    width=8,
                    height=8,
                    border_radius=999,
                    bgcolor=accent_color,
                ),
                ft.Text(title, size=12, weight='bold', color=TEXT_SECONDARY),
            ], spacing=8),
        )
        filter_buttons[filter_name] = button
        return button

    header = ft.Container(
        padding=20,
        bgcolor=CARD_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR)),
        content=ft.Row([
            ft.IconButton(
                icon=ft.icons.ARROW_BACK,
                icon_color=TEXT_PRIMARY,
                tooltip='Назад',
                on_click=lambda e: show_main_screen_callback(),
            ),
            ft.Column([
                ft.Text(
                    'Все активы портфеля',
                    size=24,
                    weight='bold',
                    color=TEXT_PRIMARY,
                ),
                ft.Text(
                    f"{user.name if user else 'Пользователь'} • полный состав активов по всем биржам",
                    size=12,
                    color=TEXT_SECONDARY,
                ),
            ], spacing=4),
            ft.Container(expand=True),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
                border_radius=999,
                bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                content=ft.Text(
                    'Отдельный экран портфеля',
                    size=11,
                    color=PRIMARY_COLOR,
                    weight='bold',
                ),
            ),
        ], vertical_alignment='center'),
    )

    filters_row = ft.Row([
        create_filter_button('all', 'Все', PRIMARY_COLOR),
        create_filter_button('bybit', 'Bybit', EXCHANGE_COLORS.get('bybit', PRIMARY_COLOR)),
        create_filter_button('gateio', 'Gate.io', EXCHANGE_COLORS.get('gateio', PRIMARY_COLOR)),
        create_filter_button('mexc', 'MEXC', EXCHANGE_COLORS.get('mexc', PRIMARY_COLOR)),
    ], spacing=10, wrap=True)

    summary_strip = ft.Container(
        padding=18,
        border_radius=18,
        bgcolor=ft.colors.with_opacity(0.12, '#0d141d'),
        border=ft.border.all(1, ft.colors.with_opacity(0.38, BORDER_COLOR)),
        content=ft.Row([
            ft.Column([
                ft.Text('Фильтр', size=10, color=TEXT_SECONDARY),
                active_filter_label,
            ], spacing=4, expand=True),
            ft.Column([
                ft.Text('Активов', size=10, color=TEXT_SECONDARY),
                total_assets_value,
            ], spacing=4, horizontal_alignment='center'),
            ft.Container(width=24),
            ft.Column([
                ft.Text('Объём', size=10, color=TEXT_SECONDARY),
                visible_volume_value,
            ], spacing=4, horizontal_alignment='end'),
        ], vertical_alignment='center'),
    )

    page.add(
        ft.Column([
            header,
            ft.Container(
                expand=True,
                padding=20,
                content=ft.Column([
                    filters_row,
                    ft.Container(height=14),
                    summary_strip,
                    ft.Container(height=16),
                    asset_list,
                ], expand=True),
            ),
        ], expand=True, spacing=0)
    )

    apply_filter('all')
