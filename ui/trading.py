"""
Торговый терминал - UI для покупки и продажи активов
Профессиональный дизайн торгового интерфейса
"""
import flet as ft
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
    
    # подключение к локальной БД, где хранятся пары и балансы
    db = DatabaseManager()
    if not db.connect():
        # показать статус позже, когда определим функцию show_status
        logger.error("[TRADING] Не удалось подключиться к локальной БД")
    
    # функции доступа к локальным таблицам
    def query_pair_info(exchange, symbol):
        try:
            db.cursor.execute(
                f"SELECT current_price, change_24h_percent, change_24h_absolute, high_24h, low_24h, volume_24h, maker_fee, taker_fee, min_order_amount, lot_size"
                f" FROM {exchange}_pairs WHERE symbol=%s",
                (symbol,)
            )
            row = db.cursor.fetchone()
            if row:
                keys = [
                    'current_price','change_24h_percent','change_24h_absolute',
                    'high_24h','low_24h','volume_24h', 'maker_fee', 'taker_fee', 'min_order_amount', 'lot_size'
                ]
                return dict(zip(keys, row))
        except Exception as e:
            logger.error(f"[TRADING] Ошибка запроса пары из БД: {e}")
        return {}
    
    def query_balance(exchange, asset):
        try:
            db.cursor.execute(
                f"SELECT free, locked, total FROM {exchange}_balance WHERE asset=%s",
                (asset,)
            )
            row = db.cursor.fetchone()
            if row:
                return {'free': row[0], 'locked': row[1], 'total': row[2]}
        except Exception as e:
            logger.error(f"[TRADING] Ошибка запроса баланса из БД: {e}")
        return {}
    
    def close_dialog():
        logger.info("[TRADING] Закрытие торгового терминала")
        try:
            db.close()
        except:
            pass
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
    # текущий тип ордера: 'market', 'limit', 'stop-limit'
    order_type = 'market'
    
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
    # текущее состояние
    current_exchange = initial_exchange
    current_symbol = initial_symbol
    side_selector_value = initial_side
    # имя монеты из символа
    coin_name = current_symbol.split("/")[0] if "/" in current_symbol else current_symbol

    # динамический текст для отображения доступных средств
    available_text = ft.Text("", size=12, color=PRIMARY_COLOR, weight="bold")

    # утилиты для обновления UI
    def load_symbols(exchange):
        symbols = []
        try:
            db.cursor.execute(f"SELECT symbol FROM {exchange}_pairs ORDER BY symbol LIMIT 100")
            symbols = [r[0] for r in db.cursor.fetchall()]
        except Exception as e:
            logger.error(f"[TRADING] Не удалось загрузить символы из БД: {e}")
        symbol_dropdown.options = [ft.dropdown.Option(s) for s in symbols]
        if symbols:
            symbol_dropdown.value = symbols[0]
            on_symbol_changed(symbols[0])

    def on_exchange_changed(e):
        nonlocal current_exchange
        current_exchange = e.control.value
        # обновляем отображение названия
        exchange_display = {
            "bybit": "Bybit",
            "gateio": "Gate.io",
            "mexc": "MEXC"
        }.get(current_exchange, current_exchange.upper())
        load_symbols(current_exchange)
        update_available()
        page.update()

    def on_symbol_changed(value):
        nonlocal current_symbol, coin_name
        current_symbol = value
        coin_name = current_symbol.split("/")[0]
        # обновляем суффикс поля количества
        quantity_field.suffix_text = coin_name if side_selector_value == 'sell' else 'USDT'
        # данные из базы
        info = query_pair_info(current_exchange, current_symbol)
        if info:
            price_value.value = f"${info.get('current_price', 0):,.2f}"
            change_label.value = f"{info.get('change_24h_percent', 0):+.2f}%"
            high_label.value = f"${info.get('high_24h', 0):,.2f}"
            low_label.value = f"${info.get('low_24h', 0):,.2f}"
            volume_label.value = f"${info.get('volume_24h', 0):,.0f}"
            maker_fee_label.value = f"{info.get('maker_fee', 0):.6f}%"
            taker_fee_label.value = f"{info.get('taker_fee', 0):.6f}%"
            min_order_label.value = f"{info.get('min_order_amount', 0)}"
            lot_size_label.value = f"{info.get('lot_size', 0)}"
        else:
            # если в БД нет данных, можно запросить цену по API как запасной вариант
            success, curr = get_current_price(current_exchange, current_symbol, "", "")
            if success:
                price_value.value = f"${curr.get('last',0):,.2f}"
                change_label.value = ""
                high_label.value = f"${curr.get('high',0):,.2f}"
                low_label.value = f"${curr.get('low',0):,.2f}"
                volume_label.value = ""
            maker_fee_label.value = "?"
            taker_fee_label.value = "?"
            min_order_label.value = "?"
            lot_size_label.value = "?"
        update_action_button()
        update_available()
        page.update()

    def update_available():
        if side_selector_value == 'sell':
            bal = query_balance(current_exchange, coin_name)
            label_asset = coin_name
        else:
            bal = query_balance(current_exchange, 'USDT')
            label_asset = 'USDT'
        # balance query may return None values for fields, ensure we format safely
        avail = 0
        if bal:
            # bal.get could return None if the DB row has NULL
            avail = bal.get('free')
            if avail is None:
                avail = 0
        available_text.value = f"{avail:.6f} {label_asset}"
        page.update()

    # dropdownы
    exchange_dropdown = ft.Dropdown(
        width=180,
        options=[
            ft.dropdown.Option(k.exchange_name,
                               text=EXCHANGE_NAMES.get(k.exchange_name, k.exchange_name.upper()))
            for k in user_keys
        ],
        value=initial_exchange,
        on_change=on_exchange_changed,
    )
    symbol_dropdown = ft.Dropdown(
        width=180,
        options=[],
        value=initial_symbol,
        on_change=lambda e: on_symbol_changed(e.control.value),
    )

    # начальную загрузку символов выполним ниже, после создания полей ввода

    # строка выбора и отображения
    exchange_selector = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("БИРЖА", size=10, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(height=5),
                exchange_dropdown,
            ], spacing=0),
            ft.Container(width=15),
            ft.Column([
                ft.Text("ТОРГОВАЯ ПАРА", size=10, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(height=5),
                symbol_dropdown,
            ], spacing=0),
            ft.Container(width=15),
            ft.Column([
                ft.Text("Доступно:", size=12, color=TEXT_SECONDARY),
                available_text,
            ], spacing=0),
            ft.Container(width=15),
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
    # динамические поля для отображения из БД или API
    price_value = ft.Text("$0.00", size=42, weight="bold", color=SUCCESS_COLOR)
    change_label = ft.Text("0.00%", size=16, color=SUCCESS_COLOR, weight="bold")
    high_label = ft.Text("$0.00", size=18, weight="bold", color=TEXT_PRIMARY)
    low_label = ft.Text("$0.00", size=18, weight="bold", color=TEXT_PRIMARY)
    volume_label = ft.Text("$0", size=18, weight="bold", color=PRIMARY_COLOR)
    maker_fee_label = ft.Text("0.00%", size=12, color=TEXT_SECONDARY)
    taker_fee_label = ft.Text("0.00%", size=12, color=TEXT_SECONDARY)
    min_order_label = ft.Text("0", size=12, color=TEXT_SECONDARY)
    lot_size_label = ft.Text("0", size=12, color=TEXT_SECONDARY)

    price_info = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("ТЕКУЩАЯ ЦЕНА", size=11, color=TEXT_SECONDARY, weight="bold"),
                        ft.Container(height=10),
                        ft.Row([
                            ft.Text("$", size=28, color=SUCCESS_COLOR, weight="bold"),
                            price_value,
                        ], spacing=3, vertical_alignment="end"),
                        ft.Container(height=8),
                        ft.Row([
                            ft.Icon(ft.icons.TRENDING_UP, size=22, color=SUCCESS_COLOR),
                            change_label,
                            ft.Text("за 24ч", size=13, color=TEXT_SECONDARY),
                        ], spacing=8),
                    ], spacing=0),
                    expand=2,
                ),
                ft.Container(
                    content=ft.VerticalDivider(width=1, color=BORDER_COLOR),
                    height=100,
                    padding=ft.padding.symmetric(horizontal=20),
                ),
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text("24ч МАКС", size=11, color=TEXT_SECONDARY, weight="bold"),
                            ft.Container(height=5),
                            high_label,
                        ], spacing=0, horizontal_alignment="center"),
                        ft.Container(width=30),
                        ft.Column([
                            ft.Text("24ч МИН", size=11, color=TEXT_SECONDARY, weight="bold"),
                            ft.Container(height=5),
                            low_label,
                        ], spacing=0, horizontal_alignment="center"),
                        ft.Container(width=30),
                        ft.Column([
                            ft.Text("ОБЪЁМ", size=11, color=TEXT_SECONDARY, weight="bold"),
                            ft.Container(height=5),
                            volume_label,
                        ], spacing=0, horizontal_alignment="center"),
                    ], alignment="center"),
                    expand=3,
                ),
            ], vertical_alignment="center"),
            # дополнительная техническая информация
            ft.Container(height=15),
            ft.Row([
                ft.Column([
                    ft.Text("Maker", size=11, color=TEXT_SECONDARY, weight="bold"),
                    maker_fee_label,
                ], spacing=0, horizontal_alignment="center"),
                ft.Container(width=20),
                ft.Column([
                    ft.Text("Taker", size=11, color=TEXT_SECONDARY, weight="bold"),
                    taker_fee_label,
                ], spacing=0, horizontal_alignment="center"),
                ft.Container(width=20),
                ft.Column([
                    ft.Text("Мин. ордер", size=11, color=TEXT_SECONDARY, weight="bold"),
                    min_order_label,
                ], spacing=0, horizontal_alignment="center"),
                ft.Container(width=20),
                ft.Column([
                    ft.Text("Лот", size=11, color=TEXT_SECONDARY, weight="bold"),
                    lot_size_label,
                ], spacing=0, horizontal_alignment="center"),
            ], alignment="center"),
        ]),
        padding=25,
        bgcolor=ft.colors.with_opacity(0.05, SUCCESS_COLOR),
        border_radius=12,
        border=ft.border.all(1, ft.colors.with_opacity(0.25, SUCCESS_COLOR)),
    )
    
    # ==================== ПЕРЕКЛЮЧАТЕЛЬ КУПИТЬ/ПРОДАТЬ ====================
    def set_side(new_side):
        nonlocal buy_active, sell_active, side_selector_value, action_color
        buy_active = new_side == 'buy'
        sell_active = new_side == 'sell'
        side_selector_value = new_side
        action_color = BUY_COLOR if buy_active else SELL_COLOR
        # обновляем стиль кнопок
        buy_btn.bgcolor = BUY_COLOR if buy_active else ft.colors.with_opacity(0.1, BUY_COLOR)
        # icon is first control, text is third
        buy_btn.content.controls[0].color = DARK_BG if buy_active else BUY_COLOR
        buy_btn.content.controls[2].color = DARK_BG if buy_active else BUY_COLOR
        sell_btn.bgcolor = SELL_COLOR if sell_active else ft.colors.with_opacity(0.1, SELL_COLOR)
        sell_btn.content.controls[0].color = DARK_BG if sell_active else SELL_COLOR
        sell_btn.content.controls[2].color = DARK_BG if sell_active else SELL_COLOR
        # обновляем суффикс поля количества
        try:
            quantity_field.suffix_text = coin_name if sell_active else 'USDT'
        except NameError:
            # quantity_field may not be initialized yet during startup
            pass
        # these helper functions might not be defined yet when set_side is
        # invoked during the initial dialog setup, so guard against NameError.
        try:
            update_available()
        except NameError:
            pass
        try:
            update_summary()
        except NameError:
            pass
        try:
            update_action_button()
        except NameError:
            pass
        page.update()

    # кнопки, которые будут изменяться
    buy_btn = ft.Container(
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
        on_click=lambda e: set_side('buy'),
    )
    sell_btn = ft.Container(
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
        on_click=lambda e: set_side('sell'),
    )
    side_selector = ft.Container(
        content=ft.Row([buy_btn, sell_btn], spacing=0),
    )
    # начальную сторону будем назначать позже, после создания всех элементов
    # (особенно update_summary, иначе возможны ошибки при первом вызове)
    # set_side(initial_side)  # moved further down
    
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
                    # will be updated by set_order_type
                    bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                    border_radius=12,
                    border=ft.border.all(1, BORDER_COLOR),
                    alignment=ft.alignment.center,
                    ink=True,
                    on_click=lambda e: set_order_type('market'),
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
                    on_click=lambda e: set_order_type('limit'),
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
                    on_click=lambda e: set_order_type('stop-limit'),
                ),
            ]),
        ]),
        padding=25,
        bgcolor=CARD_BG,
        border_radius=12,
        border=ft.border.all(1, BORDER_COLOR),
    )
    
    # ==================== ФОРМА ВВОДА ====================
    # поле ввода количества, сохраняем для последующего чтения
    def quantity_changed(e):
        clear_percent_highlight()
        update_summary()

    quantity_field = ft.TextField(
        value="0.001",
        expand=True,
        height=60,
        bgcolor=INPUT_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        text_size=20,
        text_align="right",
        suffix_text=coin_name,
        content_padding=ft.padding.symmetric(horizontal=20, vertical=15),
        on_change=quantity_changed,
    )

    # поля цены для лимитных ордеров
    price_field = ft.TextField(
        value="",
        hint_text="Цена",
        expand=True,
        height=50,
        visible=False,
        bgcolor=INPUT_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        text_size=16,
        text_align="right",
        content_padding=ft.padding.symmetric(horizontal=12, vertical=12),
        on_change=lambda e: update_summary(),
    )

    stop_price_field = ft.TextField(
        value="",
        hint_text="Стоп-цена",
        expand=True,
        height=50,
        visible=False,
        bgcolor=INPUT_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        text_size=16,
        text_align="right",
        content_padding=ft.padding.symmetric(horizontal=12, vertical=12),
        on_change=lambda e: update_summary(),
    )

    input_form = ft.Container(
        content=ft.Column([
            # Количество
            ft.Row([
                ft.Text("КОЛИЧЕСТВО", size=11, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(expand=True),
                ft.Text("Доступно: ", size=12, color=TEXT_SECONDARY),
                available_text,
            ]),
            # кнопки выбора типа ордера — вынесены в переменные для подсветки
            ft.Row([
                (market_btn := ft.Container(
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
                    border=ft.border.all(1, BORDER_COLOR),
                    alignment=ft.alignment.center,
                    ink=True,
                    on_click=lambda e: set_order_type('market'),
                )),
                ft.Container(width=15),
                (limit_btn := ft.Container(
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
                    on_click=lambda e: set_order_type('limit'),
                )),
                ft.Container(width=15),
                (stop_btn := ft.Container(
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
                    on_click=lambda e: set_order_type('stop-limit'),
                )),
            ]),
        border_radius=12,
        border=ft.border.all(1, BORDER_COLOR),
    )
    
    # ==================== ИТОГОВЫЙ РАСЧЁТ ====================
    # динамические поля в сводке
    qty_summary = ft.Text("0.000 BTC", size=14, color=TEXT_PRIMARY, weight="bold")
    price_summary = ft.Text("$0.00", size=14, color=TEXT_PRIMARY, weight="bold")
    commission_summary = ft.Text("$0.00", size=14, color=WARNING_COLOR, weight="bold")
    total_summary = ft.Text("$0.00", size=36, color=action_color, weight="bold")
    total_equiv = ft.Text("≈ 0.000 BTC", size=13, color=TEXT_SECONDARY)

    def update_summary():
        try:
            qty = float(quantity_field.value or 0)
        except:
            qty = 0.0
        price = 0.0
        try:
            # выбираем цену в зависимости от типа ордера
            if order_type in ('limit', 'stop-limit') and price_field.value:
                price = float(price_field.value.replace(',','') or 0)
            else:
                price = float(price_value.value.replace('$','').replace(',','') or 0)
        except:
            price = 0.0
        total = qty * price
        commission = abs(total) * 0.001
        qty_summary.value = f"{qty:.6f} {coin_name}"
        price_summary.value = f"${price:,.2f}"
        commission_summary.value = f"${commission:,.2f}"
        total_summary.value = f"${(total + commission if buy_active else total - commission):,.2f}"
        total_equiv.value = f"≈ {qty:.6f} {coin_name}"
        page.update()

    def set_order_type(new_type: str):
        nonlocal order_type
        order_type = new_type
        # показываем/скрываем поля цены
        price_field.visible = (order_type in ('limit', 'stop-limit'))
        stop_price_field.visible = (order_type == 'stop-limit')
        # подсветка выбранной кнопки
        try:
            # reset defaults
            market_btn.bgcolor = ft.colors.with_opacity(0.1, PRIMARY_COLOR)
            market_btn.content.controls[0].color = PRIMARY_COLOR
            market_btn.content.controls[2].color = TEXT_PRIMARY
            limit_btn.bgcolor = ft.colors.with_opacity(0.03, TEXT_SECONDARY)
            limit_btn.content.controls[0].color = TEXT_SECONDARY
            limit_btn.content.controls[2].color = TEXT_PRIMARY
            stop_btn.bgcolor = ft.colors.with_opacity(0.03, TEXT_SECONDARY)
            stop_btn.content.controls[0].color = TEXT_SECONDARY
            stop_btn.content.controls[2].color = TEXT_PRIMARY
            if order_type == 'market':
                market_btn.bgcolor = PRIMARY_COLOR
                market_btn.content.controls[0].color = DARK_BG
                market_btn.content.controls[2].color = DARK_BG
            elif order_type == 'limit':
                limit_btn.bgcolor = PRIMARY_COLOR
                limit_btn.content.controls[0].color = DARK_BG
                limit_btn.content.controls[2].color = DARK_BG
            elif order_type == 'stop-limit':
                stop_btn.bgcolor = PRIMARY_COLOR
                stop_btn.content.controls[0].color = DARK_BG
                stop_btn.content.controls[2].color = DARK_BG
        except NameError:
            pass
        # обновляем UI
        update_action_button()
        update_summary()
        page.update()

    def percent_select(pct: float):
        try:
            if side_selector_value == 'sell':
                bal = query_balance(current_exchange, coin_name)
                avail = float(bal.get('free') or 0) if bal else 0.0
                amount = avail * pct
            else:
                bal = query_balance(current_exchange, 'USDT')
                avail = float(bal.get('free') or 0) if bal else 0.0
                # используем текущую цену для расчёта количества монет
                try:
                    price = float(price_value.value.replace('$','').replace(',','') or 0)
                except:
                    succ, curr = get_current_price(current_exchange, current_symbol, "", "")
                    price = curr.get('last', 0) if succ else 0
                if not price or price == 0:
                    show_status("Не удалось получить цену для расчёта", "error")
                    return
                amount = (avail or 0) * pct / price
            quantity_field.value = f"{amount:.6f}"
        except Exception as e:
            logger.error(f"[TRADING] Ошибка расчёта процента: {e}")
        # подсветим выбранную кнопку процента
        try:
            clear_percent_highlight()
            if pct == 0.25:
                pct25_btn.bgcolor = PRIMARY_COLOR
                pct25_btn.content.color = DARK_BG
            elif pct == 0.5:
                pct50_btn.bgcolor = PRIMARY_COLOR
                pct50_btn.content.color = DARK_BG
            elif pct == 0.75:
                pct75_btn.bgcolor = PRIMARY_COLOR
                pct75_btn.content.color = DARK_BG
            elif pct == 1.0:
                pctMax_btn.bgcolor = ft.colors.with_opacity(0.35, PRIMARY_COLOR)
                pctMax_btn.content.color = DARK_BG
        except NameError:
            pass
        update_summary()
        page.update()

    def clear_percent_highlight():
        try:
            pct25_btn.bgcolor = INPUT_BG
            pct25_btn.content.color = TEXT_SECONDARY
            pct50_btn.bgcolor = INPUT_BG
            pct50_btn.content.color = TEXT_SECONDARY
            pct75_btn.bgcolor = INPUT_BG
            pct75_btn.content.color = TEXT_SECONDARY
            pctMax_btn.bgcolor = ft.colors.with_opacity(0.15, PRIMARY_COLOR)
            pctMax_btn.content.color = PRIMARY_COLOR
        except NameError:
            pass

    summary = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Text("ДЕТАЛИ ОРДЕРА", size=11, color=TEXT_SECONDARY, weight="bold"),
                    ft.Container(height=15),
                    ft.Row([
                        ft.Text("Количество", size=14, color=TEXT_SECONDARY),
                        ft.Container(expand=True),
                        qty_summary,
                    ]),
                    ft.Container(height=10),
                    ft.Row([
                        ft.Text("Цена исполнения", size=14, color=TEXT_SECONDARY),
                        ft.Container(expand=True),
                        price_summary,
                    ]),
                    ft.Container(height=10),
                    ft.Row([
                        ft.Text("Комиссия (0.1%)", size=14, color=TEXT_SECONDARY),
                        ft.Container(expand=True),
                        commission_summary,
                    ]),
                ], spacing=0),
                expand=True,
            ),
            ft.Container(
                content=ft.VerticalDivider(width=1, color=BORDER_COLOR),
                height=120,
                padding=ft.padding.symmetric(horizontal=25),
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("ИТОГО К ОПЛАТЕ", size=11, color=TEXT_SECONDARY, weight="bold"),
                    ft.Container(height=10),
                    total_summary,
                    ft.Container(height=5),
                    total_equiv,
                ], horizontal_alignment="center", spacing=0),
                width=180,
            ),
        ], vertical_alignment="center"),
        padding=25,
        bgcolor=ft.colors.with_opacity(0.05, action_color),
        border_radius=12,
        border=ft.border.all(1, ft.colors.with_opacity(0.3, action_color)),
    )
    # первоначальный расчет
    update_summary()
    
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
    # helper для обновления кнопки после изменения состояния
    action_button = None
    def update_action_button():
        if not action_button:
            return
        # иконка
        icon_ctrl = action_button.content.controls[0]
        text_ctrl = action_button.content.controls[2]
        icon_ctrl.icon = ft.icons.ARROW_DOWNWARD_ROUNDED if buy_active else ft.icons.ARROW_UPWARD_ROUNDED
        text_ctrl.value = f"{('КУПИТЬ' if buy_active else 'ПРОДАТЬ')} {coin_name}"
        action_button.bgcolor = action_color
        action_button.shadow.color = ft.colors.with_opacity(0.5, action_color)
        page.update()

    def execute_order(e):
        # собираем параметры для отправки через backend.api.create_order
        symbol = current_symbol
        amount_str = quantity_field.value or "0"
        try:
            amount = float(amount_str)
        except:
            show_status("Неверное количество", "error")
            return
        price = None
        # если выбран лимитный тип, пробуем взять значение из summary (или другое поле)
        order_type = 'market'  # пока ограничимся рыночным
        # находим API ключ
        key = None
        for k in user_keys:
            if k.exchange_name == current_exchange:
                key = k
                break
        if not key:
            show_status("API ключ для биржи не найден", "error")
            return
        success, result = create_order(
            current_exchange, symbol, side_selector_value, order_type,
            amount, price,
            key.api_key, key.secret_key, getattr(key, 'passphrase', None)
        )
        if success:
            show_status("Ордер отправлен", "success")
            logger.info(f"[TRADING] Ордер {side_selector_value} {amount} {symbol} на {current_exchange}")
            # после отправки ордера стараемся обновить доступные средства из БД
            update_available()
            update_summary()
        else:
            show_status(str(result), "error")

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
        on_click=execute_order,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=25,
            color=ft.colors.with_opacity(0.5, action_color),
        ),
    )
    # обновим кнопку после создания
    update_action_button()
    # установить стартовое состояние бокового переключателя теперь, когда
    # и update_summary, и update_action_button доступны
    set_side(initial_side)
    
    # после объявления всех элементов логики, загружаем символы
    load_symbols(initial_exchange)

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
            width=910,
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
