"""
Страница с детальной историей торговых сделок
Хронологический порядок, фильтрация по биржам, аналитика
"""
import logging
from datetime import datetime, timedelta

import flet as ft

from backend.models import TradeDecisionHistory, session
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

logger = logging.getLogger(__name__)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _format_money(value):
    return f"${_safe_float(value):,.2f}"


def _format_amount(value):
    amount = _safe_float(value)
    if amount >= 1000:
        return f"{amount:,.2f}"
    if amount >= 1:
        return f"{amount:,.4f}"
    return f"{amount:,.6f}"


def _get_trade_quality_color(score):
    """Возвращает цвет на основе оценки качества 0-100"""
    score = _safe_float(score)
    if score >= 90:
        return SUCCESS_COLOR      # Зеленый - отлично
    elif score >= 70:
        return SECONDARY_COLOR    # Неоновый - хорошо
    elif score >= 50:
        return "#FFA500"          # Оранжевый - средне
    else:
        return ACCENT_COLOR       # Coral - плохо


def _get_side_label_and_color(side: str):
    """Возвращает русский label и цвет для стороны сделки"""
    side_lower = str(side or "").lower().strip()
    if side_lower == "buy":
        return "ПОКУПКА", "#00C853"  # Зеленый - покупка
    else:
        return "ПРОДАЖА", "#FF5252"  # Красный - продажа


def _load_user_trades(user_id: int, exchange_filter: str = None):
    """Загружает сделки пользователя из БД"""
    try:
        query = session.query(TradeDecisionHistory).filter_by(user_id=user_id)
        
        if exchange_filter and exchange_filter != "all":
            query = query.filter_by(actual_exchange=exchange_filter)
        
        trades = query.order_by(
            TradeDecisionHistory.created_at.desc()
        ).all()
        
        return trades
    except Exception as e:
        logger.error(f"[TRADES HISTORY] Error loading trades: {e}")
        return []


