import logging
from datetime import datetime

import flet as ft

from backend.api import fetch_user_portfolio
from backend.models import ExchangeAPIKey, session
from ui.config import (
    ACCENT_COLOR,
    BORDER_COLOR,
    CARD_BG,
    DARK_BG,
    EXCHANGE_COLORS,
    EXCHANGE_NAMES,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    SUCCESS_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
)
from ui.slippage import show_slippage_analysis_dialog

logger = logging.getLogger(__name__)

STABLE_ASSETS = {"USDT", "USDC", "BUSD", "DAI"}
FILTER_ORDER = ("all", "bybit", "gateio", "mexc")


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _format_money(value):
    return f"${_to_float(value):,.2f}"


def _format_amount(value):
    amount = _to_float(value)
    if amount >= 1000:
        return f"{amount:,.2f}"
    if amount >= 1:
        return f"{amount:,.4f}"
    return f"{amount:,.6f}"


def _normalize_exchange_name(value):
    raw = str(value or "").strip().lower()
    aliases = {
        "gate.io": "gateio",
        "gate_io": "gateio",
        "gate-io": "gateio",
    }
    return aliases.get(raw, raw)


def _exchange_label(value):
    normalized = _normalize_exchange_name(value)
    return EXCHANGE_NAMES.get(normalized, str(value or "").upper() or "Unknown")


def _asset_key(asset):
    return (
        _normalize_exchange_name(asset.get("exchange")),
        str(asset.get("currency", "")).upper(),
    )


def _get_asset_price_usd(asset):
    return _to_float(
        asset.get("price_usd")
        or asset.get("price")
        or asset.get("usd_price")
        or 0.0
    )


def _get_asset_value_usd(asset):
    direct = _to_float(
        asset.get("value_usd")
        or asset.get("usd_value")
        or asset.get("value")
        or 0.0
    )
    if direct > 0:
        return direct
    return _to_float(asset.get("amount")) * _get_asset_price_usd(asset)


def _is_tradable(asset):
    return str(asset.get("currency", "")).upper() not in STABLE_ASSETS


def _show_snack(page: ft.Page, message: str, color: str):
    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color=TEXT_PRIMARY),
        bgcolor=color,
    )
    page.snack_bar.open = True


def _get_user_keys(user_id):
    return session.query(ExchangeAPIKey).filter_by(
        user_id=user_id,
        is_active=True,
    ).all()


def _format_timestamp(value):
    if not value:
        return "Нет данных"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y %H:%M:%S")
    return str(value)


