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
from backend.decision_quality_analyzer import (
    format_exchange_name,
    get_user_decision_quality_summary,
    get_user_trade_decision_history,
)
from backend.stress_sell_analyzer import analyze_portfolio_stress_sell

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
                     show_no_exchanges_callback, show_assets_page_callback):
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
    stress_nominal_text = ft.Text(
        "$0.00",
        size=20,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    stress_executable_text = ft.Text(
        "$0.00",
        size=20,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    stress_loss_text = ft.Text(
        "$0.00",
        size=20,
        weight="bold",
        color=ACCENT_COLOR,
    )
    stress_best_exit_text = ft.Text(
        "Нет данных",
        size=18,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    stress_top_loss_text = ft.Text(
        "Источник потерь появится после расчета",
        size=11,
        color=TEXT_SECONDARY,
    )
    stress_loss_hint_text = ft.Text(
        "Потери на ликвидации: 0.00%",
        size=11,
        color=TEXT_SECONDARY,
    )
    decision_quality_text = ft.Text(
        "0%",
        size=20,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    decision_loss_text = ft.Text(
        "$0.00",
        size=20,
        weight="bold",
        color=ACCENT_COLOR,
    )
    decision_month_loss_text = ft.Text(
        "$0.00",
        size=20,
        weight="bold",
        color=ACCENT_COLOR,
    )
    decision_worst_exchange_text = ft.Text(
        "Нет данных",
        size=18,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    decision_worst_buy_exchange_text = ft.Text(
        "Нет данных",
        size=18,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    decision_best_exchange_text = ft.Text(
        "Нет данных",
        size=18,
        weight="bold",
        color=TEXT_PRIMARY,
    )
    decision_best_price_rate_text = ft.Text(
        "0%",
        size=18,
        weight="bold",
        color=PRIMARY_COLOR,
    )
    decision_liquidity_rate_text = ft.Text(
        "0%",
        size=18,
        weight="bold",
        color=SECONDARY_COLOR,
    )
    decision_suboptimal_rate_text = ft.Text(
        "0%",
        size=18,
        weight="bold",
        color=WARNING_COLOR,
    )
    decision_hint_text = ft.Text(
        "История решений появится после сделок",
        size=11,
        color=TEXT_SECONDARY,
    )
    decision_history_caption_text = ft.Text(
        "Последние сделки будут видны после первых ордеров",
        size=11,
        color=TEXT_SECONDARY,
    )
    decision_history_rows = ft.Column(spacing=8, scroll="adaptive", expand=True)
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

    def create_stress_metric(title: str, value_control, subtitle: ft.Text, accent_color: str):
        return ft.Container(
            expand=True,
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            border_radius=16,
            bgcolor=ft.colors.with_opacity(0.14, "#0b1118"),
            border=ft.border.all(
                1,
                ft.colors.with_opacity(0.34, BORDER_COLOR),
            ),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=999,
                        bgcolor=accent_color,
                    ),
                    ft.Text(
                        title,
                        size=9,
                        weight="bold",
                        color=TEXT_SECONDARY,
                    ),
                ], spacing=8),
                ft.Container(height=8),
                value_control,
                ft.Container(height=4),
                subtitle,
            ], spacing=0),
        )

    def create_decision_signal(title: str, value_control, subtitle: str, accent_color: str):
        return ft.Container(
            expand=True,
            padding=ft.padding.symmetric(horizontal=16, vertical=14),
            border_radius=16,
            bgcolor=ft.colors.with_opacity(0.14, "#0b1118"),
            border=ft.border.all(
                1,
                ft.colors.with_opacity(0.30, BORDER_COLOR),
            ),
            content=ft.Row([
                ft.Container(
                    width=4,
                    border_radius=999,
                    bgcolor=accent_color,
                ),
                ft.Container(width=14),
                ft.Column([
                    ft.Text(
                        title,
                        size=10,
                        weight="bold",
                        color=TEXT_SECONDARY,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        subtitle,
                        size=10,
                        color=TEXT_SECONDARY,
                    ),
                ], spacing=0, expand=True, alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(width=16),
                ft.Container(
                    width=92,
                    height=52,
                    border_radius=14,
                    bgcolor=ft.colors.with_opacity(0.10, accent_color),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.24, accent_color),
                    ),
                    alignment=ft.alignment.center,
                    content=value_control,
                ),
            ], spacing=0, vertical_alignment="center"),
        )

    def create_decision_history_row(row_data: dict):
        status_positive = row_data.get('avoidable_loss', 0.0) <= 0.01
        status_color = SUCCESS_COLOR if status_positive else ACCENT_COLOR
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            border_radius=16,
            bgcolor=ft.colors.with_opacity(0.14, "#0a1117"),
            border=ft.border.all(
                1,
                ft.colors.with_opacity(0.28, BORDER_COLOR),
            ),
            content=ft.Row([
                ft.Container(
                    width=86,
                    content=ft.Column([
                        ft.Text(
                            row_data.get('symbol', '---'),
                            size=13,
                            weight="bold",
                            color=TEXT_PRIMARY,
                        ),
                        ft.Text(
                            row_data.get('side_label', 'Сделка'),
                            size=10,
                            color=TEXT_SECONDARY,
                        ),
                    ], spacing=2),
                ),
                ft.Container(width=12),
                ft.Container(
                    width=170,
                    content=ft.Column([
                        ft.Text(
                            f"{row_data.get('actual_exchange', 'Нет данных')} -> "
                            f"{row_data.get('best_exchange', 'Нет данных')}",
                            size=11,
                            color=TEXT_PRIMARY,
                        ),
                        ft.Text(
                            f"Цена {row_data.get('actual_price', 0.0):,.4f} | "
                            f"лучшая {row_data.get('best_possible_price', 0.0):,.4f}",
                            size=10,
                            color=TEXT_SECONDARY,
                        ),
                    ], spacing=2),
                ),
                ft.Container(width=12),
                ft.Container(
                    width=130,
                    content=ft.Column([
                        ft.Text(
                            f"Потери ${row_data.get('avoidable_loss', 0.0):,.2f}",
                            size=11,
                            weight="bold",
                            color=status_color,
                        ),
                        ft.Text(
                            f"Качество {row_data.get('execution_quality_score', 0.0):.0f}%",
                            size=10,
                            color=TEXT_SECONDARY,
                        ),
                    ], spacing=2),
                ),
                ft.Container(expand=True),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=999,
                    bgcolor=ft.colors.with_opacity(0.12, status_color),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.24, status_color),
                    ),
                    content=ft.Text(
                        row_data.get('status', 'Нет данных'),
                        size=10,
                        weight="bold",
                        color=status_color,
                    ),
                ),
            ], vertical_alignment="center"),
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

    stress_nominal_hint = ft.Text(
        "оценка по текущим котировкам",
        size=10,
        color=TEXT_SECONDARY,
    )
    stress_executable_hint = ft.Text(
        "что реально удастся вывести",
        size=10,
        color=TEXT_SECONDARY,
    )
    stress_loss_hint = ft.Text(
        "съедается ликвидностью рынка",
        size=10,
        color=TEXT_SECONDARY,
    )
    stress_best_exit_hint = ft.Text(
        "площадка с лучшим суммарным выходом",
        size=10,
        color=TEXT_SECONDARY,
    )

    stress_sell_panel = ft.Container(
        margin=ft.margin.only(left=18, right=18, top=0, bottom=3),
        padding=18,
        border_radius=20,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=["#141922", "#0e131a", "#0c1016"],
        ),
        border=ft.border.all(
            1,
            ft.colors.with_opacity(0.56, BORDER_COLOR),
        ),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16,
            color=ft.colors.with_opacity(0.18, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(
                        "СТРЕСС-ПРОДАЖА ПОРТФЕЛЯ",
                        size=11,
                        weight="bold",
                        color=TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "Исполнимая стоимость при срочной ликвидации",
                        size=18,
                        weight="bold",
                        color=TEXT_PRIMARY,
                    ),
                ], spacing=4),
                ft.Container(expand=True),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=999,
                    bgcolor=ft.colors.with_opacity(0.10, ACCENT_COLOR),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.24, ACCENT_COLOR),
                    ),
                    content=ft.Text(
                        "стресс-сценарий по bid-ликвидности",
                        size=10,
                        color=ACCENT_COLOR,
                        weight="bold",
                    ),
                ),
            ], vertical_alignment="center"),
            ft.Container(height=16),
            ft.Row([
                create_stress_metric(
                    "НА БУМАГЕ",
                    stress_nominal_text,
                    stress_nominal_hint,
                    PRIMARY_COLOR,
                ),
                create_stress_metric(
                    "ПРИ СРОЧНОЙ ПРОДАЖЕ",
                    stress_executable_text,
                    stress_executable_hint,
                    SECONDARY_COLOR,
                ),
                create_stress_metric(
                    "ПОТЕРИ НА ИСПОЛНЕНИИ",
                    stress_loss_text,
                    stress_loss_hint,
                    ACCENT_COLOR,
                ),
                create_stress_metric(
                    "ЛУЧШИЙ ВЫХОД",
                    stress_best_exit_text,
                    stress_best_exit_hint,
                    WARNING_COLOR,
                ),
            ], spacing=12),
            ft.Container(height=12),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                border_radius=16,
                bgcolor=ft.colors.with_opacity(0.16, "#0a1117"),
                border=ft.border.all(
                    1,
                    ft.colors.with_opacity(0.32, BORDER_COLOR),
                ),
                content=ft.Row([
                    ft.Text(
                        "Основной источник потерь",
                        size=11,
                        weight="bold",
                        color=TEXT_SECONDARY,
                    ),
                    ft.Container(width=16),
                    stress_top_loss_text,
                    ft.Container(expand=True),
                    stress_loss_hint_text,
                ], vertical_alignment="center"),
            ),
        ], spacing=0),
    )

    decision_quality_panel = ft.Container(
        margin=ft.margin.only(left=18, right=18, top=0, bottom=3),
        padding=18,
        border_radius=20,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=["#141a21", "#0d1218", "#0b0f15"],
        ),
        border=ft.border.all(
            1,
            ft.colors.with_opacity(0.52, BORDER_COLOR),
        ),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16,
            color=ft.colors.with_opacity(0.16, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(
                        "КАЧЕСТВО РЕШЕНИЙ",
                        size=11,
                        weight="bold",
                        color=TEXT_SECONDARY,
                    ),
                    ft.Text(
                        "Самоанализ выбора площадки",
                        size=18,
                        weight="bold",
                        color=TEXT_PRIMARY,
                    ),
                ], spacing=4),
                ft.Container(expand=True),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=999,
                    bgcolor=ft.colors.with_opacity(0.10, PRIMARY_COLOR),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.24, PRIMARY_COLOR),
                    ),
                    content=ft.Text(
                        "сравнение с лучшей альтернативой",
                        size=10,
                        color=PRIMARY_COLOR,
                        weight="bold",
                    ),
                ),
            ], vertical_alignment="center"),
            ft.Container(height=16),
            ft.Row([
                create_stress_metric(
                    "КАЧЕСТВО ВЫБОРА БИРЖИ",
                    decision_quality_text,
                    ft.Text(
                        "средняя оценка исполнения",
                        size=10,
                        color=TEXT_SECONDARY,
                    ),
                    PRIMARY_COLOR,
                ),
                create_stress_metric(
                    "ПОТЕРИ ЗА 30 ДНЕЙ",
                    decision_month_loss_text,
                    ft.Text(
                        "избыточные расходы за последний месяц",
                        size=10,
                        color=TEXT_SECONDARY,
                    ),
                    ACCENT_COLOR,
                ),
                create_stress_metric(
                    "ОБЩИЕ ИЗБЫТОЧНЫЕ ПОТЕРИ",
                    decision_loss_text,
                    ft.Text(
                        "накопленный эффект неидеального выбора",
                        size=10,
                        color=TEXT_SECONDARY,
                    ),
                    ACCENT_COLOR,
                ),
                create_stress_metric(
                    "НЕВЫГОДНЫЕ ПОКУПКИ",
                    decision_worst_buy_exchange_text,
                    ft.Text(
                        "где чаще всего переплачивается вход",
                        size=10,
                        color=TEXT_SECONDARY,
                    ),
                    WARNING_COLOR,
                ),
                create_stress_metric(
                    "ЛУЧШЕЕ ИСПОЛНЕНИЕ",
                    decision_best_exchange_text,
                    ft.Text(
                        "где решения были сильнее всего",
                        size=10,
                        color=TEXT_SECONDARY,
                    ),
                    SECONDARY_COLOR,
                ),
            ], spacing=12),
            ft.Container(height=12),
            ft.Row([
                ft.Container(
                    expand=3,
                    height=360,
                    padding=16,
                    border_radius=18,
                    bgcolor=ft.colors.with_opacity(0.14, "#0a1117"),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.30, BORDER_COLOR),
                    ),
                    content=ft.Column([
                        ft.Row([
                            ft.Text(
                                "ПОВЕДЕНЧЕСКИЕ СИГНАЛЫ",
                                size=10,
                                weight="bold",
                                color=TEXT_SECONDARY,
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                "как пользователь выбирает площадку",
                                size=10,
                                color=TEXT_SECONDARY,
                            ),
                        ], vertical_alignment="center"),
                        ft.Container(height=12),
                        ft.Column([
                            create_decision_signal(
                                "ТОЧНОСТЬ ПО ЦЕНЕ",
                                decision_best_price_rate_text,
                                "как часто выбрана лучшая цена",
                                PRIMARY_COLOR,
                            ),
                            create_decision_signal(
                                "СОВПАДЕНИЕ С ЛИКВИДНОСТЬЮ",
                                decision_liquidity_rate_text,
                                "как часто совпадает с лучшей глубиной",
                                SECONDARY_COLOR,
                            ),
                            create_decision_signal(
                                "НЕИДЕАЛЬНЫЕ СДЕЛКИ",
                                decision_suboptimal_rate_text,
                                "доля сделок с упущенной выгодой",
                                WARNING_COLOR,
                            ),
                        ], spacing=10, expand=True),
                        ft.Container(height=12),
                        ft.Container(
                            padding=ft.padding.symmetric(horizontal=14, vertical=12),
                            border_radius=16,
                            bgcolor=ft.colors.with_opacity(0.10, PRIMARY_COLOR),
                            border=ft.border.all(
                                1,
                                ft.colors.with_opacity(0.22, PRIMARY_COLOR),
                            ),
                            content=decision_hint_text,
                        ),
                    ], spacing=0, expand=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ),
                ft.Container(width=12),
                ft.Container(
                    expand=4,
                    height=360,
                    padding=16,
                    border_radius=18,
                    bgcolor=ft.colors.with_opacity(0.14, "#0a1117"),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.30, BORDER_COLOR),
                    ),
                    content=ft.Column([
                        ft.Row([
                            ft.Column([
                                ft.Text(
                                    "ЖУРНАЛ РЕШЕНИЙ",
                                    size=10,
                                    weight="bold",
                                    color=TEXT_SECONDARY,
                                ),
                                ft.Text(
                                    "последние сделки и сравнение с лучшей альтернативой",
                                    size=11,
                                    color=TEXT_SECONDARY,
                                ),
                            ], spacing=4),
                            ft.Container(expand=True),
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                border_radius=999,
                                bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                                border=ft.border.all(
                                    1,
                                    ft.colors.with_opacity(0.22, PRIMARY_COLOR),
                                ),
                                content=decision_history_caption_text,
                            ),
                        ], vertical_alignment="center"),
                        ft.Container(height=12),
                        decision_history_rows,
                    ], spacing=0, expand=True),
                ),
            ], spacing=0),
        ], spacing=0),
    )

    assets_gateway_panel = ft.Container(
        margin=ft.margin.only(left=18, right=18, top=0, bottom=3),
        padding=18,
        border_radius=20,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=["#161c24", "#0f141b", "#0c1015"],
        ),
        border=ft.border.all(
            1,
            ft.colors.with_opacity(0.52, BORDER_COLOR),
        ),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=16,
            color=ft.colors.with_opacity(0.16, "#000000"),
            offset=ft.Offset(0, 8),
        ),
        content=ft.Row([
            ft.Column([
                ft.Text(
                    "СОСТАВ ПОРТФЕЛЯ",
                    size=11,
                    weight="bold",
                    color=TEXT_SECONDARY,
                ),
                ft.Text(
                    "Все активы вынесены на отдельную страницу",
                    size=18,
                    weight="bold",
                    color=TEXT_PRIMARY,
                ),
                ft.Text(
                    "Откройте полный экран активов для детального просмотра, фильтрации по биржам и быстрых действий.",
                    size=11,
                    color=TEXT_SECONDARY,
                ),
            ], spacing=6, expand=True),
            ft.Container(width=18),
            ft.Container(
                width=260,
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                border_radius=18,
                bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                border=ft.border.all(
                    1,
                    ft.colors.with_opacity(0.32, PRIMARY_COLOR),
                ),
                ink=True,
                on_click=lambda e: show_assets_page_callback(),
                content=ft.Row([
                    ft.Icon(
                        ft.icons.WALLET_ROUNDED,
                        size=22,
                        color=PRIMARY_COLOR,
                    ),
                    ft.Container(width=10),
                    ft.Column([
                        ft.Text(
                            "Открыть все активы",
                            size=15,
                            weight="bold",
                            color=TEXT_PRIMARY,
                        ),
                        ft.Text(
                            "полноэкранный обзор портфеля",
                            size=10,
                            color=TEXT_SECONDARY,
                        ),
                    ], spacing=3, expand=True),
                    ft.Icon(
                        ft.icons.ARROW_FORWARD_ROUNDED,
                        size=20,
                        color=PRIMARY_COLOR,
                    ),
                ], vertical_alignment="center"),
            ),
        ], vertical_alignment="center"),
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

        stress_summary = analyze_portfolio_stress_sell(portfolio_data)
        nominal_value = stress_summary.get('nominal_value', 0.0)
        executable_value = stress_summary.get('executable_value', 0.0)
        liquidation_loss = stress_summary.get('liquidation_loss', 0.0)
        liquidation_loss_pct = stress_summary.get('liquidation_loss_pct', 0.0)
        best_exit_exchange = stress_summary.get('best_exit_exchange')
        top_loss_assets = stress_summary.get('top_loss_assets') or []

        stress_nominal_text.value = f"${nominal_value:,.2f}"
        stress_executable_text.value = f"${executable_value:,.2f}"
        stress_loss_text.value = f"${liquidation_loss:,.2f}"
        stress_best_exit_text.value = EXCHANGE_NAMES.get(
            best_exit_exchange,
            "Нет данных",
        )
        stress_top_loss_text.value = (
            ", ".join(top_loss_assets)
            if top_loss_assets
            else "Критичных источников потерь не обнаружено"
        )
        stress_loss_hint_text.value = (
            f"Потери на ликвидации: {liquidation_loss_pct:.2f}%"
        )
        stress_loss_text.color = (
            ACCENT_COLOR if liquidation_loss > 0.01 else SUCCESS_COLOR
        )

        decision_summary = get_user_decision_quality_summary(user.id)
        decision_history = get_user_trade_decision_history(user.id, limit=5)
        decision_quality = decision_summary.get('quality_score', 0.0)
        decision_quality_text.value = f"{decision_quality:.0f}%"
        decision_month_loss_text.value = (
            f"${decision_summary.get('avoidable_loss_month', 0.0):,.2f}"
        )
        decision_loss_text.value = (
            f"${decision_summary.get('avoidable_loss_total', 0.0):,.2f}"
        )
        decision_worst_exchange_text.value = format_exchange_name(
            decision_summary.get('worst_exchange')
        )
        decision_worst_buy_exchange_text.value = format_exchange_name(
            decision_summary.get('worst_buy_exchange')
        )
        decision_best_exchange_text.value = format_exchange_name(
            decision_summary.get('best_exchange')
        )
        decision_best_price_rate_text.value = (
            f"{decision_summary.get('best_price_pick_rate', 0.0):.0f}%"
        )
        decision_liquidity_rate_text.value = (
            f"{decision_summary.get('liquidity_alignment_rate', 0.0):.0f}%"
        )
        decision_suboptimal_rate_text.value = (
            f"{decision_summary.get('suboptimal_rate', 0.0):.0f}%"
        )
        dominant_issue_exchange = (
            decision_summary.get('worst_buy_exchange')
            or decision_summary.get('worst_exchange')
        )
        if decision_summary.get('records_count', 0) > 0 and dominant_issue_exchange:
            dominant_side_label = (
                'покупки'
                if decision_summary.get('worst_side_label') == 'Чаще ошибается на покупках'
                else 'продажи'
            )
            decision_hint_text.value = (
                f"Чаще всего невыгодные {dominant_side_label} происходят на "
                f"{format_exchange_name(dominant_issue_exchange)}"
                f" · сделок в анализе: {decision_summary.get('records_count', 0)}"
            )
        else:
            decision_hint_text.value = "История решений появится после первых сделок"
        decision_loss_text.color = (
            ACCENT_COLOR
            if decision_summary.get('avoidable_loss_total', 0.0) > 0.01
            else SUCCESS_COLOR
        )
        decision_month_loss_text.color = (
            ACCENT_COLOR
            if decision_summary.get('avoidable_loss_month', 0.0) > 0.01
            else SUCCESS_COLOR
        )
        if decision_summary.get('best_exchange'):
            decision_history_caption_text.value = (
                f"Лучшие сделки по исполнению: "
                f"{format_exchange_name(decision_summary.get('best_exchange'))}"
            )
        else:
            decision_history_caption_text.value = (
                "Журнал автоматически заполнится после первых ордеров"
            )
        decision_history_rows.controls.clear()
        if decision_history:
            for row in decision_history:
                decision_history_rows.controls.append(
                    create_decision_history_row(row)
                )
        else:
            decision_history_rows.controls.append(
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=14, vertical=18),
                    border_radius=16,
                    bgcolor=ft.colors.with_opacity(0.10, "#0a1117"),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.26, BORDER_COLOR),
                    ),
                    content=ft.Row([
                        ft.Icon(
                            ft.icons.INSIGHTS_OUTLINED,
                            size=20,
                            color=TEXT_SECONDARY,
                        ),
                        ft.Container(width=10),
                        ft.Text(
                            "После первых сделок здесь появится история решений пользователя",
                            size=11,
                            color=TEXT_SECONDARY,
                        ),
                    ], vertical_alignment="center"),
                )
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
            decision_quality_panel,
            stress_sell_panel,
            assets_gateway_panel,
            ft.Container(expand=True),
            footer,
        ], expand=True, spacing=0, scroll="adaptive")
    )

    def render_portfolio(portfolio_data: dict):
        apply_portfolio_summary(portfolio_data)
        page.update()

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