def _build_trade_card(trade: TradeDecisionHistory, is_selected=False):
    """Строит UI карточку для одной сделки"""
    
    side_label, side_color = _get_side_label_and_color(trade.side)
    exchange_name = EXCHANGE_NAMES.get(trade.actual_exchange, trade.actual_exchange.upper())
    exchange_color = EXCHANGE_COLORS.get(trade.actual_exchange, PRIMARY_COLOR)
    quality_score = _safe_float(trade.execution_quality_score, 0.0)
    quality_color = _get_trade_quality_color(quality_score)
    avoidable_loss = _safe_float(trade.avoidable_loss, 0.0)
    is_loss = avoidable_loss > 0.01
    loss_color = ACCENT_COLOR if is_loss else SUCCESS_COLOR
    
    # Извлечение пары и символа
    symbol = str(trade.symbol or "").upper()
    asset, quote = (symbol.split("/") if "/" in symbol else (symbol, ""))[:2]
    
    # Timeline точка слева
    timeline_dot = ft.Container(
        width=12,
        height=12,
        border_radius=999,
        bgcolor=quality_color,
        border=ft.border.all(3, DARK_BG),
    )
    
    # Основная карточка
    card_content = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=ft.colors.with_opacity(0.14, "#0a1117") if not is_selected else ft.colors.with_opacity(0.26, PRIMARY_COLOR),
        border=ft.border.all(
            2 if is_selected else 1,
            PRIMARY_COLOR if is_selected else ft.colors.with_opacity(0.36, BORDER_COLOR),
        ),
        content=ft.Column([
            # Заголовок: пара и время
            ft.Row([
                ft.Column([
                    ft.Text(
                        symbol,
                        size=18,
                        weight="bold",
                        color=TEXT_PRIMARY,
                    ),
                    ft.Text(
                        trade.created_at.strftime("%d.%m.%Y %H:%M:%S") if trade.created_at else "N/A",
                        size=10,
                        color=TEXT_SECONDARY,
                    ),
                ], spacing=2, expand=True),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=8,
                    bgcolor=ft.colors.with_opacity(0.18, side_color),
                    border=ft.border.all(1, side_color),
                    content=ft.Text(
                        side_label,
                        size=11,
                        weight="bold",
                        color=side_color,
                    ),
                ),
            ], vertical_alignment="center"),
            
            ft.Divider(height=12, color=ft.colors.with_opacity(0.2, BORDER_COLOR)),
            
            # Основные данные сделки (2 колонки)
            ft.Row([
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        ft.Row([
                            ft.Text("КОЛИЧЕСТВО", size=8, color=TEXT_SECONDARY, weight="bold"),
                            ft.Container(expand=True),
                            ft.Text(
                                _format_amount(trade.amount),
                                size=12,
                                weight="bold",
                                color=TEXT_PRIMARY,
                            ),
                        ]),
                        ft.Container(height=6),
                        ft.Row([
                            ft.Text("СУММА", size=8, color=TEXT_SECONDARY, weight="bold"),
                            ft.Container(expand=True),
                            ft.Text(
                                _format_money(trade.notional_usdt),
                                size=12,
                                weight="bold",
                                color=PRIMARY_COLOR,
                            ),
                        ]),
                    ], spacing=8),
                ),
                ft.Container(width=16),
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        ft.Row([
                            ft.Text("ЦЕНА", size=8, color=TEXT_SECONDARY, weight="bold"),
                            ft.Container(expand=True),
                            ft.Text(
                                f"${_safe_float(trade.actual_price):,.6f}",
                                size=12,
                                weight="bold",
                                color=TEXT_PRIMARY,
                            ),
                        ]),
                        ft.Container(height=6),
                        ft.Row([
                            ft.Text("БИРЖА", size=8, color=TEXT_SECONDARY, weight="bold"),
                            ft.Container(expand=True),
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6,
                                bgcolor=ft.colors.with_opacity(0.18, exchange_color),
                                border=ft.border.all(1, exchange_color),
                                content=ft.Text(
                                    exchange_name,
                                    size=10,
                                    weight="bold",
                                    color=exchange_color,
                                ),
                            ),
                        ]),
                    ], spacing=8),
                ),
            ], spacing=0),
            
            ft.Divider(height=12, color=ft.colors.with_opacity(0.2, BORDER_COLOR)),
            
            # Метрики качества (3 колонки)
            ft.Row([
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        ft.Text("КАЧЕСТВО", size=8, color=TEXT_SECONDARY, weight="bold"),
                        ft.Container(height=4),
                        ft.Row([
                            ft.Container(
                                width=8,
                                height=8,
                                border_radius=999,
                                bgcolor=quality_color,
                            ),
                            ft.Container(width=6),
                            ft.Text(
                                f"{quality_score:.0f}%",
                                size=16,
                                weight="bold",
                                color=quality_color,
                            ),
                        ], vertical_alignment="center"),
                    ], spacing=2),
                ),
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        ft.Text("НЕИЗБЕЖНЫЕ ПОТЕРИ", size=8, color=TEXT_SECONDARY, weight="bold"),
                        ft.Container(height=4),
                        ft.Row([
                            ft.Container(
                                width=8,
                                height=8,
                                border_radius=999,
                                bgcolor=loss_color,
                            ),
                            ft.Container(width=6),
                            ft.Text(
                                _format_money(avoidable_loss),
                                size=16,
                                weight="bold",
                                color=loss_color,
                            ),
                        ], vertical_alignment="center"),
                    ], spacing=2),
                ),
                ft.Container(
                    expand=True,
                    content=ft.Column([
                        ft.Text("ПОТЕРИ %", size=8, color=TEXT_SECONDARY, weight="bold"),
                        ft.Container(height=4),
                        ft.Row([
                            ft.Container(
                                width=8,
                                height=8,
                                border_radius=999,
                                bgcolor=loss_color,
                            ),
                            ft.Container(width=6),
                            ft.Text(
                                f"{_safe_float(trade.avoidable_loss_pct):.2f}%",
                                size=16,
                                weight="bold",
                                color=loss_color,
                            ),
                        ], vertical_alignment="center"),
                    ], spacing=2),
                ),
            ], spacing=0),
            
            # Альтернативная биржа (если есть)
            ft.Container(height=8),
            ft.Row([
                ft.Icon(ft.icons.TRENDING_UP_ROUNDED, size=14, color=SECONDARY_COLOR),
                ft.Container(width=6),
                ft.Text(
                    "Альтернатива: ",
                    size=10,
                    color=TEXT_SECONDARY,
                    weight="bold",
                ),
                ft.Text(
                    EXCHANGE_NAMES.get(trade.best_exchange, trade.best_exchange or "Данные не доступны") if trade.best_exchange else "Данные не доступны",
                    size=10,
                    color=SECONDARY_COLOR,
                    weight="bold",
                ),
                ft.Text(
                    f"@ ${_safe_float(trade.best_possible_price):,.6f}",
                    size=10,
                    color=TEXT_SECONDARY,
                ),
            ]) if trade.best_exchange else ft.Container(),
        ], spacing=0),
    )
    
    return ft.Row([
        # Timeline слева
        ft.Column([
            ft.Container(height=8),
            timeline_dot,
            ft.Container(expand=True, height=1, bgcolor=ft.colors.with_opacity(0.18, quality_color)),
        ], spacing=0, horizontal_alignment="center"),
        ft.Container(width=12),
        # Основная карточка
        ft.Container(expand=True, content=card_content),
    ], vertical_alignment="start", spacing=0)


