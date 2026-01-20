"""
Торговый терминал - UI для покупки и продажи активов
Профессиональный дизайн торгового интерфейса
"""
import flet as ft
import logging
from datetime import datetime

from ui.config import (
    DARK_BG, CARD_BG, PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    EXCHANGE_COLORS, EXCHANGE_NAMES,
)

# Настройка логирования для торгового терминала
logger = logging.getLogger(__name__)


def show_trading_dialog(page: ft.Page, current_user: dict, user_keys: list,
                        asset=None, exchange_name=None, side=None):
    """
    Профессиональный торговый терминал
    
    Args:
        page: Страница Flet
        current_user: Текущий пользователь
        user_keys: Список API ключей бирж
        asset: Выбранный актив (опционально)
        exchange_name: Название биржи (опционально)
        side: Направление сделки 'buy' или 'sell' (опционально)
    """
    
    # Логируем открытие терминала
    logger.info(f"[TRADING] Открытие торгового терминала")
    logger.info(f"[TRADING] Пользователь: {current_user.get('user').name if current_user.get('user') else 'Unknown'}")
    logger.info(f"[TRADING] Актив: {asset['currency'] if asset else 'не выбран'}, Биржа: {exchange_name or 'не указана'}, Направление: {side or 'buy'}")
    logger.info(f"[TRADING] Доступно бирж: {len(user_keys) if user_keys else 0}")
    
    # Проверка наличия API ключей
    if not user_keys:
        logger.warning("[TRADING] Нет подключенных бирж!")
        page.snack_bar = ft.SnackBar(
            content=ft.Row([
                ft.Icon(ft.icons.ERROR_OUTLINE, color="#FF5252"),
                ft.Text("Нет подключенных бирж. Добавьте API ключ в настройках.", color=TEXT_PRIMARY),
            ], spacing=10),
            bgcolor=CARD_BG,
        )
        page.snack_bar.open = True
        page.update()
        return
    
    # Начальные значения
    initial_side = side or "buy"
    initial_symbol = f"{asset['currency']}/USDT" if asset else "BTC/USDT"
    initial_exchange = exchange_name or (user_keys[0].exchange_name if user_keys else "bybit")
    
    logger.info(f"[TRADING] Инициализация: пара={initial_symbol}, биржа={initial_exchange}, сторона={initial_side}")
    
    def close_dialog():
        logger.info("[TRADING] Закрытие торгового терминала")
        dialog.open = False
        page.update()
    
    # ==================== СОСТОЯНИЕ И ПОДСКАЗКИ ====================
    status_message = ft.Container(visible=False)
    
    def show_status(message: str, status_type: str = "info"):
        """Показывает статусное сообщение пользователю"""
        colors = {
            "success": SUCCESS_COLOR,
            "error": ACCENT_COLOR,
            "warning": WARNING_COLOR,
            "info": PRIMARY_COLOR,
        }
        icons = {
            "success": ft.icons.CHECK_CIRCLE_OUTLINE,
            "error": ft.icons.ERROR_OUTLINE,
            "warning": ft.icons.WARNING_AMBER_ROUNDED,
            "info": ft.icons.INFO_OUTLINE,
        }
        color = colors.get(status_type, PRIMARY_COLOR)
        icon = icons.get(status_type, ft.icons.INFO_OUTLINE)
        
        logger.info(f"[TRADING] Статус [{status_type.upper()}]: {message}")
        
        status_message.content = ft.Row([
            ft.Icon(icon, size=18, color=color),
            ft.Container(width=8),
            ft.Text(message, size=12, color=color, weight="bold"),
        ])
        status_message.bgcolor = ft.colors.with_opacity(0.1, color)
        status_message.border = ft.border.all(1, ft.colors.with_opacity(0.3, color))
        status_message.visible = True
        page.update()
    
    # ==================== ЦВЕТА ====================
    BUY_COLOR = "#00C853"
    SELL_COLOR = "#FF5252"
    INPUT_BG = "#0d0d1a"
    
    buy_active = initial_side == "buy"
    sell_active = initial_side == "sell"
    action_color = BUY_COLOR if buy_active else SELL_COLOR
    
    # ==================== ЗАГОЛОВОК ====================
    header = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.CANDLESTICK_CHART, size=36, color=PRIMARY_COLOR),
                ft.Container(width=15),
                ft.Column([
                    ft.Text("ТОРГОВЫЙ ТЕРМИНАЛ", size=22, weight="bold", color=TEXT_PRIMARY),
                    ft.Text("Покупка и продажа криптовалют", size=13, color=TEXT_SECONDARY),
                ], spacing=3),
            ]),
            ft.Container(expand=True),
            ft.Row([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.CIRCLE, size=10, color=SUCCESS_COLOR),
                        ft.Text("Рынок открыт", size=12, color=SUCCESS_COLOR, weight="bold"),
                    ], spacing=8),
                    padding=ft.padding.symmetric(horizontal=15, vertical=8),
                    border_radius=20,
                    bgcolor=ft.colors.with_opacity(0.15, SUCCESS_COLOR),
                ),
                ft.Container(width=10),
                ft.IconButton(
                    icon=ft.icons.CLOSE_ROUNDED,
                    icon_color=TEXT_SECONDARY,
                    icon_size=28,
                    on_click=lambda e: close_dialog(),
                    tooltip="Закрыть",
                ),
            ]),
        ], alignment="spaceBetween", vertical_alignment="center"),
        padding=25,
        bgcolor=CARD_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR)),
    )
    
    # ==================== ВЫБОР БИРЖИ И ПАРЫ ====================
    # Название биржи для отображения
    exchange_display_name = {
        "bybit": "Bybit",
        "gateio": "Gate.io", 
        "mexc": "MEXC"
    }.get(initial_exchange, initial_exchange.upper())
    
    # Название монеты
    coin_name = asset['currency'] if asset else "BTC"
    
    exchange_selector = ft.Container(
        content=ft.Row([
            # Биржа (только отображение)
            ft.Column([
                ft.Text("БИРЖА", size=10, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(height=5),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_BALANCE, size=18, color=PRIMARY_COLOR),
                        ft.Container(width=8),
                        ft.Text(exchange_display_name, size=14, weight="bold", color=TEXT_PRIMARY),
                    ]),
                    width=180,
                    height=45,
                    bgcolor=INPUT_BG,
                    border_radius=8,
                    border=ft.border.all(1, BORDER_COLOR),
                    padding=ft.padding.symmetric(horizontal=15),
                    alignment=ft.alignment.center_left,
                ),
            ], spacing=0),
            ft.Container(width=15),
            # Торговая пара (только отображение)
            ft.Column([
                ft.Text("ТОРГОВАЯ ПАРА", size=10, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(height=5),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.CURRENCY_BITCOIN, size=18, color=WARNING_COLOR),
                        ft.Container(width=8),
                        ft.Text(f"{coin_name} / USDT", size=14, weight="bold", color=TEXT_PRIMARY),
                    ]),
                    width=180,
                    height=45,
                    bgcolor=INPUT_BG,
                    border_radius=8,
                    border=ft.border.all(1, BORDER_COLOR),
                    padding=ft.padding.symmetric(horizontal=15),
                    alignment=ft.alignment.center_left,
                ),
            ], spacing=0),
            ft.Container(width=15),
            # Подсказка о подключении
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.CHECK_CIRCLE, size=16, color=SUCCESS_COLOR),
                    ft.Text(f"Подключено: {len(user_keys)} бирж(и)", size=11, color=SUCCESS_COLOR),
                ], spacing=5),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                bgcolor=ft.colors.with_opacity(0.1, SUCCESS_COLOR),
                border_radius=8,
            ),
        ], alignment="start", vertical_alignment="end"),
        padding=20,
        bgcolor=CARD_BG,
        border_radius=12,
        border=ft.border.all(1, BORDER_COLOR),
    )
    
    # ==================== ИНФОРМАЦИЯ О ЦЕНЕ ====================
    price_info = ft.Container(
        content=ft.Row([
            # Текущая цена (левая часть)
            ft.Container(
                content=ft.Column([
                    ft.Text("ТЕКУЩАЯ ЦЕНА", size=11, color=TEXT_SECONDARY, weight="bold"),
                    ft.Container(height=10),
                    ft.Row([
                        ft.Text("$", size=28, color=SUCCESS_COLOR, weight="bold"),
                        ft.Text("104,250.00", size=42, weight="bold", color=SUCCESS_COLOR),
                    ], spacing=3, vertical_alignment="end"),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Icon(ft.icons.TRENDING_UP, size=22, color=SUCCESS_COLOR),
                        ft.Text("+2.45%", size=16, color=SUCCESS_COLOR, weight="bold"),
                        ft.Text("за 24ч", size=13, color=TEXT_SECONDARY),
                    ], spacing=8),
                ], spacing=0),
                expand=2,
            ),
            
            # Разделитель
            ft.Container(
                content=ft.VerticalDivider(width=1, color=BORDER_COLOR),
                height=100,
                padding=ft.padding.symmetric(horizontal=20),
            ),
            
            # Статистика (правая часть)
            ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text("24ч МАКС", size=11, color=TEXT_SECONDARY, weight="bold"),
                        ft.Container(height=5),
                        ft.Text("$105,800", size=18, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=0, horizontal_alignment="center"),
                    ft.Container(width=30),
                    ft.Column([
                        ft.Text("24ч МИН", size=11, color=TEXT_SECONDARY, weight="bold"),
                        ft.Container(height=5),
                        ft.Text("$101,200", size=18, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=0, horizontal_alignment="center"),
                    ft.Container(width=30),
                    ft.Column([
                        ft.Text("ОБЪЁМ", size=11, color=TEXT_SECONDARY, weight="bold"),
                        ft.Container(height=5),
                        ft.Text("$2.4B", size=18, weight="bold", color=PRIMARY_COLOR),
                    ], spacing=0, horizontal_alignment="center"),
                ], alignment="center"),
                expand=3,
            ),
        ], vertical_alignment="center"),
        padding=25,
        bgcolor=ft.colors.with_opacity(0.05, SUCCESS_COLOR),
        border_radius=12,
        border=ft.border.all(1, ft.colors.with_opacity(0.25, SUCCESS_COLOR)),
    )
    
    # ==================== ПЕРЕКЛЮЧАТЕЛЬ КУПИТЬ/ПРОДАТЬ ====================
    side_selector = ft.Container(
        content=ft.Row([
            # Кнопка КУПИТЬ
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.ARROW_DOWNWARD_ROUNDED, size=26, color=DARK_BG if buy_active else BUY_COLOR),
                    ft.Container(width=10),
                    ft.Text("КУПИТЬ", size=18, weight="bold", color=DARK_BG if buy_active else BUY_COLOR),
                ], alignment="center"),
                expand=True,
                height=60,
                bgcolor=BUY_COLOR if buy_active else ft.colors.with_opacity(0.1, BUY_COLOR),
                border_radius=ft.border_radius.only(top_left=12, bottom_left=12),
                border=ft.border.all(2, BUY_COLOR),
                alignment=ft.alignment.center,
                ink=True,
            ),
            # Кнопка ПРОДАТЬ
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.ARROW_UPWARD_ROUNDED, size=26, color=DARK_BG if sell_active else SELL_COLOR),
                    ft.Container(width=10),
                    ft.Text("ПРОДАТЬ", size=18, weight="bold", color=DARK_BG if sell_active else SELL_COLOR),
                ], alignment="center"),
                expand=True,
                height=60,
                bgcolor=SELL_COLOR if sell_active else ft.colors.with_opacity(0.1, SELL_COLOR),
                border_radius=ft.border_radius.only(top_right=12, bottom_right=12),
                border=ft.border.all(2, SELL_COLOR),
                alignment=ft.alignment.center,
                ink=True,
            ),
        ], spacing=0),
    )
    
    # ==================== ТИП ОРДЕРА ====================
    order_type_selector = ft.Container(
        content=ft.Column([
            ft.Text("ТИП ОРДЕРА", size=11, color=TEXT_SECONDARY, weight="bold"),
            ft.Container(height=15),
            ft.Row([
                # Рыночный
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.FLASH_ON_ROUNDED, size=32, color=PRIMARY_COLOR),
                        ft.Container(height=8),
                        ft.Text("Рыночный", size=15, weight="bold", color=TEXT_PRIMARY),
                        ft.Text("Моментальное исполнение", size=11, color=TEXT_SECONDARY),
                    ], horizontal_alignment="center", spacing=2),
                    expand=True,
                    padding=20,
                    bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                    border_radius=12,
                    border=ft.border.all(2, PRIMARY_COLOR),
                    alignment=ft.alignment.center,
                    ink=True,
                ),
                ft.Container(width=15),
                # Лимитный
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SCHEDULE_ROUNDED, size=32, color=TEXT_SECONDARY),
                        ft.Container(height=8),
                        ft.Text("Лимитный", size=15, weight="bold", color=TEXT_PRIMARY),
                        ft.Text("По указанной цене", size=11, color=TEXT_SECONDARY),
                    ], horizontal_alignment="center", spacing=2),
                    expand=True,
                    padding=20,
                    bgcolor=ft.colors.with_opacity(0.03, TEXT_SECONDARY),
                    border_radius=12,
                    border=ft.border.all(1, BORDER_COLOR),
                    alignment=ft.alignment.center,
                    ink=True,
                ),
                ft.Container(width=15),
                # Стоп-лимит
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SHIELD_ROUNDED, size=32, color=TEXT_SECONDARY),
                        ft.Container(height=8),
                        ft.Text("Стоп-лимит", size=15, weight="bold", color=TEXT_PRIMARY),
                        ft.Text("При достижении цены", size=11, color=TEXT_SECONDARY),
                    ], horizontal_alignment="center", spacing=2),
                    expand=True,
                    padding=20,
                    bgcolor=ft.colors.with_opacity(0.03, TEXT_SECONDARY),
                    border_radius=12,
                    border=ft.border.all(1, BORDER_COLOR),
                    alignment=ft.alignment.center,
                    ink=True,
                ),
            ]),
        ]),
        padding=25,
        bgcolor=CARD_BG,
        border_radius=12,
        border=ft.border.all(1, BORDER_COLOR),
    )
    
    # ==================== ФОРМА ВВОДА ====================
    input_form = ft.Container(
        content=ft.Column([
            # Количество
            ft.Row([
                ft.Text("КОЛИЧЕСТВО", size=11, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(expand=True),
                ft.Text("Доступно: ", size=12, color=TEXT_SECONDARY),
                ft.Text("0.5823 BTC", size=12, color=PRIMARY_COLOR, weight="bold"),
            ]),
            ft.Container(height=12),
            ft.Row([
                ft.TextField(
                    value="0.001",
                    expand=True,
                    height=60,
                    bgcolor=INPUT_BG,
                    border_color=BORDER_COLOR,
                    focused_border_color=PRIMARY_COLOR,
                    text_size=20,
                    text_align="right",
                    suffix_text="BTC",
                    content_padding=ft.padding.symmetric(horizontal=20, vertical=15),
                ),
                ft.Container(width=20),
                # Быстрый выбор процента
                ft.Row([
                    ft.Container(
                        content=ft.Text("25%", size=13, color=TEXT_SECONDARY, weight="bold"),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        bgcolor=INPUT_BG,
                        border_radius=8,
                        border=ft.border.all(1, BORDER_COLOR),
                        ink=True,
                    ),
                    ft.Container(
                        content=ft.Text("50%", size=13, color=TEXT_SECONDARY, weight="bold"),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        bgcolor=INPUT_BG,
                        border_radius=8,
                        border=ft.border.all(1, BORDER_COLOR),
                        ink=True,
                    ),
                    ft.Container(
                        content=ft.Text("75%", size=13, color=TEXT_SECONDARY, weight="bold"),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        bgcolor=INPUT_BG,
                        border_radius=8,
                        border=ft.border.all(1, BORDER_COLOR),
                        ink=True,
                    ),
                    ft.Container(
                        content=ft.Text("MAX", size=13, color=PRIMARY_COLOR, weight="bold"),
                        padding=ft.padding.symmetric(horizontal=16, vertical=12),
                        bgcolor=ft.colors.with_opacity(0.15, PRIMARY_COLOR),
                        border_radius=8,
                        border=ft.border.all(1, PRIMARY_COLOR),
                        ink=True,
                    ),
                ], spacing=10),
            ]),
        ]),
        padding=25,
        bgcolor=CARD_BG,
        border_radius=12,
        border=ft.border.all(1, BORDER_COLOR),
    )
    
    # ==================== ИТОГОВЫЙ РАСЧЁТ ====================
    summary = ft.Container(
        content=ft.Row([
            # Левая часть - детали
            ft.Container(
                content=ft.Column([
                    ft.Text("ДЕТАЛИ ОРДЕРА", size=11, color=TEXT_SECONDARY, weight="bold"),
                    ft.Container(height=15),
                    ft.Row([
                        ft.Text("Количество", size=14, color=TEXT_SECONDARY),
                        ft.Container(expand=True),
                        ft.Text("0.001 BTC", size=14, color=TEXT_PRIMARY, weight="bold"),
                    ]),
                    ft.Container(height=10),
                    ft.Row([
                        ft.Text("Цена исполнения", size=14, color=TEXT_SECONDARY),
                        ft.Container(expand=True),
                        ft.Text("$104,250.00", size=14, color=TEXT_PRIMARY, weight="bold"),
                    ]),
                    ft.Container(height=10),
                    ft.Row([
                        ft.Text("Комиссия (0.1%)", size=14, color=TEXT_SECONDARY),
                        ft.Container(expand=True),
                        ft.Text("$0.10", size=14, color=WARNING_COLOR, weight="bold"),
                    ]),
                ], spacing=0),
                expand=True,
            ),
            
            # Разделитель
            ft.Container(
                content=ft.VerticalDivider(width=1, color=BORDER_COLOR),
                height=120,
                padding=ft.padding.symmetric(horizontal=25),
            ),
            
            # Правая часть - итого
            ft.Container(
                content=ft.Column([
                    ft.Text("ИТОГО К ОПЛАТЕ", size=11, color=TEXT_SECONDARY, weight="bold"),
                    ft.Container(height=10),
                    ft.Text("$104.35", size=36, color=action_color, weight="bold"),
                    ft.Container(height=5),
                    ft.Text("≈ 0.001 BTC", size=13, color=TEXT_SECONDARY),
                ], horizontal_alignment="center", spacing=0),
                width=180,
            ),
        ], vertical_alignment="center"),
        padding=25,
        bgcolor=ft.colors.with_opacity(0.05, action_color),
        border_radius=12,
        border=ft.border.all(1, ft.colors.with_opacity(0.3, action_color)),
    )
    
    # ==================== ПРЕДУПРЕЖДЕНИЯ ====================
    warnings = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.INFO_OUTLINE_ROUNDED, size=22, color=WARNING_COLOR),
            ft.Container(width=15),
            ft.Column([
                ft.Text("Важная информация", size=13, color=WARNING_COLOR, weight="bold"),
                ft.Container(height=3),
                ft.Text(
                    "Торговля криптовалютами сопряжена с высоким риском. Убедитесь, что вы понимаете все риски перед совершением сделки.",
                    size=12, color=TEXT_SECONDARY,
                ),
            ], spacing=0, expand=True),
        ], vertical_alignment="start"),
        padding=20,
        bgcolor=ft.colors.with_opacity(0.1, WARNING_COLOR),
        border_radius=12,
        border=ft.border.all(1, ft.colors.with_opacity(0.3, WARNING_COLOR)),
    )
    
    # ==================== СТАТУСНОЕ СООБЩЕНИЕ ====================
    status_message.padding = ft.padding.symmetric(horizontal=15, vertical=10)
    status_message.border_radius = 10
    status_message.margin = ft.margin.only(bottom=10)
    
    # ==================== ПОДСКАЗКИ ПО ШАГАМ ====================
    steps_hint = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text("1", size=11, color=DARK_BG, weight="bold"),
                        width=22, height=22,
                        border_radius=11,
                        bgcolor=PRIMARY_COLOR,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text("Выберите пару", size=11, color=TEXT_SECONDARY),
                ], spacing=6),
            ),
            ft.Icon(ft.icons.ARROW_FORWARD, size=14, color=BORDER_COLOR),
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text("2", size=11, color=DARK_BG, weight="bold"),
                        width=22, height=22,
                        border_radius=11,
                        bgcolor=PRIMARY_COLOR,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text("Укажите количество", size=11, color=TEXT_SECONDARY),
                ], spacing=6),
            ),
            ft.Icon(ft.icons.ARROW_FORWARD, size=14, color=BORDER_COLOR),
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text("3", size=11, color=DARK_BG, weight="bold"),
                        width=22, height=22,
                        border_radius=11,
                        bgcolor=PRIMARY_COLOR,
                        alignment=ft.alignment.center,
                    ),
                    ft.Text("Подтвердите ордер", size=11, color=TEXT_SECONDARY),
                ], spacing=6),
            ),
        ], alignment="center", spacing=15),
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        bgcolor=ft.colors.with_opacity(0.05, PRIMARY_COLOR),
        border_radius=10,
        border=ft.border.all(1, ft.colors.with_opacity(0.2, PRIMARY_COLOR)),
    )
    
    # ==================== КНОПКА ДЕЙСТВИЯ ====================
    action_button = ft.Container(
        content=ft.Row([
            ft.Icon(
                ft.icons.ARROW_DOWNWARD_ROUNDED if buy_active else ft.icons.ARROW_UPWARD_ROUNDED, 
                size=28, 
                color=DARK_BG
            ),
            ft.Container(width=12),
            ft.Text(
                f"{'КУПИТЬ' if buy_active else 'ПРОДАТЬ'} BTC", 
                size=20, 
                weight="bold", 
                color=DARK_BG
            ),
        ], alignment="center"),
        height=65,
        bgcolor=action_color,
        border_radius=12,
        alignment=ft.alignment.center,
        ink=True,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=25,
            color=ft.colors.with_opacity(0.5, action_color),
        ),
    )
    
    # ==================== ОСНОВНОЙ КОНТЕНТ ====================
    content = ft.Column([
        header,
        ft.Container(
            content=ft.Column([
                steps_hint,
                ft.Container(height=15),
                status_message,
                exchange_selector,
                ft.Container(height=20),
                price_info,
                ft.Container(height=20),
                side_selector,
                ft.Container(height=20),
                order_type_selector,
                ft.Container(height=20),
                input_form,
                ft.Container(height=20),
                summary,
                ft.Container(height=25),
                action_button,
            ], scroll="auto"),
            padding=25,
            expand=True,
        ),
    ], spacing=0)
    
    # Логируем успешную инициализацию
    logger.info(f"[TRADING] Терминал успешно инициализирован")
    
    # ==================== ДИАЛОГОВОЕ ОКНО ====================
    dialog = ft.AlertDialog(
        modal=True,
        title=None,
        content=ft.Container(
            content=content,
            width=700,
            height=850,
            bgcolor=DARK_BG,
            border_radius=20,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        ),
        bgcolor=ft.colors.TRANSPARENT,
        content_padding=0,
        inset_padding=30,
        shape=ft.RoundedRectangleBorder(radius=20),
    )
    
    page.overlay.append(dialog)
    dialog.open = True
    page.update()