def show_assets_page(
    page: ft.Page,
    current_user: dict,
    portfolio_cache: dict,
    show_main_screen_callback,
    show_trading_callback,
    show_trades_history_callback,
    show_portfolio_risk_callback=None,
):
    user = current_user.get("user")
    if not user:
        logger.warning("[ASSETS] Open page aborted: missing current user")
        show_main_screen_callback()
        return

    logger.info("[ASSETS] Open page for user=%s", user.name)

    if not portfolio_cache.get("data"):
        try:
            user_keys = _get_user_keys(user.id)
            portfolio_cache["data"] = fetch_user_portfolio(user_keys)
            portfolio_cache["timestamp"] = datetime.now()
        except Exception:
            logger.exception("[ASSETS] Failed to warm portfolio cache")
            portfolio_cache["data"] = {
                "total_usd": 0.0,
                "all_assets": [],
                "exchanges": {},
            }

    state = {
        "filter": "all",
        "selected_key": None,
        "portfolio": portfolio_cache.get("data") or {},
        "all_assets": list((portfolio_cache.get("data") or {}).get("all_assets") or []),
    }

    page.controls.clear()

    filter_buttons = {}
    asset_stream = ft.Column(spacing=12, scroll="adaptive", expand=True)

    hero_title = ft.Text("Активы портфеля", size=28, weight="bold", color=TEXT_PRIMARY)
    hero_subtitle = ft.Text("", size=12, color=TEXT_SECONDARY)
    total_portfolio_value = ft.Text("$0.00", size=24, weight="bold", color=SUCCESS_COLOR)
    visible_filter_name = ft.Text("Все биржи", size=13, weight="bold", color=TEXT_PRIMARY)
    visible_assets_count = ft.Text("0", size=20, weight="bold", color=TEXT_PRIMARY)
    visible_assets_volume = ft.Text("$0.00", size=20, weight="bold", color=SUCCESS_COLOR)
    connected_exchanges_value = ft.Text("0", size=18, weight="bold", color=TEXT_PRIMARY)
    updated_time_text = ft.Text("Нет данных", size=11, color=TEXT_SECONDARY)
    selected_asset_title = ft.Text("Актив не выбран", size=18, weight="bold", color=TEXT_PRIMARY)
    selected_asset_meta = ft.Text(
        "Выбери карточку справа, чтобы использовать отдельные кнопки покупки и продажи",
        size=11,
        color=TEXT_SECONDARY,
    )
    selected_asset_value = ft.Text("$0.00", size=18, weight="bold", color=SUCCESS_COLOR)
    stream_caption = ft.Text("Поток активов", size=12, weight="bold", color=TEXT_SECONDARY)
    stream_summary = ft.Text("", size=12, color=TEXT_SECONDARY)

    buy_button = ft.ElevatedButton(
        "Купить",
        icon=ft.icons.ARROW_DOWNWARD_ROUNDED,
        disabled=True,
        style=ft.ButtonStyle(
            bgcolor={
                ft.MaterialState.DEFAULT: SUCCESS_COLOR,
                ft.MaterialState.DISABLED: CARD_BG,
            },
            color={
                ft.MaterialState.DEFAULT: DARK_BG,
                ft.MaterialState.DISABLED: TEXT_SECONDARY,
            },
            padding=ft.padding.symmetric(horizontal=18, vertical=16),
            shape=ft.RoundedRectangleBorder(radius=14),
        ),
    )
    sell_button = ft.ElevatedButton(
        "Продать",
        icon=ft.icons.ARROW_UPWARD_ROUNDED,
        disabled=True,
        style=ft.ButtonStyle(
            bgcolor={
                ft.MaterialState.DEFAULT: ACCENT_COLOR,
                ft.MaterialState.DISABLED: CARD_BG,
            },
            color={
                ft.MaterialState.DEFAULT: DARK_BG,
                ft.MaterialState.DISABLED: TEXT_SECONDARY,
            },
            padding=ft.padding.symmetric(horizontal=18, vertical=16),
            shape=ft.RoundedRectangleBorder(radius=14),
        ),
    )
    refresh_button = ft.ElevatedButton(
        "Обновить данные",
        icon=ft.icons.REFRESH_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=PRIMARY_COLOR,
            color=DARK_BG,
            padding=ft.padding.symmetric(horizontal=18, vertical=16),
            shape=ft.RoundedRectangleBorder(radius=14),
        ),
    )
    
    trades_history_button = ft.ElevatedButton(
        "История сделок",
        icon=ft.icons.HISTORY_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=SECONDARY_COLOR,
            color=DARK_BG,
            padding=ft.padding.symmetric(horizontal=25, vertical=16),
            shape=ft.RoundedRectangleBorder(radius=14),
        ),
    )

    def _get_visible_assets():
        current_filter = state["filter"]
        if current_filter == "all":
            return list(state["all_assets"])
        return [
            asset
            for asset in state["all_assets"]
            if _normalize_exchange_name(asset.get("exchange")) == current_filter
        ]

    def _get_selected_asset():
        selected_key = state["selected_key"]
        if not selected_key:
            return None
        for asset in state["all_assets"]:
            if _asset_key(asset) == selected_key:
                return asset
        return None

    def _refresh_selection():
        if state["selected_key"] is None:
            return
        if _get_selected_asset() is None:
            logger.info("[ASSETS] Selected asset dropped after refresh")
            state["selected_key"] = None

    def _open_trading(side):
        asset = _get_selected_asset()
        if not asset:
            _show_snack(page, "Сначала выбери актив", ACCENT_COLOR)
            page.update()
            return
        if not _is_tradable(asset):
            _show_snack(page, "Для стейблкоинов торговля с этой панели недоступна", WARNING_COLOR)
            page.update()
            return

        exchange_name = _normalize_exchange_name(asset.get("exchange"))
        logger.info(
            "[ASSETS] Toolbar trade side=%s asset=%s exchange=%s",
            side,
            asset.get("currency"),
            exchange_name,
        )
        show_trading_callback(
            asset=dict(asset),
            exchange_name=exchange_name,
            side=side,
        )

    def _open_slippage(asset):
        frozen_asset = dict(asset)
        logger.info(
            "[ASSETS] Slippage click asset=%s exchange=%s",
            frozen_asset.get("currency"),
            _normalize_exchange_name(frozen_asset.get("exchange")),
        )
        show_slippage_analysis_dialog(page, frozen_asset)

    def _apply_filter(filter_name):
        state["filter"] = filter_name
        logger.info("[ASSETS] Apply filter=%s", filter_name)
        _render_state()

    def _select_asset(asset):
        state["selected_key"] = _asset_key(asset)
        logger.info(
            "[ASSETS] Select asset=%s exchange=%s",
            asset.get("currency"),
            _normalize_exchange_name(asset.get("exchange")),
        )
        _render_state()

    def _refresh_portfolio(_):
        logger.info("[ASSETS] Manual refresh requested")
        refresh_button.disabled = True
        refresh_button.text = "Обновление..."
        page.update()

        try:
            user_keys = _get_user_keys(user.id)
            portfolio = fetch_user_portfolio(user_keys)
            portfolio_cache["data"] = portfolio
            portfolio_cache["timestamp"] = datetime.now()
            state["portfolio"] = portfolio
            state["all_assets"] = list(portfolio.get("all_assets") or [])
            _refresh_selection()
            logger.info(
                "[ASSETS] Refresh success total=%s assets=%s",
                _format_money(portfolio.get("total_usd", 0.0)),
                len(state["all_assets"]),
            )
            _show_snack(page, "Данные портфеля обновлены из базы данных", SUCCESS_COLOR)
        except Exception:
            logger.exception("[ASSETS] Refresh failed")
            _show_snack(page, "Не удалось обновить данные портфеля", ACCENT_COLOR)
        finally:
            refresh_button.disabled = False
            refresh_button.text = "Обновить данные"
            _render_state()

    buy_button.on_click = lambda e: _open_trading("buy")
    sell_button.on_click = lambda e: _open_trading("sell")
    refresh_button.on_click = _refresh_portfolio
    trades_history_button.on_click = lambda e: show_trades_history_callback()

    def _build_filter_button(filter_name, title, color):
        button_title = ft.Text(title, size=13, weight="bold", color=TEXT_SECONDARY)
        button_stats = ft.Text("$0.00", size=10, color=TEXT_SECONDARY)
        button_count = ft.Text("0 активов", size=10, color=TEXT_SECONDARY)
        control = ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            border_radius=16,
            bgcolor=CARD_BG,
            border=ft.border.all(1, BORDER_COLOR),
            ink=True,
            on_click=lambda e, current=filter_name: _apply_filter(current),
            content=ft.Row([
                ft.Container(
                    width=10,
                    height=42,
                    border_radius=999,
                    bgcolor=color,
                ),
                ft.Container(width=10),
                ft.Column([
                    button_title,
                    button_count,
                ], spacing=2, expand=True),
                ft.Column([
                    ft.Text("Объем", size=9, color=TEXT_SECONDARY),
                    button_stats,
                ], spacing=2, horizontal_alignment="end"),
            ], spacing=0, vertical_alignment="center"),
        )
        filter_buttons[filter_name] = {
            "control": control,
            "title": button_title,
            "stats": button_stats,
            "count": button_count,
        }
        return control

    def _build_stat_card(title, value_control, accent_color):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            border_radius=18,
            bgcolor=CARD_BG,
            border=ft.border.all(1, BORDER_COLOR),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=999,
                        bgcolor=accent_color,
                    ),
                    ft.Text(title, size=10, weight="bold", color=TEXT_SECONDARY),
                ], spacing=8),
                ft.Container(height=8),
                value_control,
            ], spacing=0),
        )

    def _build_asset_card(asset):
        exchange_name = _normalize_exchange_name(asset.get("exchange"))
        exchange_color = EXCHANGE_COLORS.get(exchange_name, PRIMARY_COLOR)
        currency = str(asset.get("currency", "")).upper() or "?"
        amount = _format_amount(asset.get("amount"))
        price = _format_money(_get_asset_price_usd(asset))
        value = _format_money(_get_asset_value_usd(asset))
        is_selected = state["selected_key"] == _asset_key(asset)
        is_tradable = _is_tradable(asset)

        return ft.Container(
            padding=16,
            border_radius=18,
            bgcolor=CARD_BG,
            border=ft.border.all(1, PRIMARY_COLOR if is_selected else BORDER_COLOR),
            content=ft.Row([
                ft.Container(
                    width=54,
                    height=54,
                    border_radius=16,
                    bgcolor=exchange_color,
                    alignment=ft.alignment.center,
                    content=ft.Text(
                        currency[:4],
                        size=13,
                        weight="bold",
                        color=DARK_BG,
                    ),
                ),
                ft.Container(width=14),
                ft.Column([
                    ft.Row([
                        ft.Text(currency, size=18, weight="bold", color=TEXT_PRIMARY),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            border_radius=999,
                            bgcolor=ft.colors.with_opacity(0.16, exchange_color),
                            content=ft.Text(
                                _exchange_label(exchange_name),
                                size=10,
                                weight="bold",
                                color=exchange_color,
                            ),
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=10, vertical=4),
                            border_radius=999,
                            bgcolor=ft.colors.with_opacity(
                                0.12,
                                SUCCESS_COLOR if is_tradable else WARNING_COLOR,
                            ),
                            content=ft.Text(
                                "Торгуется" if is_tradable else "Стейбл",
                                size=10,
                                weight="bold",
                                color=SUCCESS_COLOR if is_tradable else WARNING_COLOR,
                            ),
                        ),
                    ], spacing=8, wrap=True),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Text("Количество", size=10, color=TEXT_SECONDARY),
                        ft.Text(amount, size=12, weight="bold", color=TEXT_PRIMARY),
                        ft.Container(width=16),
                        ft.Text("Цена", size=10, color=TEXT_SECONDARY),
                        ft.Text(price, size=12, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=6, wrap=True),
                ], spacing=0, expand=True),
                ft.Container(width=14),
                ft.Column([
                    ft.Text("Стоимость", size=10, color=TEXT_SECONDARY),
                    ft.Text(value, size=18, weight="bold", color=SUCCESS_COLOR),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=10, vertical=8),
                            border_radius=12,
                            bgcolor=ft.colors.with_opacity(
                                0.16 if is_selected else 0.08,
                                PRIMARY_COLOR,
                            ),
                            border=ft.border.all(
                                1,
                                PRIMARY_COLOR if is_selected else BORDER_COLOR,
                            ),
                            ink=True,
                            on_click=lambda e, current=dict(asset): _select_asset(current),
                            content=ft.Text(
                                "Выбран" if is_selected else "Выбрать",
                                size=11,
                                weight="bold",
                                color=PRIMARY_COLOR if is_selected else TEXT_SECONDARY,
                            ),
                        ),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=12, vertical=8),
                            border_radius=12,
                            bgcolor=ft.colors.with_opacity(0.10, PRIMARY_COLOR),
                            border=ft.border.all(
                                1,
                                ft.colors.with_opacity(0.24, PRIMARY_COLOR),
                            ),
                            ink=True,
                            on_click=lambda e, current=dict(asset): _open_slippage(current),
                            content=ft.Row([
                                ft.Icon(
                                    ft.icons.SHOW_CHART_ROUNDED,
                                    size=16,
                                    color=PRIMARY_COLOR,
                                ),
                                ft.Text(
                                    "Ликвидность",
                                    size=11,
                                    weight="bold",
                                    color=PRIMARY_COLOR,
                                ),
                            ], spacing=6),
                        ),
                    ], spacing=8, wrap=True),
                ], spacing=0, horizontal_alignment="end"),
            ], spacing=0, vertical_alignment="center"),
        )

    def _update_filter_button_states():
        all_assets = list(state["all_assets"])
        totals = {}
        for filter_name in FILTER_ORDER:
            if filter_name == "all":
                assets = all_assets
            else:
                assets = [
                    asset
                    for asset in all_assets
                    if _normalize_exchange_name(asset.get("exchange")) == filter_name
                ]
            totals[filter_name] = {
                "count": len(assets),
                "volume": sum(_get_asset_value_usd(asset) for asset in assets),
            }

        for filter_name, controls in filter_buttons.items():
            active = filter_name == state["filter"]
            controls["count"].value = f"{totals[filter_name]['count']} активов"
            controls["stats"].value = _format_money(totals[filter_name]["volume"])
            controls["control"].bgcolor = (
                ft.colors.with_opacity(0.14, PRIMARY_COLOR) if active else CARD_BG
            )
            controls["control"].border = ft.border.all(
                1,
                PRIMARY_COLOR if active else BORDER_COLOR,
            )
            controls["title"].color = TEXT_PRIMARY if active else TEXT_SECONDARY

    def _render_state():
        visible_assets = _get_visible_assets()
        _refresh_selection()
        selected_asset = _get_selected_asset()
        portfolio = state["portfolio"] or {}
        cache_time = portfolio_cache.get("timestamp") or portfolio.get("timestamp")
        connected_exchanges = [
            name
            for name, data in (portfolio.get("exchanges") or {}).items()
            if isinstance(data, dict)
        ]

        total_portfolio_value.value = _format_money(portfolio.get("total_usd", 0.0))
        visible_filter_name.value = (
            "Все биржи"
            if state["filter"] == "all"
            else _exchange_label(state["filter"])
        )
        visible_assets_count.value = str(len(visible_assets))
        visible_assets_volume.value = _format_money(
            sum(_get_asset_value_usd(asset) for asset in visible_assets)
        )
        connected_exchanges_value.value = str(len(connected_exchanges))
        updated_time_text.value = _format_timestamp(cache_time)
        hero_subtitle.value = f"{user.name} • единый реестр активов по подключенным биржам"
        stream_summary.value = (
            f"{visible_filter_name.value} • {len(visible_assets)} поз. • "
            f"{visible_assets_volume.value}"
        )

        if selected_asset:
            exchange_name = _normalize_exchange_name(selected_asset.get("exchange"))
            selected_asset_title.value = str(selected_asset.get("currency", "")).upper()
            selected_asset_meta.value = (
                f"{_exchange_label(exchange_name)} • "
                f"количество {_format_amount(selected_asset.get('amount'))}"
            )
            selected_asset_value.value = _format_money(_get_asset_value_usd(selected_asset))
            tradable = _is_tradable(selected_asset)
            buy_button.disabled = not tradable
            sell_button.disabled = not tradable
        else:
            selected_asset_title.value = "Актив не выбран"
            selected_asset_meta.value = (
                "Выбери карточку справа, чтобы использовать отдельные кнопки покупки и продажи"
            )
            selected_asset_value.value = "$0.00"
            buy_button.disabled = True
            sell_button.disabled = True

        asset_stream.controls.clear()
        if visible_assets:
            for asset in visible_assets:
                asset_stream.controls.append(_build_asset_card(asset))
        else:
            asset_stream.controls.append(
                ft.Container(
                    padding=32,
                    border_radius=18,
                    bgcolor=CARD_BG,
                    border=ft.border.all(1, BORDER_COLOR),
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(
                            ft.icons.SAVINGS_OUTLINED,
                            size=48,
                            color=TEXT_SECONDARY,
                        ),
                        ft.Container(height=8),
                        ft.Text(
                            "По выбранной бирже пока нет активов",
                            size=16,
                            weight="bold",
                            color=TEXT_PRIMARY,
                        ),
                        ft.Text(
                            "Попробуй переключить фильтр или обновить данные из базы",
                            size=11,
                            color=TEXT_SECONDARY,
                        ),
                    ], spacing=4, horizontal_alignment="center"),
                )
            )

        logger.info(
            "[ASSETS] Render filter=%s visible=%s total=%s selected=%s",
            state["filter"],
            len(visible_assets),
            visible_assets_volume.value,
            selected_asset_title.value,
        )
        _update_filter_button_states()
        page.update()

    navigator = ft.Container(
        width=310,
        padding=18,
        border_radius=22,
        bgcolor="#0d1118",
        border=ft.border.all(1, BORDER_COLOR),
        content=ft.Column([
            ft.Row([
                ft.IconButton(
                    icon=ft.icons.ARROW_BACK_ROUNDED,
                    icon_color=TEXT_PRIMARY,
                    tooltip="Назад",
                    on_click=lambda e: show_main_screen_callback(),
                ),
                ft.Column([
                    ft.Text("Navigator", size=10, weight="bold", color=TEXT_SECONDARY),
                    ft.Text("Управление активами", size=17, weight="bold", color=TEXT_PRIMARY),
                ], spacing=2),
            ], spacing=8),
            ft.Container(height=12),
            ft.Container(
                padding=18,
                border_radius=20,
                bgcolor=CARD_BG,
                border=ft.border.all(1, BORDER_COLOR),
                content=ft.Column([
                    ft.Text("Консолидированный объем", size=10, weight="bold", color=TEXT_SECONDARY),
                    ft.Container(height=6),
                    total_portfolio_value,
                    ft.Container(height=6),
                    ft.Text(
                        "Сводка по всем подключенным биржам в локальной базе данных",
                        size=11,
                        color=TEXT_SECONDARY,
                    ),
                ], spacing=0),
            ),
            ft.Container(height=12),
            ft.Text("Биржи", size=11, weight="bold", color=TEXT_SECONDARY),
            ft.Container(height=8),
            ft.Column([
                _build_filter_button("all", "Все биржи", PRIMARY_COLOR),
                _build_filter_button(
                    "bybit",
                    "Bybit",
                    EXCHANGE_COLORS.get("bybit", PRIMARY_COLOR),
                ),
                _build_filter_button(
                    "gateio",
                    "Gate.io",
                    EXCHANGE_COLORS.get("gateio", PRIMARY_COLOR),
                ),
                _build_filter_button(
                    "mexc",
                    "MEXC",
                    EXCHANGE_COLORS.get("mexc", PRIMARY_COLOR),
                ),
            ], spacing=10),
            ft.Container(height=12),
            ft.Container(
                padding=14,
                border_radius=18,
                bgcolor=CARD_BG,
                border=ft.border.all(1, BORDER_COLOR),
                content=ft.Column([
                    ft.Text("Последнее обновление", size=10, weight="bold", color=TEXT_SECONDARY),
                    ft.Container(height=4),
                    updated_time_text,
                    ft.Container(height=12),
                    refresh_button,
                    ft.Container(height=10),
                    trades_history_button,
                ], spacing=0),
            ),
        ], spacing=0),
    )

    action_panel = ft.Container(
        padding=18,
        border_radius=22,
        bgcolor="#0d1118",
        border=ft.border.all(1, BORDER_COLOR),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    hero_title,
                    hero_subtitle,
                ], spacing=4, expand=True),
            ], vertical_alignment="center"),
            ft.Container(height=16),
            ft.Container(
                padding=16,
                border_radius=18,
                bgcolor=CARD_BG,
                border=ft.border.all(1, BORDER_COLOR),
                content=ft.Row([
                    ft.Column([
                        ft.Text("Выбранный актив", size=10, weight="bold", color=TEXT_SECONDARY),
                        ft.Container(height=4),
                        selected_asset_title,
                        ft.Container(height=4),
                        selected_asset_meta,
                    ], spacing=0, expand=True),
                    ft.Container(width=16),
                    ft.Column([
                        ft.Text("Текущая стоимость", size=10, weight="bold", color=TEXT_SECONDARY),
                        ft.Container(height=4),
                        selected_asset_value,
                    ], spacing=0),
                    ft.Container(width=18),
                    ft.Row([
                        buy_button,
                        sell_button,
                    ], spacing=10),
                ], spacing=0, vertical_alignment="center"),
            ),
        ], spacing=0),
    )

    stream_panel = ft.Container(
        expand=True,
        padding=18,
        border_radius=22,
        bgcolor="#0d1118",
        border=ft.border.all(1, BORDER_COLOR),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    stream_caption,
                    stream_summary,
                ], spacing=4),
            ]),
            ft.Container(height=14),
            ft.Container(
                expand=True,
                padding=2,
                bgcolor="#0d1118",
                content=asset_stream,
            ),
        ], spacing=0, expand=True),
    )

    page.add(
        ft.Column([
            ft.Container(
                padding=20,
                expand=True,
                content=ft.Row([
                    navigator,
                    ft.Container(width=18),
                    ft.Column([
                        action_panel,
                        ft.Container(height=18),
                        stream_panel,
                    ], expand=True, spacing=0),
                ], expand=True, spacing=0),
            ),
        ], expand=True, spacing=0)
    )

    _render_state()
