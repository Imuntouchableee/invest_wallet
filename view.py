import sqlite3
import flet as ft
import matplotlib
matplotlib.use("Agg")       # переключаемся на безголовый бекенд
import matplotlib.pyplot as plt
import os
import threading
import hashlib
from flet import Image
from models import User, Asset, PortfolioHistory
from models import session, engine, Session
from api import mainn, fetch_last_20_prices
from ml import predict_future_price
from portfolio_chart_handler import create_portfolio_chart, get_chart_stats
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from email_service import generate_recovery_code, send_recovery_email_mock, verify_recovery_code, get_code_expiry_time
data = {}
user_name = str()

top_25_expensive_coins = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT'
]


# Проверка пользователя в базе
def check_user(name, password):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name = ? AND password = ?", (name, password))
    user = cursor.fetchone()
    conn.close()
    return user


# Добавление нового пользователя
def add_user(name, password):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name, password) VALUES (?, ?)", (name, password))
    conn.commit()
    conn.close()


# Flet-приложение
def main(page: ft.Page):
    data = mainn()
    page.title = "Invest Wallet"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    
    # Кибер-панк тема с неоновыми акцентами
    page.bgcolor = "#0a0e17"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.min_width = 1200
    page.window.min_height = 800
    page.window.maximized = True  # Запуск во весь экран

    # Цветовая палитра - "Киберпанк/Блокчейн"
    PRIMARY_COLOR = "#00d4ff"      # Неоновый циан (основной)
    SECONDARY_COLOR = "#00ff88"    # Неоновый зеленый (рост)
    ACCENT_COLOR = "#ff3366"       # Ярко-коралловый (опасность)
    SUCCESS_COLOR = "#00ff88"      # Неоновый зеленый (положительные значения)
    DARK_BG = "#0a0e17"            # Почти черный с синеватым оттенком
    CARD_BG = "#121828"            # Фон карточек (темнее)
    CARD_BG_ALT = "#1a2236"        # Альтернативный фон карточек
    TEXT_PRIMARY = "#ffffff"       # Белый (основной текст)
    TEXT_SECONDARY = "#8a93a7"     # Серо-голубой (вторичный)
    TEXT_ACCENT = "#cbd5e0"        # Выделенный текст
    BORDER_COLOR = "#1a2236"       # Цвет границ

    # Поля для входа
    login_username_field = ft.TextField(
        label="Имя пользователя",
        width=350,
        bgcolor=CARD_BG,
        border_color=PRIMARY_COLOR,
        focused_border_color=SECONDARY_COLOR,
        label_style=ft.TextStyle(color=TEXT_SECONDARY),
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
        prefix_icon=ft.icons.PERSON,
    )
    login_password_field = ft.TextField(
        label="Пароль",
        width=350,
        password=True,
        bgcolor=CARD_BG,
        border_color=PRIMARY_COLOR,
        focused_border_color=SECONDARY_COLOR,
        label_style=ft.TextStyle(color=TEXT_SECONDARY),
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
        prefix_icon=ft.icons.LOCK,
    )
    login_button = ft.ElevatedButton(
        text="ВОЙТИ",
        width=350,
        height=50,
        style=ft.ButtonStyle(
            bgcolor=PRIMARY_COLOR,
            color=DARK_BG,
            text_style=ft.TextStyle(size=16, weight="bold", color=DARK_BG),
            padding=ft.padding.symmetric(vertical=12),
            shape=ft.RoundedRectangleBorder(radius=8),
            shadow_color=PRIMARY_COLOR,
        ),
        on_click=lambda e: login_user()
    )
    go_to_register_button = ft.TextButton(
        text="Создать аккаунт",
        style=ft.ButtonStyle(color=PRIMARY_COLOR),
        on_click=lambda e: show_register_screen()
    )

    # Поля для регистрации
    register_username_field = ft.TextField(
        label="Имя пользователя",
        width=350,
        bgcolor=CARD_BG,
        border_color=PRIMARY_COLOR,
        focused_border_color=SECONDARY_COLOR,
        label_style=ft.TextStyle(color=TEXT_SECONDARY),
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
        prefix_icon=ft.icons.PERSON,
    )
    register_password_field = ft.TextField(
        label="Пароль",
        width=350,
        password=True,
        bgcolor=CARD_BG,
        border_color=PRIMARY_COLOR,
        focused_border_color=SECONDARY_COLOR,
        label_style=ft.TextStyle(color=TEXT_SECONDARY),
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
        prefix_icon=ft.icons.LOCK,
    )
    register_button = ft.ElevatedButton(
        text="ЗАРЕГИСТРИРОВАТЬСЯ",
        width=350,
        height=50,
        style=ft.ButtonStyle(
            bgcolor=PRIMARY_COLOR,
            color=DARK_BG,
            text_style=ft.TextStyle(size=16, weight="bold", color=DARK_BG),
            padding=ft.padding.symmetric(vertical=12),
            shape=ft.RoundedRectangleBorder(radius=8),
            shadow_color=PRIMARY_COLOR,
        ),
        on_click=lambda e: register_user()
    )
    back_to_login_button = ft.TextButton(
        text="Вернуться ко входу",
        style=ft.ButtonStyle(color=PRIMARY_COLOR),
        on_click=lambda e: show_login_screen()
    )

    # Профиль
    def show_profile(page: ft.Page, name):
        user = session.query(User).filter(User.name == name).first()
        
        # Обновляем last_login
        from datetime import datetime
        user.last_login = datetime.now()
        
        assets = session.query(Asset).filter(Asset.user_id == user.id).all()
        
        # Инициализируем все None значения
        if user.balance is None:
            user.balance = 0
        if user.total_profit is None:
            user.total_profit = 0.0
        if user.total_invested is None:
            user.total_invested = 0.0
        if user.total_trades is None:
            user.total_trades = 0
        if user.full_name is None:
            user.full_name = "Активный инвестор"
        if user.avatar_color is None:
            user.avatar_color = PRIMARY_COLOR
        if user.country is None:
            user.country = "Россия"
        if user.portfolio_value is None:
            user.portfolio_value = sum(a.value_rub for a in assets)
        if user.previous_portfolio_value is None:
            user.previous_portfolio_value = user.portfolio_value
        
        session.commit()

        def show_snack_bar(message, color=SUCCESS_COLOR, icon=ft.icons.CHECK_CIRCLE):
            """Показывает уведомление (snack bar)"""
            snack_bar = ft.SnackBar(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, size=20, color=color),
                        ft.Text(message, color=TEXT_PRIMARY, size=14),
                    ], spacing=10),
                    padding=10,
                ),
                bgcolor=CARD_BG,
                duration=3000,
            )
            page.overlay.append(snack_bar)
            snack_bar.open = True
            page.update()

        def delete_asset(asset_id):
            asset_to_delete = session.query(Asset).filter(Asset.id == asset_id).first()
            if asset_to_delete:
                session.delete(asset_to_delete)
                session.commit()
                show_profile(page, name)  # Перезагрузить профиль после удаления

        def add_asset():
            # Переменная для сообщения об ошибке
            error_message = ft.Text("", color=ACCENT_COLOR, visible=False, weight="bold")

            # Функция для пересчета количества монет
            def update_quantity(e):
                try:
                    selected_coin = asset_name_dropdown.value
                    selected_exchange = exchange_dropdown.value
                    entered_amount = float(asset_value_field.value)

                    if not selected_coin or not selected_exchange:
                        return

                    # Цена монеты с выбранной биржи
                    coin_price = data[selected_coin][selected_exchange]
                    calculated_quantity = entered_amount / coin_price

                    # Обновляем поле с количеством
                    asset_quantity_field.value = f"{calculated_quantity:.6f}"
                    page.update()

                except ValueError:
                    # Игнорируем ошибку, если поле пустое
                    pass

            # Функция для добавления актива
            def validate_and_confirm(e):
                try:
                    new_asset_name = asset_name_dropdown.value
                    new_exchange = exchange_dropdown.value
                    new_asset_quantity = float(asset_quantity_field.value)
                    new_asset_value = float(asset_value_field.value)

                    if new_asset_value <= 0:
                        error_message.value = "Сумма должна быть больше 0 долларов."
                        error_message.visible = True
                        page.update()
                        return

                    elif new_asset_quantity <= 0:
                        error_message.value = "Количество должно быть больше 0."
                        error_message.visible = True
                        page.update()
                        return

                    total_cost = new_asset_quantity * data[new_asset_name][new_exchange]

                    if total_cost > user.balance:
                        error_message.value = "Недостаточно средств на балансе для покупки."
                        error_message.visible = True
                        page.update()
                        return

                    # Все проверки пройдены — добавляем актив
                    new_asset = Asset(
                        user_id=user.id,
                        coin_name=new_asset_name,
                        quantity=new_asset_quantity,
                        value_rub=new_asset_value,
                    )
                    session.add(new_asset)
                    user.balance -= total_cost
                    
                    # Обновляем статистику пользователя
                    user.total_invested = (user.total_invested or 0) + total_cost
                    user.total_trades = (user.total_trades or 0) + 1
                    
                    session.commit()

                    show_profile(page, name)
                except ValueError:
                    error_message.value = "Пожалуйста, введите корректные значения."
                    error_message.visible = True
                    page.update()

            # Выпадающий список для выбора монеты
            asset_name_dropdown = ft.Dropdown(
                options=[ft.dropdown.Option(coin) for coin in data.keys()],
                hint_text="Выберите монету",
                prefix_icon=ft.icons.CURRENCY_BITCOIN,
                bgcolor=CARD_BG,
                border_color=PRIMARY_COLOR,
                focused_border_color=SECONDARY_COLOR,
                on_change=update_quantity,
            )

            # Выпадающий список для выбора биржи
            exchange_dropdown = ft.Dropdown(
                options=[ft.dropdown.Option(exchange) for exchange in list(data.values())[0].keys()],
                hint_text="Выберите биржу",
                prefix_icon=ft.icons.ACCOUNT_BALANCE,
                bgcolor=CARD_BG,
                border_color=PRIMARY_COLOR,
                focused_border_color=SECONDARY_COLOR,
                on_change=update_quantity,
            )

            # Поле для ввода суммы
            asset_value_field = ft.TextField(
                label="Инвестировать",
                hint_text="Введите сумму в $",
                prefix_icon=ft.icons.ATTACH_MONEY,
                bgcolor=CARD_BG,
                border_color=PRIMARY_COLOR,
                focused_border_color=SECONDARY_COLOR,
                label_style=ft.TextStyle(color=TEXT_SECONDARY, size=12),
                text_style=ft.TextStyle(color=TEXT_PRIMARY),
                on_change=update_quantity,
            )

            # Поле для автоматического расчета количества
            asset_quantity_field = ft.TextField(
                label="Получите монет",
                read_only=True,
                prefix_icon=ft.icons.TRENDING_UP,
                bgcolor=CARD_BG,
                border_color=SECONDARY_COLOR,
                label_style=ft.TextStyle(color=TEXT_SECONDARY, size=12),
                text_style=ft.TextStyle(color=SECONDARY_COLOR, weight="bold"),
            )

            # Информационный блок
            info_block = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=18, color=TEXT_SECONDARY),
                        ft.Text("Баланс:", size=12, color=TEXT_SECONDARY, weight="500"),
                        ft.Text(f"${round(user.balance, 2)}", size=13, color=SUCCESS_COLOR, weight="bold"),
                    ], spacing=10, vertical_alignment="center"),
                ], spacing=0),
                padding=10,
                bgcolor=ft.colors.with_opacity(0.1, SUCCESS_COLOR),
                border_radius=8,
                border=ft.border.all(1, BORDER_COLOR),
            )

            # Кнопка подтверждения
            confirm_button = ft.ElevatedButton(
                text="КУПИТЬ АКТИВ",
                style=ft.ButtonStyle(
                    bgcolor=SUCCESS_COLOR,
                    color=TEXT_PRIMARY,
                    text_style=ft.TextStyle(size=14, weight="bold"),
                    padding=ft.padding.symmetric(horizontal=30, vertical=12),
                ),
                on_click=validate_and_confirm,
            )

            # Отображение интерфейса в диалоговом окне
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ADD_CIRCLE, size=28, color=SUCCESS_COLOR),
                        ft.Text("Добавить актив", size=22, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=10),
                    padding=10,
                ),
                content=ft.Column(
                    [
                        ft.Text("Выберите монету", size=12, color=TEXT_SECONDARY, weight="500"),
                        asset_name_dropdown,
                        
                        ft.Container(height=5),
                        ft.Text("Выберите биржу", size=12, color=TEXT_SECONDARY, weight="500"),
                        exchange_dropdown,
                        
                        ft.Container(height=5),
                        ft.Text("Сумма инвестиции", size=12, color=TEXT_SECONDARY, weight="500"),
                        asset_value_field,
                        
                        ft.Container(height=5),
                        ft.Text("Расчётное количество", size=12, color=TEXT_SECONDARY, weight="500"),
                        asset_quantity_field,
                        
                        info_block,
                        error_message,
                    ],
                    tight=True,
                    spacing=10,
                ),
                actions=[
                    ft.TextButton(
                        "Отмена",
                        style=ft.ButtonStyle(color=SECONDARY_COLOR),
                        on_click=lambda e: (setattr(dialog, 'open', False), page.update()),
                    ),
                    confirm_button,
                ],
                actions_alignment="end",
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=12),
            )

            page.overlay.append(dialog)
            dialog.open = True
            dialog.open = True
            page.update()

        def sell_asset(asset_id):
            asset = session.query(Asset).filter(Asset.id == asset_id).first()

            if not asset:
                snack_bar = ft.SnackBar(ft.Text("Актива не существует!", color=ACCENT_COLOR))
                page.overlay.append(snack_bar)
                snack_bar.open = True
                return

            def confirm_sell_asset(e):
                sell_quantity = float(sell_quantity_slider.value)
                if sell_quantity >= asset.quantity:
                    # Если продаём все - добавляем всю стоимость в баланс
                    user.balance += asset.value_rub
                    session.delete(asset)
                else:
                    # Если продаём часть - добавляем пропорциональную стоимость
                    sell_cost = sell_quantity * (asset.value_rub / asset.quantity)
                    user.balance += sell_cost
                    asset.quantity -= sell_quantity
                
                session.commit()
                # Закрыть диалог и обновить профиль
                dialog.open = False
                page.update()
                # Пересчитываем данные и обновляем главное окно
                rebuild_asset_list()
                show_snack_bar("✓ Актив успешно продан!")

            def close_dialog():
                dialog.open = False
                page.update()

            def update_quantity_display(e):
                sell_qty = float(sell_quantity_slider.value)
                sell_cost = sell_qty * (asset.value_rub / asset.quantity)
                quantity_display.value = f"{sell_qty:.6f}"
                cost_display.value = f"${sell_cost:.2f}"
                page.update()

            # Ползунок для выбора количества с отображением значения
            sell_quantity_slider = ft.Slider(
                min=0,
                max=asset.quantity,
                value=asset.quantity / 2,  # По умолчанию половина
                divisions=100,
                on_change=update_quantity_display,
            )

            # Текст для отображения текущего количества
            sell_qty_default = asset.quantity / 2
            sell_cost_default = sell_qty_default * (asset.value_rub / asset.quantity)
            
            quantity_display = ft.Text(
                f"{sell_qty_default:.6f}",
                size=20,
                weight="bold",
                color=PRIMARY_COLOR,
            )

            cost_display = ft.Text(
                f"${sell_cost_default:.2f}",
                size=20,
                weight="bold",
                color=SUCCESS_COLOR,
            )

            # Отобразить модальное окно
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.SELL, size=28, color=PRIMARY_COLOR),
                        ft.Text("Продажа актива", size=22, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=10),
                    padding=10,
                ),
                content=ft.Column([
                    # Информация об активе
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=20, color=SECONDARY_COLOR),
                                ft.Text("Монета:", size=13, color=TEXT_SECONDARY, weight="500"),
                                ft.Text(asset.coin_name, size=14, color=TEXT_PRIMARY, weight="bold"),
                            ], spacing=10, vertical_alignment="center"),
                            ft.Row([
                                ft.Icon(ft.icons.PERCENT, size=20, color=SECONDARY_COLOR),
                                ft.Text("Доступно:", size=13, color=TEXT_SECONDARY, weight="500"),
                                ft.Text(f"{asset.quantity:.6f}", size=14, color=TEXT_PRIMARY, weight="bold"),
                            ], spacing=10, vertical_alignment="center"),
                            ft.Row([
                                ft.Icon(ft.icons.ATTACH_MONEY, size=20, color=SUCCESS_COLOR),
                                ft.Text("Стоимость:", size=13, color=TEXT_SECONDARY, weight="500"),
                                ft.Text(f"${asset.value_rub:.2f}", size=14, color=SUCCESS_COLOR, weight="bold"),
                            ], spacing=10, vertical_alignment="center"),
                        ], spacing=10),
                        padding=15,
                        bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                        border_radius=10,
                        border=ft.border.all(1, PRIMARY_COLOR),
                    ),
                    ft.Container(height=15),
                    
                    # Ползунок продажи
                    ft.Text("Выберите количество для продажи", size=13, color=TEXT_SECONDARY, weight="500"),
                    sell_quantity_slider,
                    
                    # Отображение выбранного количества и стоимости
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text("Продаёте:", size=13, color=TEXT_SECONDARY, weight="500"),
                                quantity_display,
                            ], alignment="spaceBetween"),
                            ft.Row([
                                ft.Text("Получите:", size=13, color=TEXT_SECONDARY, weight="500"),
                                cost_display,
                            ], alignment="spaceBetween"),
                        ], spacing=8),
                        padding=12,
                        bgcolor=CARD_BG,
                        border_radius=8,
                        border=ft.border.all(1, BORDER_COLOR),
                    ),
                ], spacing=12),
                actions=[
                    ft.TextButton(
                        "Отмена",
                        style=ft.ButtonStyle(color=SECONDARY_COLOR),
                        on_click=lambda e: close_dialog(),
                    ),
                    ft.ElevatedButton(
                        "ПРОДАТЬ",
                        style=ft.ButtonStyle(
                            bgcolor=PRIMARY_COLOR,
                            color=TEXT_PRIMARY,
                            text_style=ft.TextStyle(size=14, weight="bold"),
                            padding=ft.padding.symmetric(horizontal=30, vertical=10),
                        ),
                        on_click=confirm_sell_asset,
                    ),
                ],
                actions_alignment="end",
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=12),
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def logout():
            show_login_screen()

        def open_logout_dialog():
            # Модальное окно подтверждения выхода
            def confirm_logout(e):
                close_dialog()
                logout()

            def close_dialog():
                # Dialog closing
                    dialog.open = False
                    page.update()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.LOGOUT, size=28, color=ACCENT_COLOR),
                        ft.Text("Выход из профиля", size=22, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=10),
                    padding=10,
                ),
                content=ft.Text(
                    "Вы действительно хотите выйти из аккаунта?",
                    size=16,
                    color=TEXT_SECONDARY,
                ),
                actions=[
                    ft.ElevatedButton(
                        "Выйти",
                        style=ft.ButtonStyle(
                            bgcolor=ACCENT_COLOR,
                            color=TEXT_PRIMARY,
                            text_style=ft.TextStyle(size=14, weight="bold"),
                            padding=ft.padding.symmetric(horizontal=30, vertical=10),
                        ),
                        on_click=confirm_logout,
                    ),
                    ft.TextButton(
                        "Отмена",
                        style=ft.ButtonStyle(color=SECONDARY_COLOR),
                        on_click=lambda e: close_dialog(),
                    ),
                ],
                actions_alignment="end",
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=12),
            )
            page.overlay.append(dialog)
            dialog.open = True
            dialog.open = True
            page.update()

        def show_info_dialog():
            """Показывает диалог с информацией о приложении"""
            def close_dialog():
                dialog.open = False
                page.update()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.INFO_OUTLINE, size=28, color=PRIMARY_COLOR),
                        ft.Text("О приложении", size=22, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=10),
                    padding=10,
                ),
                content=ft.Column([
                    ft.Text("Invest Wallet", size=18, weight="bold", color=SECONDARY_COLOR),
                    ft.Text("Версия 1.0.0", size=12, color=TEXT_SECONDARY),
                    ft.Container(height=15),
                    ft.Text("Управление криптопортфелем", size=14, color=TEXT_PRIMARY, weight="500"),
                    ft.Container(height=10),
                    ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.CHECK_CIRCLE, size=16, color=SUCCESS_COLOR),
                            ft.Text("Отслеживание активов в реальном времени", size=12, color=TEXT_SECONDARY),
                        ], spacing=8),
                        ft.Row([
                            ft.Icon(ft.icons.CHECK_CIRCLE, size=16, color=SUCCESS_COLOR),
                            ft.Text("Анализ цен и прогнозирование", size=12, color=TEXT_SECONDARY),
                        ], spacing=8),
                        ft.Row([
                            ft.Icon(ft.icons.CHECK_CIRCLE, size=16, color=SUCCESS_COLOR),
                            ft.Text("Управление множеством активов", size=12, color=TEXT_SECONDARY),
                        ], spacing=8),
                        ft.Row([
                            ft.Icon(ft.icons.CHECK_CIRCLE, size=16, color=SUCCESS_COLOR),
                            ft.Text("Интеграция с биржами Bybit, OKX, MEXC", size=12, color=TEXT_SECONDARY),
                        ], spacing=8),
                    ], spacing=10),
                    ft.Container(height=15),
                    ft.Text("© 2024 Invest Wallet. Все права защищены.", size=11, color=TEXT_SECONDARY, italic=True),
                ], spacing=5, scroll="adaptive"),
                actions=[
                    ft.TextButton(
                        "Закрыть",
                        style=ft.ButtonStyle(color=PRIMARY_COLOR),
                        on_click=lambda e: close_dialog(),
                    ),
                ],
                actions_alignment="end",
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=12),
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def show_portfolio_chart_dialog():
            """Показывает большое окно с графиком портфеля за 7 дней"""
            try:
                # Получаем статистику
                stats = get_chart_stats(user.id)
                if not stats:
                    show_snack_bar("Недостаточно данных для графика", ACCENT_COLOR, ft.icons.WARNING)
                    return
                
                # Создаем график
                chart_file = create_portfolio_chart(user.id, output_file='portfolio_chart_display.png')
                
                if not chart_file or not os.path.exists(chart_file):
                    show_snack_bar("Ошибка при создании графика", ACCENT_COLOR, ft.icons.ERROR)
                    return
                
                # Закрытие диалога
                def close_dialog(e=None):
                    chart_dialog.open = False
                    page.update()
                
                # Диалог
                chart_dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.ASSESSMENT, size=26, color=PRIMARY_COLOR),
                            ft.Text("Динамика портфеля (7 дней)", size=20, weight="bold", color=TEXT_PRIMARY),
                        ], spacing=10),
                        padding=10,
                    ),
                    content=ft.Container(
                        content=ft.Image(src=chart_file, fit="contain"),
                        expand=True,
                        bgcolor="#1A1F2E",
                        border_radius=10,
                        width=1400,
                        height=850,
                    ),
                    actions=[
                        ft.TextButton("Закрыть", on_click=close_dialog),
                    ],
                    actions_alignment="center",
                    bgcolor=CARD_BG,
                    shape=ft.RoundedRectangleBorder(radius=12),
                )
                
                page.overlay.append(chart_dialog)
                chart_dialog.open = True
                page.update()
                
            except Exception as e:
                print(f"Ошибка при показе графика: {e}")
                import traceback
                traceback.print_exc()
                show_snack_bar("Ошибка при отображении графика", ACCENT_COLOR, ft.icons.ERROR)

        def top_up_balance():
            def confirm_top_up(e):
                try:
                    top_up_amount = round(float(balance_field.value), 1)
                    if top_up_amount <= 0:
                        raise ValueError("Сумма должна быть положительной")
                    user.balance += top_up_amount
                    # Увеличиваем общую сумму инвестиций (влияет на уровень пользователя)
                    user.total_invested = (user.total_invested or 0) + top_up_amount
                    session.commit()
                    show_profile(page, name)
                except ValueError as ex:
                    snack_bar = ft.SnackBar(ft.Text(f"Ошибка: {ex}", color=ACCENT_COLOR))
                    page.overlay.append(snack_bar)
                    snack_bar.open = True

            def close_dialog():
                # Dialog closing
                    dialog.open = False
                    page.update()

            # Поле для ввода суммы
            balance_field = ft.TextField(
                label="Сумма пополнения",
                hint_text="Введите сумму ($)",
                keyboard_type="number",
                bgcolor=CARD_BG,
                border_color=PRIMARY_COLOR,
                focused_border_color=SECONDARY_COLOR,
                label_style=ft.TextStyle(color=TEXT_SECONDARY),
                text_style=ft.TextStyle(color=TEXT_PRIMARY),
                prefix_icon=ft.icons.ATTACH_MONEY,
            )

            # Модальное окно
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ADD_CIRCLE, size=28, color=PRIMARY_COLOR),
                        ft.Text("Пополнить баланс", size=22, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=10),
                    padding=10,
                ),
                content=ft.Column(
                    [balance_field],
                    spacing=20,
                ),
                actions=[
                    ft.ElevatedButton(
                        "ПОПОЛНИТЬ",
                        style=ft.ButtonStyle(
                            bgcolor=PRIMARY_COLOR,
                            color=TEXT_PRIMARY,
                            text_style=ft.TextStyle(size=14, weight="bold"),
                            padding=ft.padding.symmetric(horizontal=30, vertical=10),
                        ),
                        on_click=confirm_top_up,
                    ),
                    ft.TextButton(
                        "Отмена",
                        style=ft.ButtonStyle(color=SECONDARY_COLOR),
                        on_click=lambda e: close_dialog(),
                    ),
                ],
                actions_alignment="end",
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=12),
            )
            page.overlay.append(dialog)
            dialog.open = True
            dialog.open = True
            page.update()

        def show_edit_profile_dialog():
            """Показывает диалог для редактирования профиля"""
            user = session.query(User).filter_by(name=user_name).first()
            if not user:
                return

            # Создаем поля ввода
            full_name_input = ft.TextField(
                label="Полное имя",
                value=user.full_name or "",
                bgcolor=CARD_BG,
                border_radius=8,
                filled=True,
                border="underline",
            )
            
            email_input = ft.TextField(
                label="Email",
                value=user.email or "",
                bgcolor=CARD_BG,
                border_radius=8,
                filled=True,
                border="underline",
            )
            
            phone_input = ft.TextField(
                label="Телефон",
                value=user.phone or "",
                bgcolor=CARD_BG,
                border_radius=8,
                filled=True,
                border="underline",
            )
            
            country_input = ft.TextField(
                label="Страна",
                value=user.country or "Россия",
                bgcolor=CARD_BG,
                border_radius=8,
                filled=True,
                border="underline",
            )
            
            bio_input = ft.TextField(
                label="Статус/О себе",
                value=user.bio or "Инвестор криптовалют",
                bgcolor=CARD_BG,
                border_radius=8,
                filled=True,
                border="underline",
                multiline=True,
                min_lines=2,
            )

            def save_profile(e):
                """Сохраняет изменения профиля"""
                try:
                    user.full_name = full_name_input.value or None
                    user.email = email_input.value or None
                    user.phone = phone_input.value or None
                    user.country = country_input.value or "Россия"
                    user.bio = bio_input.value or "Инвестор криптовалют"
                    
                    session.commit()
                    
                    # Закрываем диалог
                    edit_dialog.open = False
                    page.update()
                    
                    # Показываем уведомление об успехе
                    show_snack_bar("Профиль успешно обновлен!")
                    
                except Exception as ex:
                    print(f"Ошибка при сохранении профиля: {ex}")
                    session.rollback()

            edit_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.EDIT, size=28, color=SECONDARY_COLOR),
                        ft.Text("Редактирование профиля", size=22, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=10),
                    padding=10,
                ),
                content=ft.Column([
                    full_name_input,
                    email_input,
                    phone_input,
                    country_input,
                    bio_input,
                ], scroll="adaptive", spacing=12),
                actions=[
                    ft.TextButton(
                        "Отмена",
                        style=ft.ButtonStyle(color=ACCENT_COLOR),
                        on_click=lambda e: (setattr(edit_dialog, 'open', False), page.update()),
                    ),
                    ft.TextButton(
                        "Сохранить",
                        style=ft.ButtonStyle(color=SUCCESS_COLOR),
                        on_click=save_profile,
                    ),
                ],
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=12),
            )
            page.overlay.append(edit_dialog)
            edit_dialog.open = True
            page.update()

        def show_profile_dialog():
            """Показывает серьезный диалог с полной информацией профиля"""
            user = session.query(User).filter_by(name=user_name).first()
            if not user:
                return

            # Инициализируем значения
            total_profit = user.total_profit or 0.0
            total_invested = user.total_invested or 0.0
            total_trades = user.total_trades or 0
            full_name = user.full_name or "Активный инвестор"
            avatar_color = user.avatar_color or PRIMARY_COLOR
            country = user.country or "Россия"
            email = user.email or "Не указан"
            phone = user.phone or "Не указан"
            bio = user.bio or "Инвестор криптовалют"
            avatar_type = user.avatar_type or "initials"
            avatar_icon = user.avatar_icon or "PERSON"
            avatar_path = user.avatar_path

            # Статистика портфеля
            assets = session.query(Asset).filter_by(user_id=user.id).all()
            portfolio_value = sum(asset.value_rub for asset in assets)
            
            # Форматируем даты
            reg_date = user.registration_date.strftime("%d.%m.%Y") if user.registration_date else "Неизвестно"
            last_login = user.last_login.strftime("%d.%m.%Y %H:%M") if user.last_login else "Неизвестно"
            days_since_reg = (datetime.now() - user.registration_date).days if user.registration_date else 0
            
            # Определяем уровень пользователя по сумме инвестиций
            total_invested = user.total_invested or 0.0
            if total_invested >= 1000000:
                user_level = "DIAMOND"
                level_color = "#b9f2ff"
                level_icon = ft.icons.DIAMOND
            elif total_invested >= 100000:
                user_level = "PRO"
                level_color = "#ffd700"
                level_icon = ft.icons.WORKSPACE_PREMIUM
            else:
                user_level = "ОБЫЧНЫЙ"
                level_color = PRIMARY_COLOR
                level_icon = ft.icons.PERSON
            
            # Создаем аватар в зависимости от типа
            if avatar_type == "image" and avatar_path:
                avatar_widget = ft.CircleAvatar(
                    foreground_image_src=avatar_path,
                    radius=60,
                )
            elif avatar_type == "icon":
                icon_map = {
                    "PERSON": ft.icons.PERSON,
                    "FACE": ft.icons.FACE,
                    "ACCOUNT_CIRCLE": ft.icons.ACCOUNT_CIRCLE,
                    "SENTIMENT_VERY_SATISFIED": ft.icons.SENTIMENT_VERY_SATISFIED,
                    "ROCKET_LAUNCH": ft.icons.ROCKET_LAUNCH,
                    "DIAMOND": ft.icons.DIAMOND,
                    "STAR": ft.icons.STAR,
                    "BOLT": ft.icons.BOLT,
                }
                avatar_widget = ft.CircleAvatar(
                    content=ft.Icon(icon_map.get(avatar_icon, ft.icons.PERSON), size=50, color=DARK_BG),
                    radius=60,
                    bgcolor=avatar_color,
                )
            else:
                avatar_widget = ft.CircleAvatar(
                    content=ft.Text(user.name[0].upper(), size=48, weight="bold", color=DARK_BG),
                    radius=60,
                    bgcolor=avatar_color,
                )

            def close_dialog():
                dialog.open = False
                page.update()

            # Создаем диалог профиля
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_CIRCLE, size=28, color=PRIMARY_COLOR),
                        ft.Text("Профиль пользователя", size=22, weight="bold", color=TEXT_PRIMARY),
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(level_icon, size=16, color=level_color),
                                ft.Text(user_level, size=12, weight="bold", color=level_color),
                            ], spacing=5),
                            padding=ft.padding.symmetric(horizontal=10, vertical=5),
                            bgcolor=ft.colors.with_opacity(0.15, level_color),
                            border_radius=15,
                        ),
                    ], spacing=10, vertical_alignment="center"),
                    padding=10,
                ),
                content=ft.Container(
                    content=ft.Column([
                        # ===== ШАПКА ПРОФИЛЯ =====
                        ft.Container(
                            content=ft.Row([
                                # Аватар
                                ft.Container(
                                    content=avatar_widget,
                                    padding=5,
                                    border=ft.border.all(3, avatar_color),
                                    border_radius=70,
                                ),
                                ft.Container(width=20),
                                # Информация
                                ft.Column([
                                    ft.Row([
                                        ft.Text(user.name, size=26, weight="bold", color=TEXT_PRIMARY),
                                        ft.Icon(ft.icons.VERIFIED, size=20, color=SECONDARY_COLOR),
                                    ], spacing=8),
                                    ft.Text(full_name, size=14, color=TEXT_SECONDARY),
                                    ft.Text(bio, size=12, color=TEXT_SECONDARY, italic=True),
                                    ft.Container(height=5),
                                    ft.Row([
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Icon(ft.icons.PUBLIC, size=14, color=TEXT_SECONDARY),
                                                ft.Text(country, size=11, color=TEXT_SECONDARY),
                                            ], spacing=5),
                                        ),
                                        ft.Text("•", color=BORDER_COLOR),
                                        ft.Text(f"ID: {user.id}", size=11, color=TEXT_SECONDARY),
                                        ft.Text("•", color=BORDER_COLOR),
                                        ft.Text(f"{days_since_reg} дней", size=11, color=TEXT_SECONDARY),
                                    ], spacing=8),
                                ], spacing=3, expand=True),
                            ], vertical_alignment="center"),
                            padding=20,
                            bgcolor=ft.colors.with_opacity(0.05, PRIMARY_COLOR),
                            border_radius=15,
                            border=ft.border.all(1, BORDER_COLOR),
                        ),

                        ft.Container(height=15),

                        # ===== ФИНАНСОВАЯ СТАТИСТИКА =====
                        ft.Text("Финансовая статистика", size=14, weight="bold", color=PRIMARY_COLOR),
                        ft.Container(
                            content=ft.Row([
                                # Баланс
                                ft.Container(
                                    content=ft.Column([
                                        ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=28, color=SUCCESS_COLOR),
                                        ft.Text("Баланс", size=11, color=TEXT_SECONDARY),
                                        ft.Text(f"${user.balance:,.2f}", size=18, weight="bold", color=SUCCESS_COLOR),
                                    ], alignment="center", horizontal_alignment="center", spacing=5),
                                    padding=15,
                                    bgcolor=ft.colors.with_opacity(0.1, SUCCESS_COLOR),
                                    border_radius=12,
                                    expand=True,
                                ),
                                # Портфель
                                ft.Container(
                                    content=ft.Column([
                                        ft.Icon(ft.icons.TRENDING_UP, size=28, color=PRIMARY_COLOR),
                                        ft.Text("Портфель", size=11, color=TEXT_SECONDARY),
                                        ft.Text(f"${portfolio_value:,.2f}", size=18, weight="bold", color=PRIMARY_COLOR),
                                    ], alignment="center", horizontal_alignment="center", spacing=5),
                                    padding=15,
                                    bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                                    border_radius=12,
                                    expand=True,
                                ),
                                # Прибыль
                                ft.Container(
                                    content=ft.Column([
                                        ft.Icon(ft.icons.SHOW_CHART, size=28, color=SECONDARY_COLOR if total_profit >= 0 else ACCENT_COLOR),
                                        ft.Text("Прибыль", size=11, color=TEXT_SECONDARY),
                                        ft.Text(f"${total_profit:+,.2f}", size=18, weight="bold", 
                                               color=SECONDARY_COLOR if total_profit >= 0 else ACCENT_COLOR),
                                    ], alignment="center", horizontal_alignment="center", spacing=5),
                                    padding=15,
                                    bgcolor=ft.colors.with_opacity(0.1, SECONDARY_COLOR if total_profit >= 0 else ACCENT_COLOR),
                                    border_radius=12,
                                    expand=True,
                                ),
                            ], spacing=10),
                            padding=0,
                        ),

                        ft.Container(height=15),

                        # ===== АКТИВНОСТЬ =====
                        ft.Text("Активность", size=14, weight="bold", color=SECONDARY_COLOR),
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text(str(len(assets)), size=24, weight="bold", color=PRIMARY_COLOR),
                                        ft.Text("Активов", size=11, color=TEXT_SECONDARY),
                                    ], alignment="center", horizontal_alignment="center"),
                                    expand=True,
                                ),
                                ft.VerticalDivider(width=1, color=BORDER_COLOR),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text(str(total_trades), size=24, weight="bold", color=SECONDARY_COLOR),
                                        ft.Text("Сделок", size=11, color=TEXT_SECONDARY),
                                    ], alignment="center", horizontal_alignment="center"),
                                    expand=True,
                                ),
                                ft.VerticalDivider(width=1, color=BORDER_COLOR),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text(f"${total_invested:,.0f}", size=24, weight="bold", color=ACCENT_COLOR),
                                        ft.Text("Инвестировано", size=11, color=TEXT_SECONDARY),
                                    ], alignment="center", horizontal_alignment="center"),
                                    expand=True,
                                ),
                            ], spacing=0),
                            padding=15,
                            bgcolor=ft.colors.with_opacity(0.03, BORDER_COLOR),
                            border_radius=12,
                            border=ft.border.all(1, BORDER_COLOR),
                        ),

                        ft.Container(height=15),

                        # ===== КОНТАКТНАЯ ИНФОРМАЦИЯ =====
                        ft.Text("Контактная информация", size=14, weight="bold", color=TEXT_PRIMARY),
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon(ft.icons.EMAIL, size=20, color=PRIMARY_COLOR),
                                    ft.Text("Email:", size=12, color=TEXT_SECONDARY, width=80),
                                    ft.Text(email, size=12, color=TEXT_PRIMARY, weight="500"),
                                ], spacing=10),
                                ft.Row([
                                    ft.Icon(ft.icons.PHONE, size=20, color=SECONDARY_COLOR),
                                    ft.Text("Телефон:", size=12, color=TEXT_SECONDARY, width=80),
                                    ft.Text(phone, size=12, color=TEXT_PRIMARY, weight="500"),
                                ], spacing=10),
                            ], spacing=12),
                            padding=15,
                            bgcolor=ft.colors.with_opacity(0.03, BORDER_COLOR),
                            border_radius=12,
                            border=ft.border.all(1, BORDER_COLOR),
                        ),

                        ft.Container(height=15),

                        # ===== ИНФОРМАЦИЯ АККАУНТА =====
                        ft.Text("Информация аккаунта", size=14, weight="bold", color=TEXT_SECONDARY),
                        ft.Container(
                            content=ft.Row([
                                ft.Column([
                                    ft.Text("Дата регистрации", size=11, color=TEXT_SECONDARY),
                                    ft.Text(reg_date, size=13, color=TEXT_PRIMARY, weight="500"),
                                ], spacing=3, expand=True),
                                ft.Column([
                                    ft.Text("Последний вход", size=11, color=TEXT_SECONDARY),
                                    ft.Text(last_login, size=13, color=TEXT_PRIMARY, weight="500"),
                                ], spacing=3, expand=True),
                            ], spacing=15),
                            padding=15,
                            bgcolor=ft.colors.with_opacity(0.03, BORDER_COLOR),
                            border_radius=12,
                            border=ft.border.all(1, BORDER_COLOR),
                        ),
                    ], scroll="auto", spacing=8),
                    width=500,
                    height=550,
                ),
                actions=[
                    ft.Container(
                        content=ft.Row([
                            ft.ElevatedButton(
                                "Редактировать",
                                icon=ft.icons.EDIT,
                                style=ft.ButtonStyle(bgcolor=SECONDARY_COLOR, color=DARK_BG),
                                on_click=lambda e: (close_dialog(), show_edit_profile_dialog()),
                            ),
                            ft.ElevatedButton(
                                "Выйти",
                                icon=ft.icons.LOGOUT,
                                style=ft.ButtonStyle(bgcolor=ACCENT_COLOR, color=TEXT_PRIMARY),
                                on_click=lambda e: (close_dialog(), open_logout_dialog()),
                            ),
                            ft.TextButton(
                                "Закрыть",
                                style=ft.ButtonStyle(color=TEXT_SECONDARY),
                                on_click=lambda e: close_dialog(),
                            ),
                        ], spacing=10, alignment="center"),
                        expand=True,
                    ),
                ],
                actions_alignment="center",
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=16),
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def rebuild_asset_list():
            """Перестраивает только список активов, сохраняя scroll position"""
            try:
                # Получаем активы пользователя из БД (уже обновленные)
                user = session.query(User).filter_by(name=user_name).first()
                assets = session.query(Asset).filter_by(user_id=user.id).all()
                
                # Считаем общую стоимость портфеля
                total_portfolio_value = sum(asset.value_rub for asset in assets)
                total_assets_count = len(assets)
                
                # Очищаем список активов
                asset_list.controls.clear()
                
                # Добавляем активы заново с обновленными значениями
                if assets:
                    for asset in assets:
                        # Вычисляем процент от портфеля
                        asset_percentage = (asset.value_rub / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                        
                        # Создаем визуальное представление актива
                        asset_row = ft.Container(
                            content=ft.Row(
                                [
                                    # Левая часть: название и количество
                                    ft.Column([
                                        ft.Row([
                                            ft.Container(
                                                content=ft.Text(asset.coin_name[:3].upper(), size=14, weight="bold", color=TEXT_PRIMARY, text_align="center"),
                                                width=40,
                                                height=40,
                                                border_radius=8,
                                                bgcolor=ft.colors.with_opacity(0.2, SECONDARY_COLOR),
                                                alignment=ft.alignment.center,
                                            ),
                                            ft.Column([
                                                ft.Text(asset.coin_name, size=15, weight="bold", color=TEXT_PRIMARY),
                                                ft.Text(f"Кол-во: {asset.quantity:.6f}", size=12, color=TEXT_SECONDARY),
                                            ], spacing=2),
                                        ], spacing=12, vertical_alignment="center", expand=True),
                                        # Визуальное отображение процента портфеля
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Container(
                                                    bgcolor=PRIMARY_COLOR,
                                                    border_radius=4,
                                                    height=4,
                                                    expand=True,
                                                ),
                                                ft.Container(
                                                    bgcolor=ft.colors.with_opacity(0.1, BORDER_COLOR),
                                                    border_radius=4,
                                                    height=4,
                                                    expand=True,
                                                ),
                                            ], spacing=0, height=4),
                                            width=150,
                                            height=10,
                                            padding=ft.padding.symmetric(vertical=3),
                                        ),
                                    ], spacing=6, expand=True),
                                    # Правая часть: стоимость и кнопки
                                    ft.Column([
                                        ft.Column([
                                            ft.Text(f"${asset.value_rub:.2f}", size=16, weight="bold", color=SUCCESS_COLOR),
                                            ft.Text(f"{asset_percentage:.1f}% портфеля", size=11, color=TEXT_SECONDARY),
                                        ], alignment="end", horizontal_alignment="end", spacing=2),
                                        ft.Row(
                                            [
                                                ft.Container(
                                                    content=ft.Icon(ft.icons.ANALYTICS, size=18, color=SECONDARY_COLOR),
                                                    width=36,
                                                    height=36,
                                                    border_radius=8,
                                                    bgcolor=ft.colors.with_opacity(0.1, SECONDARY_COLOR),
                                                    on_click=lambda e, a=asset: show_analysis_dialog(a),
                                                    alignment=ft.alignment.center,
                                                    tooltip="Анализ и прогноз",
                                                ),
                                                ft.Container(
                                                    content=ft.Icon(ft.icons.SELL, size=18, color=PRIMARY_COLOR),
                                                    width=36,
                                                    height=36,
                                                    border_radius=8,
                                                    bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                                                    on_click=lambda e, a_id=asset.id: sell_asset(a_id),
                                                    alignment=ft.alignment.center,
                                                    tooltip="Продать актив",
                                                ),
                                                ft.Container(
                                                    content=ft.Icon(ft.icons.DELETE, size=18, color=ACCENT_COLOR),
                                                    width=36,
                                                    height=36,
                                                    border_radius=8,
                                                    bgcolor=ft.colors.with_opacity(0.1, ACCENT_COLOR),
                                                    on_click=lambda e, a_id=asset.id: delete_asset(a_id),
                                                    alignment=ft.alignment.center,
                                                    tooltip="Удалить актив",
                                                ),
                                            ],
                                            alignment="end",
                                            spacing=6,
                                        ),
                                    ], spacing=8, horizontal_alignment="end"),
                                ],
                                alignment="spaceBetween",
                                vertical_alignment="center",
                            ),
                            padding=ft.padding.all(14),
                            bgcolor=CARD_BG,
                            border_radius=12,
                            border=ft.border.all(1, BORDER_COLOR),
                            on_hover=None,
                        )
                        asset_list.controls.append(asset_row)
                else:
                    asset_list.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.icons.SAVINGS, size=64, color=TEXT_SECONDARY),
                                ft.Container(height=10),
                                ft.Text("У вас нет активов", size=20, color=TEXT_SECONDARY, text_align="center", weight="bold"),
                                ft.Container(height=5),
                                ft.Text("Начните с добавления первого актива", size=14, color=TEXT_SECONDARY, text_align="center"),
                            ], alignment="center", horizontal_alignment="center", spacing=0),
                            padding=60,
                            alignment=ft.alignment.center,
                        )
                    )
                
                # Обновляем только asset_list без полной перестройки
                page.update()
            except Exception as e:
                print(f"Ошибка при перестройке списка активов: {e}")

        def refresh_data():
            """Обновляет только цифры (цены) в фоне без переоткрывания UI"""

            def upsert_hourly_portfolio_history(db_session, user_id, portfolio_value):
                """Создает 1 запись на каждый час (timestamp округляется до часа)."""
                try:
                    now = datetime.now()
                    hour_ts = now.replace(minute=0, second=0, microsecond=0)

                    # Если за этот час уже есть запись — ничего не делаем
                    exists = db_session.query(PortfolioHistory).filter(
                        PortfolioHistory.user_id == user_id,
                        PortfolioHistory.timestamp == hour_ts,
                    ).first()
                    if exists:
                        return False

                    prev = db_session.query(PortfolioHistory).filter(
                        PortfolioHistory.user_id == user_id,
                        PortfolioHistory.timestamp < hour_ts,
                    ).order_by(PortfolioHistory.timestamp.desc()).first()
                    prev_value = prev.portfolio_value if prev else 0.0
                    change = float(portfolio_value) - float(prev_value)

                    # Изменение за сутки: ищем запись <= (час - 24ч)
                    day_ago_ts = hour_ts - timedelta(days=1)
                    day_ago = db_session.query(PortfolioHistory).filter(
                        PortfolioHistory.user_id == user_id,
                        PortfolioHistory.timestamp <= day_ago_ts,
                    ).order_by(PortfolioHistory.timestamp.desc()).first()
                    daily_change = 0.0
                    if day_ago:
                        daily_change = float(portfolio_value) - float(day_ago.portfolio_value)

                    rec = PortfolioHistory(
                        user_id=user_id,
                        timestamp=hour_ts,
                        portfolio_value=float(portfolio_value),
                        change=float(change),
                        daily_change=float(daily_change),
                    )
                    db_session.add(rec)
                    return True
                except Exception as e:
                    print(f"Ошибка записи portfolio_history: {e}")
                    return False

            def update_data():
                try:
                    import time
                    print(f"[{time.strftime('%H:%M:%S')}] Начинаю обновление данных...")
                    
                    # Обновляем данные (вызываем вашу функцию)
                    nonlocal data
                    data = mainn()

                    # В фоне используем отдельную сессию (глобальная session не потокобезопасна)
                    db_session = Session()
                    user = db_session.query(User).filter_by(name=user_name).first()
                    updated_count = 0
                    total_portfolio_value = 0
                    daily_change = 0
                    
                    if user:
                        assets = db_session.query(Asset).filter_by(user_id=user.id).all()
                        
                        for asset in assets:
                            coin_name = asset.coin_name
                            if coin_name in data:
                                # Берем среднюю цену по всем биржам
                                prices = data[coin_name]
                                average_price = sum(prices.values()) / len(prices)

                                # Рассчитываем стоимость актива
                                asset.value_rub = round((asset.quantity * average_price), 1)
                                total_portfolio_value += asset.value_rub
                                updated_count += 1
                            else:
                                print(f"Монета {coin_name} не найдена в обновленных данных!")
                        
                        # Сохраняем старый объем и записываем новый
                        old_portfolio_value = user.portfolio_value or 0
                        user.portfolio_value = total_portfolio_value
                        
                        # Расчитываем изменение: старый объем - новый объем
                        daily_change = old_portfolio_value - total_portfolio_value
                        user.total_profit = round(daily_change, 2)

                        # Раз в час сохраняем значение объема портфеля в portfolio_history
                        upsert_hourly_portfolio_history(db_session, user.id, total_portfolio_value)

                    # Сохраняем изменения
                    db_session.commit()
                    print(f"[{time.strftime('%H:%M:%S')}] Обновлено {updated_count} активов, объем: ${total_portfolio_value:,.2f}, изменение: ${daily_change:,.2f}")

                    db_session.close()

                except Exception as e:
                    print(f"Ошибка обновления: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        db_session.rollback()
                    except Exception:
                        pass
                    try:
                        db_session.close()
                    except Exception:
                        pass

            # Запускаем обновление в фоне без диалога
            import threading
            thread = threading.Thread(target=update_data, daemon=True)
            thread.start()

        def create_summary_page():
            """Создает страницу со сводом по монетам на разных биржах."""
            def refresh_summary(e):
                """Обновляет данные на странице свода."""
                # Показать окно загрузки
                loading_dialog = ft.AlertDialog(
                    modal=True,
                    content=ft.Container(
                        content=ft.Column([
                            ft.ProgressRing(stroke_width=3, color=PRIMARY_COLOR, value=0.5),
                            ft.Container(height=20),
                            ft.Text(
                                "Обновление данных",
                                size=18,
                                weight="bold",
                                color=TEXT_PRIMARY,
                                text_align="center",
                            ),
                            ft.Text(
                                "Пожалуйста, подождите...",
                                size=14,
                                color=TEXT_SECONDARY,
                                text_align="center",
                            ),
                        ], alignment="center", horizontal_alignment="center", spacing=15),
                        padding=40,
                        alignment=ft.alignment.center,
                    ),
                    bgcolor=CARD_BG,
                    shape=ft.RoundedRectangleBorder(radius=12),
                )
                page.overlay.append(loading_dialog)
                loading_dialog.open = True
                loading_dialog.open = True
                page.update()

                try:
                    # Получаем новые данные
                    nonlocal data
                    data = mainn()

                    # Очищаем старое содержимое
                    summary_table.controls.clear()

                    # Добавляем заголовки
                    summary_table.controls.extend([
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Text("Монета", size=16, weight="bold", color=SECONDARY_COLOR, expand=1),
                                    ft.Text("Биржа", size=16, weight="bold", color=SECONDARY_COLOR, expand=1),
                                    ft.Text("Цена ($)", size=16, weight="bold", color=SECONDARY_COLOR, expand=1, text_align="end"),
                                    ft.Text("", size=16, expand=0.2),
                                ],
                                alignment="spaceBetween",
                                height=50,
                            ),
                            padding=ft.padding.symmetric(horizontal=15),
                        ),
                        ft.Divider(thickness=1, color=BORDER_COLOR),
                    ])

                    # Добавляем обновленные данные
                    for coin_name, prices in data.items():
                        for exchange, price in prices.items():
                            summary_table.controls.append(
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Text(coin_name, size=14, color=TEXT_PRIMARY, expand=1),
                                            ft.Text(exchange, size=14, color=TEXT_SECONDARY, expand=1),
                                            ft.Text(f"${price:.2f}", size=14, color=SUCCESS_COLOR, weight="bold", expand=1, text_align="end"),
                                            ft.Container(
                                                content=ft.Icon(ft.icons.INFO, size=16, color=TEXT_SECONDARY),
                                                width=30,
                                                height=30,
                                                border_radius=6,
                                                bgcolor=ft.colors.with_opacity(0.1, BORDER_COLOR),
                                                alignment=ft.alignment.center,
                                                tooltip="Информация о цене",
                                            ),
                                        ],
                                        alignment="spaceBetween",
                                    ),
                                    padding=ft.padding.symmetric(horizontal=15, vertical=10),
                                    bgcolor=CARD_BG,
                                    border_radius=4,
                                    border=ft.border.all(1, BORDER_COLOR),
                                    margin=ft.margin.symmetric(vertical=3),
                                )
                            )
                    # Закрываем окно загрузки
                    loading_dialog.open = False
                    page.update()
                except Exception as e:
                    # Закрываем окно загрузки при ошибке
                    loading_dialog.open = False
                    page.update()
                    
                    error_snackbar = ft.SnackBar(
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.ERROR, size=20, color=ACCENT_COLOR),
                                ft.Text(f"Ошибка обновления: {e}", color=TEXT_PRIMARY, size=14),
                            ], spacing=10),
                            padding=10,
                        ),
                        bgcolor=CARD_BG,
                        duration=4000,
                    )
                    page.overlay.append(error_snackbar)
                    error_snackbar.open = True
                    page.update()

            # Создаем таблицу для отображения данных
            summary_table = ft.Column(
                [
                    # Заголовки столбцов
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text("Монета", size=16, weight="bold", color=SECONDARY_COLOR, expand=1),
                                ft.Text("Биржа", size=16, weight="bold", color=SECONDARY_COLOR, expand=1),
                                ft.Text("Цена ($)", size=16, weight="bold", color=SECONDARY_COLOR, expand=1, text_align="end"),
                                ft.Text("", size=16, expand=0.2),
                            ],
                            alignment="spaceBetween",
                            height=50,
                        ),
                        padding=ft.padding.symmetric(horizontal=15),
                    ),
                    ft.Divider(thickness=1, color=BORDER_COLOR),
                ],
                scroll="adaptive",
                expand=True,
                spacing=3,
            )

            # Инициализация таблицы с текущими данными
            for coin_name, prices in data.items():
                for exchange, price in prices.items():
                    summary_table.controls.append(
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Text(coin_name, size=14, color=TEXT_PRIMARY, expand=1),
                                    ft.Text(exchange, size=14, color=TEXT_SECONDARY, expand=1),
                                    ft.Text(f"${price:.2f}", size=14, color=SUCCESS_COLOR, weight="bold", expand=1, text_align="end"),
                                    ft.Container(
                                        content=ft.Icon(ft.icons.INFO, size=16, color=TEXT_SECONDARY),
                                        width=30,
                                        height=30,
                                        border_radius=6,
                                        bgcolor=ft.colors.with_opacity(0.1, BORDER_COLOR),
                                        alignment=ft.alignment.center,
                                        tooltip="Информация о цене",
                                    ),
                                ],
                                alignment="spaceBetween",
                            ),
                            padding=ft.padding.symmetric(horizontal=15, vertical=10),
                            bgcolor=CARD_BG,
                            border_radius=4,
                            border=ft.border.all(1, BORDER_COLOR),
                            margin=ft.margin.symmetric(vertical=3),
                        )
                    )

            # Кнопка для обновления данных
            refresh_button = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.REFRESH, size=22, color=TEXT_PRIMARY),
                        ft.Column([
                            ft.Text("Обновить данные", size=14, weight="bold", color=TEXT_PRIMARY),
                            ft.Text("Загрузить новые цены", size=11, color=TEXT_SECONDARY),
                        ], spacing=2),
                    ], spacing=12, alignment="start", vertical_alignment="center"),
                ], spacing=0),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
                bgcolor=SUCCESS_COLOR,
                border_radius=10,
                on_click=refresh_summary,
                ink=True,
                tooltip="Обновить цены на все монеты",
                expand=True,
            )

            # Кнопка возврата в профиль
            def return_to_profile(e):
                # Возврат к профилю
                page.views.pop()
                show_profile(page, name)

            back_button = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.ARROW_BACK, size=22, color=TEXT_PRIMARY),
                        ft.Column([
                            ft.Text("Вернуться", size=14, weight="bold", color=TEXT_PRIMARY),
                            ft.Text("В мой портфель", size=11, color=TEXT_SECONDARY),
                        ], spacing=2),
                    ], spacing=12, alignment="start", vertical_alignment="center"),
                ], spacing=0),
                padding=ft.padding.symmetric(horizontal=20, vertical=14),
                bgcolor=PRIMARY_COLOR,
                border_radius=10,
                on_click=return_to_profile,
                ink=True,
                tooltip="Вернуться к профилю",
                expand=True,
            )

            # Верстка новой страницы
            return ft.View(
                controls=[
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.icons.VIEW_WEEK, size=32, color=SECONDARY_COLOR),
                                ft.Text("Сводка по монетам", size=28, weight="bold", color=TEXT_PRIMARY),
                            ], spacing=15, alignment="start"),
                            ft.Text("Цены на всех биржах", size=14, color=TEXT_SECONDARY),
                        ], spacing=5),
                        padding=ft.padding.all(15),
                        bgcolor=CARD_BG,
                        border_radius=12,
                        border=ft.border.all(1, BORDER_COLOR),
                        margin=ft.margin.all(10),
                    ),
                    summary_table,
                    ft.Container(
                        content=ft.Row([refresh_button, back_button], alignment="spaceAround", spacing=10),
                        padding=ft.padding.all(10),
                        margin=ft.margin.all(10),
                    ),
                ],
                bgcolor=DARK_BG,
            )
        

        def open_summary_page(e):
            """Открывает страницу со сводом."""
            summary_page = create_summary_page()
            page.views.append(summary_page)
            page.go("/summary")

        def generate_price_chart(prices, future_price, asset_id):
                """
                Рисует линию: исторические цены + точка прогноза.
                Сохраняет в файл chart_<asset_id>.png и возвращает путь.
                Цвета настроены под тёмную тему вашего приложения.
                """
                # объединяем историю + прогноз
                x = list(range(len(prices))) + [len(prices)]
                y = prices + [future_price]

                # создаём figure с тёмным фоном
                fig = plt.figure(figsize=(5, 3), dpi=100, facecolor="#121212")
                ax = fig.add_subplot(1, 1, 1, facecolor="#121212")

                # рисуем линию (синяя) и маркеры (оранжевые)
                ax.plot(
                    x, y,
                    color="#1976D2",            # синий (Flet.blue_700)
                    marker="o",
                    markerfacecolor="#00d4ff",  # янтарный (Flet.amber_600)
                    markeredgecolor="#00d4ff",
                    linewidth=2,
                )

                # заголовок и подписи белым
                ax.set_title("История цены и прогноз", color="white", fontsize=12, pad=10)
                ax.set_xlabel("Шаги времени", color="white", fontsize=10)
                ax.set_ylabel("Цена ($)", color="white", fontsize=10)

                # цвет спайн и тиков
                for spine in ax.spines.values():
                    spine.set_color("#424242")  # тёмно-серый (Flet.grey_700)
                ax.tick_params(colors="white")

                # сетка
                ax.grid(color="#424242", linestyle="--", alpha=0.5)

                plt.tight_layout()

                # сохраняем в PNG
                filename = f"chart_{asset_id}.png"
                plt.savefig(filename, facecolor=fig.get_facecolor(), edgecolor="none")
                plt.close(fig)
                return filename


        def show_analysis_dialog(asset):
            # 1. Приготовление данных
            last_prices = fetch_last_20_prices(asset.coin_name)
            if not last_prices:
                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.ERROR, size=28, color=ACCENT_COLOR),
                            ft.Text("Ошибка", size=22, weight="bold", color=TEXT_PRIMARY),
                        ], spacing=10),
                        padding=10,
                    ),
                    content=ft.Text("Нет данных для анализа.", color=TEXT_SECONDARY),
                    actions=[ft.TextButton(
                        "Закрыть",
                        style=ft.ButtonStyle(color=PRIMARY_COLOR),
                        on_click=lambda e: close_dialog(dlg)
                    )],
                    bgcolor=CARD_BG,
                    shape=ft.RoundedRectangleBorder(radius=12),
                )
                page.overlay.append(dlg)
                dlg.open = True
                dlg.open = True
                page.update()
                return

            future_price = predict_future_price(last_prices)
            current_price = last_prices[-1]
            diff = round(future_price - current_price, 2)
            profit = round((future_price * asset.quantity) - (current_price * asset.quantity), 2)
            color = SUCCESS_COLOR if profit >= 0 else ACCENT_COLOR

            # 2. Генерируем график и получаем путь к файлу
            chart_file = generate_price_chart(last_prices, future_price, asset.id)

            # 3. Обработчик закрытия
            def close_dialog(e):
                dlg.open = False
                page.update()

            # 4. Строим диалог с Image
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ANALYTICS, size=28, color=SECONDARY_COLOR),
                        ft.Text(f"Анализ {asset.coin_name}", size=22, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=10),
                    padding=10,
                ),
                content=ft.Column(
                    [
                        # сам график
                        ft.Container(
                            content=Image(src=chart_file, width=500, height=320),
                            bgcolor=CARD_BG,
                            border_radius=8,
                            border=ft.border.all(1, BORDER_COLOR),
                            padding=10,
                        ),
                        # текстовая статистика
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Text("Текущая цена:", size=14, color=TEXT_SECONDARY, expand=1),
                                    ft.Text(f"${current_price:.2f}", size=14, weight="bold", color=TEXT_PRIMARY),
                                ], alignment="spaceBetween"),
                                ft.Row([
                                    ft.Text("Прогноз на шаг:", size=14, color=TEXT_SECONDARY, expand=1),
                                    ft.Text(f"${future_price:.2f}", size=14, weight="bold", color=SECONDARY_COLOR),
                                ], alignment="spaceBetween"),
                                ft.Row([
                                    ft.Text("Изменение:", size=14, color=TEXT_SECONDARY, expand=1),
                                    ft.Text(f"${diff:.2f}", size=14, weight="bold", color=color),
                                ], alignment="spaceBetween"),
                                ft.Divider(thickness=1, color=BORDER_COLOR),
                                ft.Row([
                                    ft.Text(f"{'Ожидаемая прибыль' if profit>=0 else 'Ожидаемый убыток'}:", size=14, color=TEXT_SECONDARY, expand=1),
                                    ft.Text(f"${profit:.2f}", size=14, weight="bold", color=color),
                                ], alignment="spaceBetween"),
                            ], spacing=10),
                            padding=15,
                            bgcolor="#0a0e17",
                            border_radius=8,
                            border=ft.border.all(1, BORDER_COLOR),
                        ),
                    ],
                    spacing=15,
                ),
                actions=[ft.TextButton(
                    "Закрыть",
                    style=ft.ButtonStyle(color=PRIMARY_COLOR),
                    on_click=close_dialog
                )],
                actions_alignment="end",
                bgcolor=CARD_BG,
                shape=ft.RoundedRectangleBorder(radius=12),
            )

            page.overlay.append(dlg)
            dlg.open = True
            dlg.open = True
            page.update()

        page.controls.clear()

        # ============ HEADER / ПРОФИЛЬ ============
        # Расчет профиля пользователя
        total_portfolio_value = sum(asset.value_rub for asset in assets)
        total_assets_count = len(assets)
        
        # Определяем уровень пользователя по инвестициям
        total_invested_val = user.total_invested or 0.0
        if total_invested_val >= 1000000:
            header_user_level = "DIAMOND"
            header_level_color = "#b9f2ff"
        elif total_invested_val >= 100000:
            header_user_level = "PRO"
            header_level_color = "#ffd700"
        else:
            header_user_level = "ОБЫЧНЫЙ"
            header_level_color = PRIMARY_COLOR
        
        header_container = ft.Container(
            content=ft.Column([
                # Профиль пользователя - кликабельная карточка
                ft.Container(
                    content=ft.Row([
                        # Аватар
                        ft.Container(
                            content=ft.CircleAvatar(
                                content=ft.Text(user.name[0].upper(), size=36, weight="bold", color=DARK_BG),
                                radius=45,
                                bgcolor=user.avatar_color or PRIMARY_COLOR,
                            ),
                        ),
                        # Информация о пользователе
                        ft.Column([
                            ft.Row([
                                ft.Text(f"{user.name}", size=20, weight="bold", color=TEXT_PRIMARY),
                                ft.Icon(ft.icons.VERIFIED, size=16, color=SECONDARY_COLOR),
                            ], spacing=8, vertical_alignment="center"),
                            ft.Text(user.full_name or "Активный инвестор", size=12, color=TEXT_SECONDARY),
                            ft.Row([
                                ft.Icon(ft.icons.TRENDING_UP, size=12, color=SUCCESS_COLOR),
                                ft.Text(f"ID: {user.id}", size=10, color=TEXT_SECONDARY),
                                ft.Text("•", color=BORDER_COLOR),
                                ft.Text(user.country or "Россия", size=10, color=TEXT_SECONDARY),
                            ], spacing=5),
                        ], spacing=3, expand=True),
                        # Статистика справа
                        ft.Column([
                            ft.Row([
                                ft.Column([
                                    ft.Text("Баланс", size=10, color=TEXT_SECONDARY, weight="500"),
                                    ft.Text(f"₽{user.balance:,}", size=13, weight="bold", color=SUCCESS_COLOR),
                                ], alignment="end", horizontal_alignment="end", spacing=2),
                                ft.Divider(thickness=1, color=BORDER_COLOR),
                                ft.Column([
                                    ft.Text("Уровень", size=10, color=TEXT_SECONDARY, weight="500"),
                                    ft.Text(header_user_level, size=13, weight="bold", color=header_level_color),
                                ], alignment="end", horizontal_alignment="end", spacing=2),
                            ], spacing=8, alignment="end", expand=True),
                        ], spacing=5, horizontal_alignment="end"),
                    ], spacing=15, vertical_alignment="center", alignment="spaceBetween"),
                    padding=15,
                    bgcolor=ft.colors.with_opacity(0.08, PRIMARY_COLOR),
                    border_radius=14,
                    border=ft.border.all(1, BORDER_COLOR),
                    on_click=lambda e: show_profile_dialog(),
                    ink=True,
                    tooltip="Нажмите для просмотра профиля",
                    margin=ft.margin.all(0),
                ),
                
                # Верхняя панель с статистикой
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.TRENDING_UP, size=24, color=SECONDARY_COLOR),
                        ft.Text("Ваши активы", size=24, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=12, alignment="start", vertical_alignment="center"),
                    ft.Row([
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Портфель", size=11, color=TEXT_SECONDARY),
                                ft.Text(f"${total_portfolio_value:,.2f}", size=16, weight="bold", color=PRIMARY_COLOR),
                            ], spacing=2),
                            padding=10,
                            bgcolor=ft.colors.with_opacity(0.05, PRIMARY_COLOR),
                            border_radius=8,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Изменение", size=11, color=TEXT_SECONDARY),
                                ft.Text(
                                    f"${(user.total_profit or 0.0):,.2f}",
                                    size=16,
                                    weight="bold",
                                    color=SUCCESS_COLOR if (user.total_profit or 0.0) >= 0 else ACCENT_COLOR
                                ),
                            ], spacing=2),
                            padding=10,
                            bgcolor=ft.colors.with_opacity(0.05, SUCCESS_COLOR if (user.total_profit or 0.0) >= 0 else ACCENT_COLOR),
                            border_radius=8,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Инвестировано", size=11, color=TEXT_SECONDARY),
                                ft.Text(f"${user.total_invested or 0.0:,.2f}", size=16, weight="bold", color=SECONDARY_COLOR),
                            ], spacing=2),
                            padding=10,
                            bgcolor=ft.colors.with_opacity(0.05, SECONDARY_COLOR),
                            border_radius=8,
                            expand=True,
                        ),
                    ], spacing=10, scroll="auto"),
                ], spacing=12),
            ], spacing=0),
            padding=ft.padding.all(15),
            bgcolor=CARD_BG,
            border_radius=16,
            border=ft.border.all(1, BORDER_COLOR),
            shadow=ft.BoxShadow(
                blur_radius=12,
                spread_radius=0,
                color="#00d4ff15",
                offset=ft.Offset(0, 4),
            ),
            margin=ft.margin.all(12),
        )

        # ============ ACTION BUTTONS ============
        action_buttons_container = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.ADD_CIRCLE, size=24, color=TEXT_PRIMARY),
                                    ft.Column([
                                        ft.Text("Добавить актив", size=14, weight="bold", color=TEXT_PRIMARY),
                                        ft.Text("Купить криптовалюту", size=11, color=TEXT_SECONDARY),
                                    ], spacing=2),
                                ], spacing=12, alignment="start", vertical_alignment="center"),
                                padding=15,
                            ),
                        ], spacing=0),
                        bgcolor=SUCCESS_COLOR,
                        border_radius=12,
                        on_click=lambda e: add_asset(),
                        ink=True,
                        tooltip="Добавить новый актив",
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.ATTACH_MONEY, size=24, color=TEXT_PRIMARY),
                                    ft.Column([
                                        ft.Text("Пополнить баланс", size=14, weight="bold", color=TEXT_PRIMARY),
                                        ft.Text("Добавить средства", size=11, color=TEXT_SECONDARY),
                                    ], spacing=2),
                                ], spacing=12, alignment="start", vertical_alignment="center"),
                                padding=15,
                            ),
                        ], spacing=0),
                        bgcolor=PRIMARY_COLOR,
                        border_radius=12,
                        on_click=lambda e: top_up_balance(),
                        ink=True,
                        tooltip="Пополнить баланс",
                        expand=True,
                    ),
                ], spacing=10, expand=True),
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.VIEW_WEEK, size=24, color=TEXT_PRIMARY),
                                    ft.Column([
                                        ft.Text("Сводка по монетам", size=14, weight="bold", color=TEXT_PRIMARY),
                                        ft.Text("Цены на всех биржах", size=11, color=TEXT_SECONDARY),
                                    ], spacing=2),
                                ], spacing=12, alignment="start", vertical_alignment="center"),
                                padding=15,
                            ),
                        ], spacing=0),
                        bgcolor=SECONDARY_COLOR,
                        border_radius=12,
                        on_click=open_summary_page,
                        ink=True,
                        tooltip="Просмотреть цены на всех биржах",
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Container(
                                content=ft.Row([
                                    ft.Icon(ft.icons.ASSESSMENT, size=24, color=TEXT_PRIMARY),
                                    ft.Column([
                                        ft.Text("График портфеля", size=14, weight="bold", color=TEXT_PRIMARY),
                                        ft.Text("Динамика за 7 дней", size=11, color=TEXT_SECONDARY),
                                    ], spacing=2),
                                ], spacing=12, alignment="start", vertical_alignment="center"),
                                padding=15,
                            ),
                        ], spacing=0),
                        bgcolor=ft.colors.with_opacity(0.15, PRIMARY_COLOR),
                        border=ft.border.all(1.5, PRIMARY_COLOR),
                        border_radius=12,
                        on_click=lambda e: show_portfolio_chart_dialog(),
                        ink=True,
                        tooltip="Показать график портфеля за 7 дней",
                        expand=True,
                    ),
                ], spacing=10, expand=True),
            ], spacing=10),
            padding=ft.padding.all(12),
            margin=ft.margin.all(12),
        )

        # ============ ASSETS LIST ============
        asset_list = ft.Column(
            scroll="adaptive",
            expand=True,
            spacing=8,
        )

        # Добавляем активы
        if assets:
            for asset in assets:
                # Вычисляем процент от портфеля
                asset_percentage = (asset.value_rub / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
                
                # Создаем визуальное представление актива
                asset_row = ft.Container(
                    content=ft.Row(
                        [
                            # Левая часть: название и количество
                            ft.Column([
                                ft.Row([
                                    ft.Container(
                                        content=ft.Text(asset.coin_name[:3].upper(), size=14, weight="bold", color=TEXT_PRIMARY, text_align="center"),
                                        width=40,
                                        height=40,
                                        border_radius=8,
                                        bgcolor=ft.colors.with_opacity(0.2, SECONDARY_COLOR),
                                        alignment=ft.alignment.center,
                                    ),
                                    ft.Column([
                                        ft.Text(asset.coin_name, size=15, weight="bold", color=TEXT_PRIMARY),
                                        ft.Text(f"Кол-во: {asset.quantity:.6f}", size=12, color=TEXT_SECONDARY),
                                    ], spacing=2),
                                ], spacing=12, vertical_alignment="center", expand=True),
                                # Визуальное отображение процента портфеля
                                ft.Container(
                                    content=ft.Row([
                                        ft.Container(
                                            bgcolor=PRIMARY_COLOR,
                                            border_radius=4,
                                            height=4,
                                            expand=True,
                                        ),
                                        ft.Container(
                                            bgcolor=ft.colors.with_opacity(0.1, BORDER_COLOR),
                                            border_radius=4,
                                            height=4,
                                            expand=True,
                                        ),
                                    ], spacing=0, height=4),
                                    width=150,
                                    height=10,
                                    padding=ft.padding.symmetric(vertical=3),
                                ),
                            ], spacing=6, expand=True),
                            # Правая часть: стоимость и кнопки
                            ft.Column([
                                ft.Column([
                                    ft.Text(f"${asset.value_rub:.2f}", size=16, weight="bold", color=SUCCESS_COLOR),
                                    ft.Text(f"{asset_percentage:.1f}% портфеля", size=11, color=TEXT_SECONDARY),
                                ], alignment="end", horizontal_alignment="end", spacing=2),
                                ft.Row(
                                    [
                                        ft.Container(
                                            content=ft.Icon(ft.icons.ANALYTICS, size=18, color=SECONDARY_COLOR),
                                            width=36,
                                            height=36,
                                            border_radius=8,
                                            bgcolor=ft.colors.with_opacity(0.1, SECONDARY_COLOR),
                                            on_click=lambda e, a=asset: show_analysis_dialog(a),
                                            alignment=ft.alignment.center,
                                            tooltip="Анализ и прогноз",
                                        ),
                                        ft.Container(
                                            content=ft.Icon(ft.icons.SELL, size=18, color=PRIMARY_COLOR),
                                            width=36,
                                            height=36,
                                            border_radius=8,
                                            bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                                            on_click=lambda e, a_id=asset.id: sell_asset(a_id),
                                            alignment=ft.alignment.center,
                                            tooltip="Продать актив",
                                        ),
                                        ft.Container(
                                            content=ft.Icon(ft.icons.DELETE, size=18, color=ACCENT_COLOR),
                                            width=36,
                                            height=36,
                                            border_radius=8,
                                            bgcolor=ft.colors.with_opacity(0.1, ACCENT_COLOR),
                                            on_click=lambda e, a_id=asset.id: delete_asset(a_id),
                                            alignment=ft.alignment.center,
                                            tooltip="Удалить актив",
                                        ),
                                    ],
                                    alignment="end",
                                    spacing=6,
                                ),
                            ], spacing=8, horizontal_alignment="end"),
                        ],
                        alignment="spaceBetween",
                        vertical_alignment="center",
                    ),
                    padding=ft.padding.all(14),
                    bgcolor=CARD_BG,
                    border_radius=12,
                    border=ft.border.all(1, BORDER_COLOR),
                    on_hover=None,
                )
                asset_list.controls.append(asset_row)
        else:
            asset_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SAVINGS, size=64, color=TEXT_SECONDARY),
                        ft.Container(height=10),
                        ft.Text("У вас нет активов", size=20, color=TEXT_SECONDARY, text_align="center", weight="bold"),
                        ft.Container(height=5),
                        ft.Text("Начните с добавления первого актива", size=14, color=TEXT_SECONDARY, text_align="center"),
                    ], alignment="center", horizontal_alignment="center", spacing=0),
                    padding=60,
                    alignment=ft.alignment.center,
                )
            )

        # Оборачиваем список в контейнер
        assets_container = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.TRENDING_UP, size=24, color=SECONDARY_COLOR),
                    ft.Text("Ваши активы", size=24, weight="bold", color=TEXT_PRIMARY),
                    ft.Text(f"({total_assets_count})", size=18, color=TEXT_SECONDARY),
                ], spacing=12, alignment="start", vertical_alignment="center"),
                asset_list,
            ], expand=True, spacing=12),
            padding=ft.padding.all(15),
            margin=ft.margin.all(12),
            border_radius=16,
            bgcolor=ft.colors.with_opacity(0.03, BORDER_COLOR),
            border=ft.border.all(1, BORDER_COLOR),
        )

        # ============ FOOTER ============
        footer_container = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=18, color=SECONDARY_COLOR),
                    ft.Text("Invest Wallet", size=14, weight="bold", color=SECONDARY_COLOR),
                    ft.Text("v1.0.0", size=12, color=TEXT_SECONDARY),
                ], spacing=8),
                ft.Row([
                    ft.TextButton(
                        content=ft.Row([
                            ft.Icon(ft.icons.INFO_OUTLINE, size=14, color=TEXT_SECONDARY),
                            ft.Text("О приложении", size=12, color=TEXT_SECONDARY),
                        ], spacing=5),
                        on_click=lambda e: show_info_dialog(),
                    ),
                ], spacing=5),
                ft.Text("© 2024 Все права защищены", size=11, color=TEXT_SECONDARY, italic=True),
            ], alignment="spaceBetween", vertical_alignment="center"),
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            bgcolor=ft.colors.with_opacity(0.05, BORDER_COLOR),
            border=ft.border.only(top=ft.BorderSide(1, BORDER_COLOR)),
        )

        # ============ ОБЪЕДИНЯЕМ ВСЁ ============
        page.controls.clear()
        page.add(
            ft.Column([
                header_container,
                action_buttons_container,
                assets_container,
                footer_container,
            ], scroll="adaptive", expand=True, spacing=0)
        )
        page.update()

        # Запуск автоматического обновления каждую минуту
        def auto_refresh():
            import time
            time.sleep(10)  # Ждём 10 секунд перед первым обновлением
            while True:
                try:
                    time.sleep(60)  # Ждём 60 секунд (1 минуту)
                    refresh_data()  # Обновляем только данные, не UI
                except Exception as e:
                    print(f"Ошибка при автоматическом обновлении: {e}")

        import threading
        auto_thread = threading.Thread(target=auto_refresh, daemon=True)
        auto_thread.start()

    # ============ ВОССТАНОВЛЕНИЕ ПАРОЛЯ ============
    def show_forgot_password_screen():
        """Экран восстановления пароля - ввод email"""
        page.controls.clear()
        
        email_field = ft.TextField(
            label="Email",
            hint_text="Введите email, указанный при регистрации",
            width=350,
            bgcolor=CARD_BG,
            border_color=PRIMARY_COLOR,
            focused_border_color=SECONDARY_COLOR,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            text_style=ft.TextStyle(color=TEXT_PRIMARY),
            prefix_icon=ft.icons.EMAIL,
        )
        
        error_text = ft.Text("", color=ACCENT_COLOR, visible=False, size=13)
        success_text = ft.Text("", color=SUCCESS_COLOR, visible=False, size=13)
        
        def send_code(e):
            email = email_field.value.strip()
            if not email:
                error_text.value = "Введите email"
                error_text.visible = True
                success_text.visible = False
                page.update()
                return
            
            # Ищем пользователя с таким email
            user = session.query(User).filter(User.email == email).first()
            if not user:
                error_text.value = "Пользователь с таким email не найден"
                error_text.visible = True
                success_text.visible = False
                page.update()
                return
            
            # Генерируем код
            code = generate_recovery_code()
            user.recovery_code = code
            user.recovery_code_expires = get_code_expiry_time(10)
            session.commit()
            
            # Отправляем (в тестовом режиме - выводим в консоль)
            send_recovery_email_mock(email, code)
            
            success_text.value = f"Код отправлен на {email}"
            success_text.visible = True
            error_text.visible = False
            page.update()
            
            # Переходим к вводу кода
            import time
            time.sleep(1)
            show_enter_code_screen(user.id, email)
        
        container = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.LOCK_RESET, size=40, color=PRIMARY_COLOR),
                        ft.Text("Восстановление", size=32, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=15, alignment="center"),
                    margin=ft.margin.only(bottom=20),
                ),
                ft.Text(
                    "Введите email для получения кода",
                    size=14,
                    color=TEXT_SECONDARY,
                    text_align="center",
                ),
                ft.Container(height=25),
                email_field,
                ft.Container(height=10),
                error_text,
                success_text,
                ft.Container(height=20),
                ft.ElevatedButton(
                    text="ОТПРАВИТЬ КОД",
                    width=350,
                    height=50,
                    style=ft.ButtonStyle(
                        bgcolor=PRIMARY_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=send_code,
                ),
                ft.Container(height=20),
                ft.TextButton(
                    text="← Вернуться ко входу",
                    style=ft.ButtonStyle(color=TEXT_SECONDARY),
                    on_click=lambda e: show_login_screen(),
                ),
            ], spacing=0, alignment="center", horizontal_alignment="center"),
            padding=ft.padding.symmetric(horizontal=40, vertical=60),
            bgcolor=DARK_BG,
            border_radius=16,
            width=500,
            shadow=ft.BoxShadow(blur_radius=20, spread_radius=0, color="#00000080", offset=ft.Offset(0, 8)),
            alignment=ft.alignment.center,
            expand=True,
        )
        page.add(container)
        page.update()

    def show_enter_code_screen(user_id, email):
        """Экран ввода кода восстановления"""
        page.controls.clear()
        
        code_field = ft.TextField(
            label="Код подтверждения",
            hint_text="Введите 6-значный код",
            width=350,
            bgcolor=CARD_BG,
            border_color=PRIMARY_COLOR,
            focused_border_color=SECONDARY_COLOR,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            text_style=ft.TextStyle(color=TEXT_PRIMARY, size=24, weight="bold"),
            prefix_icon=ft.icons.SECURITY,
            text_align=ft.TextAlign.CENTER,
            max_length=6,
        )
        
        error_text = ft.Text("", color=ACCENT_COLOR, visible=False, size=13)
        
        def verify_code(e):
            entered_code = code_field.value.strip()
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                error_text.value = "Ошибка: пользователь не найден"
                error_text.visible = True
                page.update()
                return
            
            is_valid, message = verify_recovery_code(
                user.recovery_code,
                user.recovery_code_expires,
                entered_code
            )
            
            if not is_valid:
                error_text.value = message
                error_text.visible = True
                page.update()
                return
            
            # Код верный - переходим к смене пароля
            show_new_password_screen(user_id)
        
        container = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.VERIFIED_USER, size=40, color=SUCCESS_COLOR),
                        ft.Text("Подтверждение", size=32, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=15, alignment="center"),
                    margin=ft.margin.only(bottom=20),
                ),
                ft.Text(
                    f"Код отправлен на {email}",
                    size=14,
                    color=TEXT_SECONDARY,
                    text_align="center",
                ),
                ft.Container(height=25),
                code_field,
                ft.Container(height=10),
                error_text,
                ft.Container(height=20),
                ft.ElevatedButton(
                    text="ПОДТВЕРДИТЬ",
                    width=350,
                    height=50,
                    style=ft.ButtonStyle(
                        bgcolor=SUCCESS_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=verify_code,
                ),
                ft.Container(height=15),
                ft.Text("Код действителен 10 минут", size=12, color=TEXT_SECONDARY),
                ft.Container(height=20),
                ft.TextButton(
                    text="← Вернуться ко входу",
                    style=ft.ButtonStyle(color=TEXT_SECONDARY),
                    on_click=lambda e: show_login_screen(),
                ),
            ], spacing=0, alignment="center", horizontal_alignment="center"),
            padding=ft.padding.symmetric(horizontal=40, vertical=60),
            bgcolor=DARK_BG,
            border_radius=16,
            width=500,
            shadow=ft.BoxShadow(blur_radius=20, spread_radius=0, color="#00000080", offset=ft.Offset(0, 8)),
            alignment=ft.alignment.center,
            expand=True,
        )
        page.add(container)
        page.update()

    def show_new_password_screen(user_id):
        """Экран установки нового пароля"""
        page.controls.clear()
        
        new_password_field = ft.TextField(
            label="Новый пароль",
            width=350,
            password=True,
            bgcolor=CARD_BG,
            border_color=PRIMARY_COLOR,
            focused_border_color=SECONDARY_COLOR,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            text_style=ft.TextStyle(color=TEXT_PRIMARY),
            prefix_icon=ft.icons.LOCK,
        )
        
        confirm_password_field = ft.TextField(
            label="Подтвердите пароль",
            width=350,
            password=True,
            bgcolor=CARD_BG,
            border_color=PRIMARY_COLOR,
            focused_border_color=SECONDARY_COLOR,
            label_style=ft.TextStyle(color=TEXT_SECONDARY),
            text_style=ft.TextStyle(color=TEXT_PRIMARY),
            prefix_icon=ft.icons.LOCK_OUTLINE,
        )
        
        error_text = ft.Text("", color=ACCENT_COLOR, visible=False, size=13)
        
        def change_password(e):
            new_pass = new_password_field.value
            confirm_pass = confirm_password_field.value
            
            if not new_pass or len(new_pass) < 4:
                error_text.value = "Пароль должен быть минимум 4 символа"
                error_text.visible = True
                page.update()
                return
            
            if new_pass != confirm_pass:
                error_text.value = "Пароли не совпадают"
                error_text.visible = True
                page.update()
                return
            
            # Обновляем пароль
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user.password = new_pass
                user.recovery_code = None
                user.recovery_code_expires = None
                session.commit()
                
                # Также обновляем в sqlite (для совместимости)
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_pass, user_id))
                conn.commit()
                conn.close()
            
            # Показываем успех и переходим ко входу
            show_password_changed_success()
        
        container = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.PASSWORD, size=40, color=PRIMARY_COLOR),
                        ft.Text("Новый пароль", size=32, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=15, alignment="center"),
                    margin=ft.margin.only(bottom=20),
                ),
                ft.Text(
                    "Придумайте новый надёжный пароль",
                    size=14,
                    color=TEXT_SECONDARY,
                    text_align="center",
                ),
                ft.Container(height=25),
                new_password_field,
                ft.Container(height=15),
                confirm_password_field,
                ft.Container(height=10),
                error_text,
                ft.Container(height=20),
                ft.ElevatedButton(
                    text="СОХРАНИТЬ ПАРОЛЬ",
                    width=350,
                    height=50,
                    style=ft.ButtonStyle(
                        bgcolor=SUCCESS_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=change_password,
                ),
            ], spacing=0, alignment="center", horizontal_alignment="center"),
            padding=ft.padding.symmetric(horizontal=40, vertical=60),
            bgcolor=DARK_BG,
            border_radius=16,
            width=500,
            shadow=ft.BoxShadow(blur_radius=20, spread_radius=0, color="#00000080", offset=ft.Offset(0, 8)),
            alignment=ft.alignment.center,
            expand=True,
        )
        page.add(container)
        page.update()

    def show_password_changed_success():
        """Экран успешной смены пароля"""
        page.controls.clear()
        
        container = ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.CHECK_CIRCLE, size=80, color=SUCCESS_COLOR),
                ft.Container(height=20),
                ft.Text("Пароль изменён!", size=28, weight="bold", color=TEXT_PRIMARY),
                ft.Container(height=10),
                ft.Text(
                    "Теперь вы можете войти с новым паролем",
                    size=14,
                    color=TEXT_SECONDARY,
                    text_align="center",
                ),
                ft.Container(height=30),
                ft.ElevatedButton(
                    text="ВОЙТИ В АККАУНТ",
                    width=350,
                    height=50,
                    style=ft.ButtonStyle(
                        bgcolor=PRIMARY_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e: show_login_screen(),
                ),
            ], spacing=0, alignment="center", horizontal_alignment="center"),
            padding=ft.padding.symmetric(horizontal=40, vertical=60),
            bgcolor=DARK_BG,
            border_radius=16,
            width=500,
            shadow=ft.BoxShadow(blur_radius=20, spread_radius=0, color="#00000080", offset=ft.Offset(0, 8)),
            alignment=ft.alignment.center,
            expand=True,
        )
        page.add(container)
        page.update()

    # Экран входа
    def show_login_screen():
        page.controls.clear()
        login_container = ft.Container(
            content=ft.Column([
                # Logo/Заголовок
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=40, color=PRIMARY_COLOR),
                        ft.Text("Invest Wallet", size=36, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=15, alignment="center"),
                    margin=ft.margin.only(bottom=30),
                ),
                # Подзаголовок
                ft.Text(
                    "Управляй своим криптопортфелем",
                    size=16,
                    color=TEXT_SECONDARY,
                    text_align="center",
                ),
                ft.Container(height=30),
                # Форма входа
                login_username_field,
                ft.Container(height=15),
                login_password_field,
                ft.Container(height=8),
                # Забыли пароль?
                ft.Container(
                    content=ft.TextButton(
                        text="Забыли пароль?",
                        style=ft.ButtonStyle(color=ACCENT_COLOR),
                        on_click=lambda e: show_forgot_password_screen(),
                    ),
                    alignment=ft.alignment.center_right,
                    width=350,
                ),
                ft.Container(height=15),
                # Кнопка входа
                login_button,
                ft.Container(height=15),
                # Разделитель
                ft.Row([
                    ft.Container(height=1, width=50, bgcolor=BORDER_COLOR),
                    ft.Text("или", color=TEXT_SECONDARY, size=12),
                    ft.Container(height=1, width=50, bgcolor=BORDER_COLOR),
                ], alignment="center", spacing=10),
                ft.Container(height=15),
                # Кнопка регистрации
                ft.Container(
                    content=ft.Row([
                        ft.Text("Нет аккаунта?", color=TEXT_SECONDARY),
                        go_to_register_button,
                    ], spacing=5, alignment="center"),
                    alignment=ft.alignment.center,
                ),
            ], spacing=0, alignment="center", horizontal_alignment="center"),
            padding=ft.padding.symmetric(horizontal=40, vertical=60),
            bgcolor=DARK_BG,
            border_radius=16,
            width=500,
            shadow=ft.BoxShadow(
                blur_radius=20,
                spread_radius=0,
                color="#00000080",
                offset=ft.Offset(0, 8),
            ),
            alignment=ft.alignment.center,
            expand=True,
        )
        page.add(login_container)
        page.update()

    # Экран регистрации
    def show_register_screen():
        page.controls.clear()
        
        # Доступные иконки для аватара
        avatar_icons = [
            ("PERSON", ft.icons.PERSON),
            ("FACE", ft.icons.FACE),
            ("ACCOUNT_CIRCLE", ft.icons.ACCOUNT_CIRCLE),
            ("SENTIMENT_VERY_SATISFIED", ft.icons.SENTIMENT_VERY_SATISFIED),
            ("ROCKET_LAUNCH", ft.icons.ROCKET_LAUNCH),
            ("DIAMOND", ft.icons.DIAMOND),
            ("STAR", ft.icons.STAR),
            ("BOLT", ft.icons.BOLT),
        ]
        
        avatar_colors = ["#00d4ff", "#00ff88", "#ff3366", "#ffd700", "#9b59b6", "#e74c3c", "#3498db", "#1abc9c"]
        
        # Состояние выбора
        selected_icon = {"name": "PERSON", "icon": ft.icons.PERSON}
        selected_color = {"value": "#00d4ff"}
        
        # Поля регистрации
        reg_username = ft.TextField(
            label="Имя пользователя *",
            width=400,
            bgcolor=CARD_BG,
            border_color=PRIMARY_COLOR,
            focused_border_color=SECONDARY_COLOR,
            prefix_icon=ft.icons.PERSON,
        )
        
        reg_password = ft.TextField(
            label="Пароль *",
            width=400,
            password=True,
            bgcolor=CARD_BG,
            border_color=PRIMARY_COLOR,
            focused_border_color=SECONDARY_COLOR,
            prefix_icon=ft.icons.LOCK,
        )
        
        reg_email = ft.TextField(
            label="Email *",
            hint_text="Для восстановления пароля",
            width=400,
            bgcolor=CARD_BG,
            border_color=PRIMARY_COLOR,
            focused_border_color=SECONDARY_COLOR,
            prefix_icon=ft.icons.EMAIL,
        )
        
        reg_fullname = ft.TextField(
            label="Полное имя",
            width=400,
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            focused_border_color=SECONDARY_COLOR,
            prefix_icon=ft.icons.BADGE,
        )
        
        reg_phone = ft.TextField(
            label="Телефон",
            width=400,
            bgcolor=CARD_BG,
            border_color=BORDER_COLOR,
            focused_border_color=SECONDARY_COLOR,
            prefix_icon=ft.icons.PHONE,
        )
        
        error_text = ft.Text("", color=ACCENT_COLOR, visible=False, size=13)
        
        # Превью аватара
        avatar_preview = ft.Container(
            content=ft.CircleAvatar(
                content=ft.Icon(ft.icons.PERSON, size=40, color=DARK_BG),
                radius=50,
                bgcolor=selected_color["value"],
            ),
            alignment=ft.alignment.center,
        )
        
        def update_avatar_preview():
            avatar_preview.content = ft.CircleAvatar(
                content=ft.Icon(selected_icon["icon"], size=40, color=DARK_BG),
                radius=50,
                bgcolor=selected_color["value"],
            )
            page.update()
        
        def select_icon(icon_name, icon_ref):
            selected_icon["name"] = icon_name
            selected_icon["icon"] = icon_ref
            update_avatar_preview()
        
        def select_color(color):
            selected_color["value"] = color
            update_avatar_preview()
        
        # Сетка иконок
        icon_grid = ft.Row([
            ft.Container(
                content=ft.Icon(icon_ref, size=28, color=TEXT_PRIMARY),
                width=45,
                height=45,
                border_radius=8,
                bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                border=ft.border.all(2, PRIMARY_COLOR if selected_icon["name"] == icon_name else BORDER_COLOR),
                alignment=ft.alignment.center,
                on_click=lambda e, n=icon_name, i=icon_ref: select_icon(n, i),
                ink=True,
            ) for icon_name, icon_ref in avatar_icons
        ], spacing=8, wrap=True)
        
        # Сетка цветов
        color_grid = ft.Row([
            ft.Container(
                width=35,
                height=35,
                border_radius=20,
                bgcolor=color,
                border=ft.border.all(3, TEXT_PRIMARY if selected_color["value"] == color else "transparent"),
                on_click=lambda e, c=color: select_color(c),
                ink=True,
            ) for color in avatar_colors
        ], spacing=8)
        
        def do_register(e):
            username = reg_username.value.strip()
            password = reg_password.value
            email = reg_email.value.strip()
            fullname = reg_fullname.value.strip()
            phone = reg_phone.value.strip()
            
            if not username or not password:
                error_text.value = "Имя пользователя и пароль обязательны"
                error_text.visible = True
                page.update()
                return
            
            if not email:
                error_text.value = "Email обязателен для восстановления пароля"
                error_text.visible = True
                page.update()
                return
            
            if len(password) < 4:
                error_text.value = "Пароль должен быть минимум 4 символа"
                error_text.visible = True
                page.update()
                return
            
            # Проверяем существование пользователя
            existing = session.query(User).filter(User.name == username).first()
            if existing:
                error_text.value = "Пользователь с таким именем уже существует"
                error_text.visible = True
                page.update()
                return
            
            # Создаем пользователя
            try:
                new_user = User(
                    name=username,
                    password=password,
                    email=email,
                    full_name=fullname or "Инвестор",
                    phone=phone,
                    avatar_type="icon",
                    avatar_icon=selected_icon["name"],
                    avatar_path=None,
                    avatar_color=selected_color["value"],
                    balance=0,
                    country="Россия",
                    bio="Инвестор криптовалют",
                    registration_date=datetime.now(),
                )
                session.add(new_user)
                session.commit()
                
                # Переходим ко входу
                show_registration_success()
                
            except Exception as ex:
                error_text.value = f"Ошибка регистрации: {ex}"
                error_text.visible = True
                page.update()
        
        register_container = ft.Container(
            content=ft.Column([
                # Заголовок
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.PERSON_ADD, size=36, color=PRIMARY_COLOR),
                        ft.Text("Регистрация", size=32, weight="bold", color=TEXT_PRIMARY),
                    ], spacing=15, alignment="center"),
                    margin=ft.margin.only(bottom=15),
                ),
                
                # Аватар
                ft.Container(
                    content=ft.Column([
                        avatar_preview,
                        ft.Container(height=10),
                        ft.Text("Выберите иконку", size=12, color=TEXT_SECONDARY),
                        icon_grid,
                        ft.Container(height=8),
                        ft.Text("Выберите цвет", size=12, color=TEXT_SECONDARY),
                        color_grid,
                    ], alignment="center", horizontal_alignment="center", spacing=5),
                    padding=15,
                    bgcolor=ft.colors.with_opacity(0.05, BORDER_COLOR),
                    border_radius=12,
                    border=ft.border.all(1, BORDER_COLOR),
                ),
                
                ft.Container(height=15),
                
                # Поля
                reg_username,
                ft.Container(height=10),
                reg_password,
                ft.Container(height=10),
                reg_email,
                ft.Container(height=10),
                reg_fullname,
                ft.Container(height=10),
                reg_phone,
                
                ft.Container(height=5),
                error_text,
                ft.Container(height=15),
                
                # Кнопка
                ft.ElevatedButton(
                    text="СОЗДАТЬ АККАУНТ",
                    width=400,
                    height=50,
                    style=ft.ButtonStyle(
                        bgcolor=SUCCESS_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=do_register,
                ),
                
                ft.Container(height=15),
                ft.TextButton(
                    text="← Уже есть аккаунт? Войти",
                    style=ft.ButtonStyle(color=PRIMARY_COLOR),
                    on_click=lambda e: show_login_screen(),
                ),
            ], spacing=0, alignment="center", horizontal_alignment="center", scroll="auto"),
            padding=ft.padding.symmetric(horizontal=40, vertical=30),
            bgcolor=DARK_BG,
            border_radius=16,
            width=550,
            height=750,
            shadow=ft.BoxShadow(blur_radius=20, spread_radius=0, color="#00000080", offset=ft.Offset(0, 8)),
            alignment=ft.alignment.center,
        )
        
        page.add(ft.Container(content=register_container, alignment=ft.alignment.center, expand=True))
        page.update()

    def show_registration_success():
        """Экран успешной регистрации"""
        page.controls.clear()
        
        container = ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.CELEBRATION, size=80, color=SUCCESS_COLOR),
                ft.Container(height=20),
                ft.Text("Аккаунт создан!", size=28, weight="bold", color=TEXT_PRIMARY),
                ft.Container(height=10),
                ft.Text(
                    "Добро пожаловать в Invest Wallet!",
                    size=14,
                    color=TEXT_SECONDARY,
                    text_align="center",
                ),
                ft.Container(height=30),
                ft.ElevatedButton(
                    text="ВОЙТИ В АККАУНТ",
                    width=350,
                    height=50,
                    style=ft.ButtonStyle(
                        bgcolor=PRIMARY_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e: show_login_screen(),
                ),
            ], spacing=0, alignment="center", horizontal_alignment="center"),
            padding=ft.padding.symmetric(horizontal=40, vertical=60),
            bgcolor=DARK_BG,
            border_radius=16,
            width=500,
            shadow=ft.BoxShadow(blur_radius=20, spread_radius=0, color="#00000080", offset=ft.Offset(0, 8)),
            alignment=ft.alignment.center,
            expand=True,
        )
        page.add(container)
        page.update()

    # Логика входа
    def login_user():
        try:
            username = login_username_field.value
            global user_name
            user_name = str(username)
            password = login_password_field.value

            if not username or not password:
                snack = ft.SnackBar(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.WARNING, size=20, color=ACCENT_COLOR),
                            ft.Text("Введите имя пользователя и пароль!", color=TEXT_PRIMARY, size=14),
                        ], spacing=10),
                        padding=10,
                    ),
                    bgcolor=CARD_BG,
                    duration=3000,
                )
                page.overlay.append(snack)
                snack.open = True
                page.update()
                return

            user = check_user(username, password)
            if not user:
                snack = ft.SnackBar(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.ERROR, size=20, color=ACCENT_COLOR),
                            ft.Text("Пользователь не найден!", color=TEXT_PRIMARY, size=14),
                        ], spacing=10),
                        padding=10,
                    ),
                    bgcolor=CARD_BG,
                    duration=3000,
                )
                page.overlay.append(snack)
                snack.open = True
                page.update()
                return

            # Если пользователь найден, показываем профиль
            show_profile(page, username)
        except ValueError as e:
            snack_bar = ft.SnackBar(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ERROR, size=20, color=ACCENT_COLOR),
                        ft.Text(str(e), color=TEXT_PRIMARY, size=14),
                    ], spacing=10),
                    padding=10,
                ),
                bgcolor=CARD_BG,
                duration=3000,
            )
            page.overlay.append(snack_bar)
            snack_bar.open = True
        except LookupError as e:
            snack_bar = ft.SnackBar(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ERROR, size=20, color=ACCENT_COLOR),
                        ft.Text(str(e), color=TEXT_PRIMARY, size=14),
                    ], spacing=10),
                    padding=10,
                ),
                bgcolor=CARD_BG,
                duration=3000,
            )
            page.overlay.append(snack_bar)
            snack_bar.open = True

    # Логика регистрации
    def register_user():
        username = register_username_field.value
        user_name = username
        password = register_password_field.value

        if not username or not password:
            snack = ft.SnackBar(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.WARNING, size=20, color=ACCENT_COLOR),
                        ft.Text("Введите имя пользователя и пароль!", color=TEXT_PRIMARY, size=14),
                    ], spacing=10),
                    padding=10,
                ),
                bgcolor=CARD_BG,
                duration=3000,
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return

        try:
            add_user(username, password)
            snack = ft.SnackBar(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.CHECK_CIRCLE, size=20, color=SUCCESS_COLOR),
                        ft.Text("Пользователь успешно зарегистрирован!", color=TEXT_PRIMARY, size=14),
                    ], spacing=10),
                    padding=10,
                ),
                bgcolor=CARD_BG,
                duration=3000,
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()
            show_login_screen()
        except sqlite3.IntegrityError:
            snack = ft.SnackBar(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ERROR, size=20, color=ACCENT_COLOR),
                        ft.Text("Пользователь с таким именем уже существует!", color=TEXT_PRIMARY, size=14),
                    ], spacing=10),
                    padding=10,
                ),
                bgcolor=CARD_BG,
                duration=3000,
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()

    # Изначально показываем экран входа
    show_login_screen()


if __name__ == "__main__":
    ft.app(target=main)