def show_trades_history_page(
    page: ft.Page,
    current_user: dict,
    show_assets_callback,
):
    """Показывает страницу с историей сделок"""
    
    user = current_user.get("user")
    if not user:
        logger.warning("[TRADES HISTORY] Missing user, returning to assets")
        show_assets_callback()
        return
    
    logger.info(f"[TRADES HISTORY] Open page for user={user.name}")
    
    page.controls.clear()
    
    # ============ STATE ============
    state = {"filter": "all"}
    
    # ============ TEXT CONTROLS ============
    total_trades_text = ft.Text("0", size=28, weight="bold", color=PRIMARY_COLOR)
    total_loss_text = ft.Text("$0.00", size=28, weight="bold", color=ACCENT_COLOR)
    avg_quality_text = ft.Text("0%", size=28, weight="bold", color=SECONDARY_COLOR)
    period_text = ft.Text("Все время", size=12, color=TEXT_SECONDARY)
    
    trades_list = ft.Column(spacing=12, scroll="adaptive", expand=True)
    
    # ============ ФИЛЬТРЫ ============
    def create_filter_chip(label: str, value: str, is_active: bool):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            border_radius=999,
            bgcolor=ft.colors.with_opacity(0.22, PRIMARY_COLOR) if is_active else ft.colors.with_opacity(0.14, BORDER_COLOR),
            border=ft.border.all(2 if is_active else 1, PRIMARY_COLOR if is_active else ft.colors.with_opacity(0.36, BORDER_COLOR)),
            content=ft.Text(
                label,
                size=12,
                weight="bold",
                color=PRIMARY_COLOR if is_active else TEXT_SECONDARY,
            ),
            on_click=lambda e, v=value: apply_filter(v),
            ink=True,
        )
    
    filter_chips_container = ft.Row(spacing=8, scroll="adaptive")
    
    def apply_filter(exchange_filter: str):
        """Применяет фильтр и обновляет список сделок"""
        state["filter"] = exchange_filter
        
        # Обновляем фильтр-чипсы
        filter_chips_container.controls.clear()
        for label, value in [("ВСЕ БИРЖИ", "all"), ("Bybit", "bybit"), ("Gate.io", "gateio"), ("MEXC", "mexc")]:
            filter_chips_container.controls.append(
                create_filter_chip(label, value, value == exchange_filter)
            )
        
        # Загружаем сделки
        trades = _load_user_trades(user.id, exchange_filter if exchange_filter != "all" else None)
        
        # Обновляем статистику
        if trades:
            total_trades_text.value = str(len(trades))
            total_loss = sum(_safe_float(t.avoidable_loss) for t in trades)
            avg_quality = sum(_safe_float(t.execution_quality_score) for t in trades) / len(trades) if trades else 0.0
            
            total_loss_text.value = _format_money(total_loss)
            avg_quality_text.value = f"{avg_quality:.0f}%"
            
            total_loss_text.color = ACCENT_COLOR if total_loss > 0.01 else SUCCESS_COLOR
            
            # Определяем период
            if trades:
                newest = trades[0].created_at
                oldest = trades[-1].created_at
                if newest and oldest:
                    days_diff = (newest - oldest).days
                    if days_diff == 0:
                        period_text.value = "Сегодня"
                    elif days_diff < 7:
                        period_text.value = f"За {days_diff} дней"
                    elif days_diff < 30:
                        weeks = days_diff // 7
                        period_text.value = f"За {weeks} недель"
                    else:
                        months = days_diff // 30
                        period_text.value = f"За {months} месяцев"
        else:
            total_trades_text.value = "0"
            total_loss_text.value = "$0.00"
            avg_quality_text.value = "0%"
            period_text.value = "Нет данных"
        
        # Строим список карточек
        trades_list.controls.clear()
        
        if not trades:
            trades_list.controls.append(
                ft.Container(
                    expand=True,
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.icons.HISTORY_ROUNDED, size=80, color=TEXT_SECONDARY),
                        ft.Container(height=20),
                        ft.Text(
                            "Нет сделок",
                            size=24,
                            weight="bold",
                            color=TEXT_SECONDARY,
                        ),
                        ft.Text(
                            "История операций появится после первых торговых сделок",
                            size=14,
                            color=TEXT_SECONDARY,
                            text_align="center",
                        ),
                    ], alignment="center", horizontal_alignment="center"),
                )
            )
        else:
            for i, trade in enumerate(trades):
                trades_list.controls.append(
                    _build_trade_card(trade, is_selected=False)
                )
        
        page.update()
    
    # ============ HEADER ============
    header = ft.Container(
        padding=ft.padding.symmetric(horizontal=18, vertical=16),
        bgcolor=DARK_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.36, BORDER_COLOR))),
        content=ft.Column([
            # Back button + title
            ft.Row([
                ft.IconButton(
                    ft.icons.ARROW_BACK_ROUNDED,
                    icon_size=24,
                    on_click=lambda e: show_assets_callback(),
                    tooltip="Вернуться к активам",
                ),
                ft.Column([
                    ft.Text(
                        "ИСТОРИЯ СДЕЛОК",
                        size=20,
                        weight="bold",
                        color=PRIMARY_COLOR,
                    ),
                    ft.Text(
                        "Детальная аналитика всех торговых операций",
                        size=11,
                        color=TEXT_SECONDARY,
                    ),
                ], spacing=2, expand=True),
            ], vertical_alignment="center"),
            
            ft.Container(height=12),
            
            # Статистика (3 метрики)
            ft.Row([
                ft.Container(
                    expand=True,
                    padding=12,
                    border_radius=14,
                    bgcolor=ft.colors.with_opacity(0.14, "#0b1118"),
                    border=ft.border.all(1, ft.colors.with_opacity(0.36, BORDER_COLOR)),
                    content=ft.Column([
                        ft.Text("ВСЕГО СДЕЛОК", size=9, weight="bold", color=TEXT_SECONDARY),
                        ft.Container(height=6),
                        total_trades_text,
                        ft.Container(height=4),
                        period_text,
                    ], spacing=0),
                ),
                ft.Container(width=8),
                ft.Container(
                    expand=True,
                    padding=12,
                    border_radius=14,
                    bgcolor=ft.colors.with_opacity(0.14, "#0b1118"),
                    border=ft.border.all(1, ft.colors.with_opacity(0.36, BORDER_COLOR)),
                    content=ft.Column([
                        ft.Text("НЕИЗБЕЖНЫЕ ПОТЕРИ", size=9, weight="bold", color=TEXT_SECONDARY),
                        ft.Container(height=6),
                        total_loss_text,
                        ft.Container(height=4),
                        ft.Text("от неоптимального выбора", size=8, color=TEXT_SECONDARY),
                    ], spacing=0),
                ),
                ft.Container(width=8),
                ft.Container(
                    expand=True,
                    padding=12,
                    border_radius=14,
                    bgcolor=ft.colors.with_opacity(0.14, "#0b1118"),
                    border=ft.border.all(1, ft.colors.with_opacity(0.36, BORDER_COLOR)),
                    content=ft.Column([
                        ft.Text("СРЕДНЕЕ КАЧЕСТВО", size=9, weight="bold", color=TEXT_SECONDARY),
                        ft.Container(height=6),
                        avg_quality_text,
                        ft.Container(height=4),
                        ft.Text("оценка исполнения", size=8, color=TEXT_SECONDARY),
                    ], spacing=0),
                ),
            ], spacing=0),
            
            ft.Container(height=12),
            
            # Фильтр по биржам
            ft.Column([
                ft.Text("ФИЛЬТР ПО БИРЖАМ", size=9, weight="bold", color=TEXT_SECONDARY),
                ft.Container(height=8),
                filter_chips_container,
            ], spacing=0),
        ], spacing=0),
    )
    
    # ============ FOOTER ============
    footer = ft.Container(
        content=ft.Row([
            ft.Text(
                "© 2024 Invest Wallet • Аналитика торговых решений",
                size=10,
                color=TEXT_SECONDARY,
                italic=True,
            ),
        ]),
        padding=ft.padding.symmetric(horizontal=18, vertical=12),
        bgcolor=CARD_BG,
        border=ft.border.only(top=ft.BorderSide(1, ft.colors.with_opacity(0.36, BORDER_COLOR))),
    )
    
    # ============ MAIN LAYOUT ============
    page.add(
        ft.Column([
            header,
            ft.Container(
                expand=True,
                content=trades_list,
                padding=ft.padding.symmetric(horizontal=18, vertical=12),
            ),
            footer,
        ], expand=True, spacing=0)
    )
    
    # Инициализируем первый фильтр (все биржи)
    apply_filter("all")


