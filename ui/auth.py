"""
Экраны авторизации: вход, регистрация, восстановление пароля
"""
import flet as ft
from datetime import datetime, timedelta

from ui.config import (
    DARK_BG, CARD_BG, PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    EXCHANGE_COLORS, EXCHANGE_NAMES, AVATAR_COLORS,
)
from backend.models import User, ExchangeAPIKey, session
from backend.email_service import generate_recovery_code, send_recovery_email_mock, verify_recovery_code
from backend.api import test_exchange_connection


def show_login_screen(page: ft.Page, current_user: dict, show_main_screen_callback, 
                      show_register_callback, show_forgot_password_callback):
    """Экран входа в систему"""
    page.controls.clear()
    
    username_field = ft.TextField(
        label="Имя пользователя",
        width=380,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.PERSON,
        text_size=15,
        border_radius=12,
    )
    
    password_field = ft.TextField(
        label="Пароль",
        width=380,
        height=55,
        password=True,
        can_reveal_password=True,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.LOCK,
        text_size=15,
        border_radius=12,
    )
    
    error_text = ft.Text("", color=ACCENT_COLOR, visible=False, size=13)
    
    def do_login(e):
        username = username_field.value.strip()
        password = password_field.value
        
        if not username or not password:
            error_text.value = "Заполните все поля"
            error_text.visible = True
            page.update()
            return
        
        user = session.query(User).filter_by(name=username, password=password).first()
        if user:
            user.last_login = datetime.now()
            session.commit()
            current_user["user"] = user
            show_main_screen_callback()
        else:
            error_text.value = "Неверное имя пользователя или пароль"
            error_text.visible = True
            page.update()
    
    # Логотип с анимированным эффектом
    logo_section = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=60, color=DARK_BG),
                width=100,
                height=100,
                border_radius=50,
                gradient=ft.LinearGradient(
                    colors=[PRIMARY_COLOR, SECONDARY_COLOR],
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                ),
                alignment=ft.alignment.center,
                shadow=ft.BoxShadow(blur_radius=30, color=ft.colors.with_opacity(0.4, PRIMARY_COLOR)),
            ),
            ft.Container(height=15),
            ft.Text("Invest Wallet", size=36, weight="bold", color=TEXT_PRIMARY),
            ft.Text("Управление криптопортфелем", size=14, color=TEXT_SECONDARY),
        ], horizontal_alignment="center"),
        padding=ft.padding.only(bottom=30),
    )
    
    login_container = ft.Container(
        content=ft.Column([
            logo_section,
            username_field,
            ft.Container(height=15),
            password_field,
            ft.Container(height=8),
            error_text,
            ft.Container(height=25),
            ft.ElevatedButton(
                text="ВОЙТИ",
                width=380,
                height=55,
                style=ft.ButtonStyle(
                    bgcolor=PRIMARY_COLOR,
                    color=DARK_BG,
                    text_style=ft.TextStyle(size=16, weight="bold"),
                    shape=ft.RoundedRectangleBorder(radius=12),
                    shadow_color=ft.colors.with_opacity(0.3, PRIMARY_COLOR),
                    elevation=8,
                ),
                on_click=do_login,
            ),
            ft.Container(height=15),
            ft.TextButton(
                text="Забыли пароль?",
                style=ft.ButtonStyle(color=ACCENT_COLOR),
                on_click=lambda e: show_forgot_password_callback(),
            ),
            ft.Container(height=20),
            ft.Row([
                ft.Container(height=1, bgcolor=BORDER_COLOR, expand=True),
                ft.Text("  или  ", size=12, color=TEXT_SECONDARY),
                ft.Container(height=1, bgcolor=BORDER_COLOR, expand=True),
            ], width=380),
            ft.Container(height=20),
            ft.ElevatedButton(
                text="Создать аккаунт",
                width=380,
                height=50,
                style=ft.ButtonStyle(
                    bgcolor=SECONDARY_COLOR,
                    color=DARK_BG,
                    text_style=ft.TextStyle(size=15, weight="bold"),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
                on_click=lambda e: show_register_callback(),
            ),
        ], alignment="center", horizontal_alignment="center"),
        padding=40,
        bgcolor=CARD_BG,
        border_radius=20,
        width=500,
        border=ft.border.all(1, BORDER_COLOR),
        shadow=ft.BoxShadow(blur_radius=40, spread_radius=5, color="#00000060"),
    )
    
    page.add(ft.Container(content=login_container, expand=True, alignment=ft.alignment.center))
    page.update()


def show_forgot_password_screen(page: ft.Page, show_login_callback):
    """Экран восстановления пароля"""
    page.controls.clear()
    
    current_step = {"value": 1}  # 1 - ввод email, 2 - ввод кода, 3 - новый пароль
    user_data = {"user": None, "code": None}
    
    email_field = ft.TextField(
        label="Email адрес",
        width=400,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.EMAIL,
        text_size=15,
        border_radius=12,
        hint_text="Введите email вашего аккаунта",
    )
    
    code_field = ft.TextField(
        label="Код подтверждения",
        width=400,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=SUCCESS_COLOR,
        prefix_icon=ft.icons.SECURITY,
        text_size=20,
        text_align="center",
        border_radius=12,
        hint_text="6 цифр",
    )
    
    new_password_field = ft.TextField(
        label="Новый пароль",
        width=400,
        height=55,
        password=True,
        can_reveal_password=True,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.LOCK_OUTLINE,
        text_size=15,
        border_radius=12,
    )
    
    confirm_password_field = ft.TextField(
        label="Подтвердите пароль",
        width=400,
        height=55,
        password=True,
        can_reveal_password=True,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.LOCK,
        text_size=15,
        border_radius=12,
    )
    
    error_text = ft.Text("", color=ACCENT_COLOR, visible=False, size=13)
    success_text = ft.Text("", color=SUCCESS_COLOR, visible=False, size=13)
    step_content = ft.Container()
    
    def update_content():
        if current_step["value"] == 1:
            step_content.content = ft.Column([
                ft.Icon(ft.icons.MARK_EMAIL_READ, size=70, color=PRIMARY_COLOR),
                ft.Container(height=20),
                ft.Text("Восстановление пароля", size=26, weight="bold", color=TEXT_PRIMARY),
                ft.Text("Введите email, указанный при регистрации", size=14, color=TEXT_SECONDARY),
                ft.Container(height=30),
                email_field,
                ft.Container(height=10),
                error_text,
                success_text,
                ft.Container(height=25),
                ft.ElevatedButton(
                    text="ОТПРАВИТЬ КОД",
                    width=400,
                    height=55,
                    style=ft.ButtonStyle(
                        bgcolor=PRIMARY_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    on_click=send_code,
                ),
            ], horizontal_alignment="center")
        
        elif current_step["value"] == 2:
            step_content.content = ft.Column([
                ft.Container(
                    content=ft.Icon(ft.icons.VERIFIED_USER, size=50, color=DARK_BG),
                    width=90,
                    height=90,
                    border_radius=45,
                    bgcolor=SUCCESS_COLOR,
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=20),
                ft.Text("Введите код", size=26, weight="bold", color=TEXT_PRIMARY),
                ft.Text(f"Код отправлен на {email_field.value}", size=14, color=TEXT_SECONDARY),
                ft.Container(height=30),
                code_field,
                ft.Container(height=10),
                error_text,
                ft.Container(height=25),
                ft.ElevatedButton(
                    text="ПОДТВЕРДИТЬ",
                    width=400,
                    height=55,
                    style=ft.ButtonStyle(
                        bgcolor=SUCCESS_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    on_click=verify_code_handler,
                ),
                ft.Container(height=15),
                ft.TextButton(
                    text="Отправить код повторно",
                    style=ft.ButtonStyle(color=TEXT_SECONDARY),
                    on_click=resend_code,
                ),
            ], horizontal_alignment="center")
        
        elif current_step["value"] == 3:
            step_content.content = ft.Column([
                ft.Container(
                    content=ft.Icon(ft.icons.LOCK_RESET, size=50, color=DARK_BG),
                    width=90,
                    height=90,
                    border_radius=45,
                    bgcolor=PRIMARY_COLOR,
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=20),
                ft.Text("Новый пароль", size=26, weight="bold", color=TEXT_PRIMARY),
                ft.Text("Придумайте надежный пароль", size=14, color=TEXT_SECONDARY),
                ft.Container(height=30),
                new_password_field,
                ft.Container(height=15),
                confirm_password_field,
                ft.Container(height=10),
                error_text,
                ft.Container(height=25),
                ft.ElevatedButton(
                    text="СОХРАНИТЬ ПАРОЛЬ",
                    width=400,
                    height=55,
                    style=ft.ButtonStyle(
                        bgcolor=SUCCESS_COLOR,
                        color=DARK_BG,
                        text_style=ft.TextStyle(size=16, weight="bold"),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    on_click=save_new_password,
                ),
            ], horizontal_alignment="center")
        
        page.update()
    
    def send_code(e):
        email = email_field.value.strip()
        
        if not email:
            error_text.value = "Введите email"
            error_text.visible = True
            success_text.visible = False
            page.update()
            return
        
        # Ищем пользователя
        user = session.query(User).filter_by(email=email).first()
        if not user:
            error_text.value = "Пользователь с таким email не найден"
            error_text.visible = True
            success_text.visible = False
            page.update()
            return
        
        # Генерируем код
        code = generate_recovery_code()
        user.recovery_code = code
        user.recovery_code_expires = datetime.now() + timedelta(minutes=10)
        session.commit()
        
        user_data["user"] = user
        user_data["code"] = code
        
        # Отправляем (в демо режиме показываем код)
        send_recovery_email_mock(email, code)
        
        error_text.visible = False
        current_step["value"] = 2
        update_content()
    
    def resend_code(e):
        if user_data["user"]:
            code = generate_recovery_code()
            user_data["user"].recovery_code = code
            user_data["user"].recovery_code_expires = datetime.now() + timedelta(minutes=10)
            session.commit()
            user_data["code"] = code
            send_recovery_email_mock(email_field.value, code)
            
            error_text.value = "Новый код отправлен!"
            error_text.color = SUCCESS_COLOR
            error_text.visible = True
            page.update()
    
    def verify_code_handler(e):
        entered_code = code_field.value.strip()
        
        if not entered_code:
            error_text.value = "Введите код"
            error_text.visible = True
            page.update()
            return
        
        # Проверяем код
        user = user_data["user"]
        success, msg = verify_recovery_code(user.recovery_code, user.recovery_code_expires, entered_code)
        
        if success:
            error_text.visible = False
            current_step["value"] = 3
            update_content()
        else:
            error_text.value = msg
            error_text.color = ACCENT_COLOR
            error_text.visible = True
            page.update()
    
    def save_new_password(e):
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
        
        # Сохраняем новый пароль
        user_data["user"].password = new_pass
        user_data["user"].recovery_code = None
        user_data["user"].recovery_code_expires = None
        session.commit()
        
        show_login_callback()
    
    update_content()
    
    # Прогресс-индикатор
    progress_dots = ft.Row([
        ft.Container(
            width=12, height=12,
            border_radius=6,
            bgcolor=PRIMARY_COLOR if current_step["value"] >= 1 else BORDER_COLOR,
        ),
        ft.Container(width=30, height=2, bgcolor=PRIMARY_COLOR if current_step["value"] >= 2 else BORDER_COLOR),
        ft.Container(
            width=12, height=12,
            border_radius=6,
            bgcolor=SUCCESS_COLOR if current_step["value"] >= 2 else BORDER_COLOR,
        ),
        ft.Container(width=30, height=2, bgcolor=SUCCESS_COLOR if current_step["value"] >= 3 else BORDER_COLOR),
        ft.Container(
            width=12, height=12,
            border_radius=6,
            bgcolor=SUCCESS_COLOR if current_step["value"] >= 3 else BORDER_COLOR,
        ),
    ], alignment="center")
    
    container = ft.Container(
        content=ft.Column([
            progress_dots,
            ft.Container(height=30),
            step_content,
            ft.Container(height=30),
            ft.TextButton(
                text="← Вернуться к входу",
                style=ft.ButtonStyle(color=TEXT_SECONDARY),
                on_click=lambda e: show_login_callback(),
            ),
        ], horizontal_alignment="center"),
        padding=50,
        bgcolor=CARD_BG,
        border_radius=20,
        width=520,
        border=ft.border.all(1, BORDER_COLOR),
        shadow=ft.BoxShadow(blur_radius=40, spread_radius=5, color="#00000060"),
    )
    
    page.add(ft.Container(content=container, expand=True, alignment=ft.alignment.center))
    page.update()


def show_register_screen(page: ft.Page, current_user: dict, 
                         show_login_callback, show_main_screen_callback):
    """Экран регистрации"""
    page.controls.clear()
    
    current_step = {"value": 1}  # 1-Профиль, 2-Аватар, 3-Биржи, 4-API ключи
    selected_exchanges = {"list": []}
    exchange_keys_data = {"data": {}}
    
    # Аватар - иконки и цвета
    avatar_icons_list = [
        ("PERSON", ft.icons.PERSON),
        ("FACE", ft.icons.FACE),
        ("ROCKET_LAUNCH", ft.icons.ROCKET_LAUNCH),
        ("DIAMOND", ft.icons.DIAMOND),
        ("STAR", ft.icons.STAR),
        ("BOLT", ft.icons.BOLT),
        ("FAVORITE", ft.icons.FAVORITE),
        ("SHIELD", ft.icons.SHIELD),
    ]
    avatar_colors_list = AVATAR_COLORS
    selected_avatar = {"icon": "PERSON", "color": "#00d4ff"}
    
    # Поля Step 1 - Основные данные (обязательные)
    username_field = ft.TextField(
        label="Имя пользователя *",
        width=420,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.PERSON,
        hint_text="Уникальный логин",
        border_radius=12,
    )
    
    password_field = ft.TextField(
        label="Пароль *",
        width=420,
        height=55,
        password=True,
        can_reveal_password=True,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.LOCK,
        hint_text="Минимум 4 символа",
        border_radius=12,
    )
    
    email_field = ft.TextField(
        label="Email *",
        width=420,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.EMAIL,
        hint_text="Для восстановления пароля",
        border_radius=12,
    )
    
    full_name_field = ft.TextField(
        label="Полное имя *",
        width=420,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.BADGE,
        hint_text="Фамилия Имя Отчество",
        border_radius=12,
    )
    
    phone_field = ft.TextField(
        label="Телефон",
        width=200,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.PHONE,
        hint_text="+7...",
        border_radius=12,
    )
    
    country_dropdown = ft.Dropdown(
        label="Страна",
        width=200,
        height=55,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        value="Россия",
        border_radius=12,
        options=[
            ft.dropdown.Option("Россия"),
            ft.dropdown.Option("Казахстан"),
            ft.dropdown.Option("Беларусь"),
            ft.dropdown.Option("Украина"),
            ft.dropdown.Option("Узбекистан"),
            ft.dropdown.Option("Другая"),
        ],
    )
    
    error_text = ft.Text("", color=ACCENT_COLOR, visible=False, size=13)
    step_content = ft.Container(expand=True)
    progress_container = ft.Container()
    buttons_container = ft.Container()
    
    def update_progress():
        """Обновляет индикатор прогресса"""
        steps = [
            ("1", "Данные", PRIMARY_COLOR),
            ("2", "Аватар", SECONDARY_COLOR),
            ("3", "Биржи", WARNING_COLOR),
            ("4", "Ключи", SUCCESS_COLOR),
        ]
        
        progress_items = []
        for i, (num, label, color) in enumerate(steps):
            step_num = i + 1
            is_active = current_step["value"] >= step_num
            is_current = current_step["value"] == step_num
            
            progress_items.append(
                ft.Column([
                    ft.Container(
                        content=ft.Text(num, size=14, weight="bold", 
                                      color=DARK_BG if is_active else TEXT_SECONDARY),
                        width=36, height=36,
                        bgcolor=color if is_active else BORDER_COLOR,
                        border_radius=18,
                        alignment=ft.alignment.center,
                        border=ft.border.all(3, TEXT_PRIMARY) if is_current else None,
                        shadow=ft.BoxShadow(blur_radius=15, color=ft.colors.with_opacity(0.5, color)) if is_current else None,
                    ),
                    ft.Text(label, size=10, color=color if is_active else TEXT_SECONDARY, weight="bold" if is_current else None),
                ], horizontal_alignment="center", spacing=5)
            )
            
            if i < len(steps) - 1:
                progress_items.append(
                    ft.Container(
                        width=40, height=3, 
                        bgcolor=steps[i+1][2] if current_step["value"] > step_num else BORDER_COLOR,
                        border_radius=2,
                        margin=ft.margin.only(bottom=15),
                    )
                )
        
        progress_container.content = ft.Row(progress_items, alignment="center")
        page.update()
    
    def update_step_content():
        error_text.visible = False
        
        if current_step["value"] == 1:
            # Шаг 1: Основные данные
            step_content.content = ft.Column([
                ft.Container(
                    content=ft.Icon(ft.icons.PERSON_ADD, size=40, color=DARK_BG),
                    width=70, height=70,
                    border_radius=35,
                    bgcolor=PRIMARY_COLOR,
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=15),
                ft.Text("Создание аккаунта", size=22, weight="bold", color=TEXT_PRIMARY),
                ft.Text("Заполните информацию о себе", size=13, color=TEXT_SECONDARY),
                ft.Container(height=25),
                username_field,
                ft.Container(height=12),
                password_field,
                ft.Container(height=12),
                email_field,
                ft.Container(height=12),
                full_name_field,
                ft.Container(height=12),
                ft.Row([phone_field, country_dropdown], spacing=20),
                ft.Container(height=8),
                error_text,
            ], horizontal_alignment="center")
        
        elif current_step["value"] == 2:
            # Шаг 2: Выбор аватара
            def select_icon(icon_name):
                selected_avatar["icon"] = icon_name
                update_step_content()
            
            def select_color(color):
                selected_avatar["color"] = color
                update_step_content()
            
            # Предпросмотр аватара
            current_icon = next((ic for name, ic in avatar_icons_list if name == selected_avatar["icon"]), ft.icons.PERSON)
            
            avatar_preview = ft.Container(
                content=ft.Icon(current_icon, size=60, color=DARK_BG),
                width=120, height=120,
                border_radius=60,
                bgcolor=selected_avatar["color"],
                alignment=ft.alignment.center,
                shadow=ft.BoxShadow(blur_radius=30, color=ft.colors.with_opacity(0.5, selected_avatar["color"])),
                animate=ft.animation.Animation(300, "easeOut"),
            )
            
            # Сетка иконок
            icon_grid = ft.Row([
                ft.Container(
                    content=ft.Icon(ic, size=28, color=DARK_BG if selected_avatar["icon"] == name else TEXT_PRIMARY),
                    width=50, height=50,
                    border_radius=25,
                    bgcolor=selected_avatar["color"] if selected_avatar["icon"] == name else ft.colors.with_opacity(0.1, TEXT_PRIMARY),
                    border=ft.border.all(3, SUCCESS_COLOR) if selected_avatar["icon"] == name else None,
                    alignment=ft.alignment.center,
                    on_click=lambda e, n=name: select_icon(n),
                    ink=True,
                ) for name, ic in avatar_icons_list
            ], wrap=True, spacing=10, run_spacing=10, alignment="center")
            
            # Палитра цветов
            color_row = ft.Row([
                ft.Container(
                    width=45, height=45,
                    border_radius=23,
                    bgcolor=c,
                    border=ft.border.all(4, TEXT_PRIMARY if selected_avatar["color"] == c else "transparent"),
                    on_click=lambda e, col=c: select_color(col),
                    ink=True,
                    shadow=ft.BoxShadow(blur_radius=10, color=ft.colors.with_opacity(0.3, c)) if selected_avatar["color"] == c else None,
                ) for c in avatar_colors_list
            ], spacing=10, alignment="center")
            
            step_content.content = ft.Column([
                ft.Text("Выберите аватар", size=22, weight="bold", color=TEXT_PRIMARY),
                ft.Text("Персонализируйте свой профиль", size=13, color=TEXT_SECONDARY),
                ft.Container(height=30),
                avatar_preview,
                ft.Container(height=30),
                ft.Text("Иконка", size=14, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(height=10),
                icon_grid,
                ft.Container(height=25),
                ft.Text("Цвет", size=14, color=TEXT_SECONDARY, weight="bold"),
                ft.Container(height=10),
                color_row,
                ft.Container(height=10),
                error_text,
            ], horizontal_alignment="center")
        
        elif current_step["value"] == 3:
            # Шаг 3: Выбор бирж
            def toggle_exchange(exchange_name):
                if exchange_name in selected_exchanges["list"]:
                    selected_exchanges["list"].remove(exchange_name)
                else:
                    selected_exchanges["list"].append(exchange_name)
                update_step_content()
            
            # Создаем карточки бирж напрямую
            bybit_selected = "bybit" in selected_exchanges["list"]
            gateio_selected = "gateio" in selected_exchanges["list"]
            mexc_selected = "mexc" in selected_exchanges["list"]
            
            bybit_card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.CURRENCY_BITCOIN, size=28, color=DARK_BG),
                        width=55, height=55,
                        border_radius=12,
                        bgcolor="#f7a600",
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text("Bybit", size=18, weight="bold", color=TEXT_PRIMARY),
                        ft.Text("Криптовалютная биржа", size=12, color=TEXT_SECONDARY),
                    ], spacing=2, expand=True),
                    ft.Icon(
                        ft.icons.CHECK_CIRCLE if bybit_selected else ft.icons.RADIO_BUTTON_UNCHECKED,
                        size=32, color=SUCCESS_COLOR if bybit_selected else TEXT_SECONDARY
                    ),
                ], vertical_alignment="center"),
                padding=18,
                bgcolor="#2a2200" if bybit_selected else "#1a1a22",
                border_radius=16,
                border=ft.border.all(2, "#f7a600" if bybit_selected else BORDER_COLOR),
                on_click=lambda e: toggle_exchange("bybit"),
                ink=True,
                width=420,
            )
            
            gateio_card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.CURRENCY_EXCHANGE, size=28, color=DARK_BG),
                        width=55, height=55,
                        border_radius=12,
                        bgcolor="#2354e6",
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text("Gate.io", size=18, weight="bold", color=TEXT_PRIMARY),
                        ft.Text("Криптовалютная биржа", size=12, color=TEXT_SECONDARY),
                    ], spacing=2, expand=True),
                    ft.Icon(
                        ft.icons.CHECK_CIRCLE if gateio_selected else ft.icons.RADIO_BUTTON_UNCHECKED,
                        size=32, color=SUCCESS_COLOR if gateio_selected else TEXT_SECONDARY
                    ),
                ], vertical_alignment="center"),
                padding=18,
                bgcolor="#1a1a33" if gateio_selected else "#1a1a22",
                border_radius=16,
                border=ft.border.all(2, "#2354e6" if gateio_selected else BORDER_COLOR),
                on_click=lambda e: toggle_exchange("gateio"),
                ink=True,
                width=420,
            )
            
            mexc_card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.SHOW_CHART, size=28, color=DARK_BG),
                        width=55, height=55,
                        border_radius=12,
                        bgcolor="#00ff88",
                        alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Text("MEXC", size=18, weight="bold", color=TEXT_PRIMARY),
                        ft.Text("Криптовалютная биржа", size=12, color=TEXT_SECONDARY),
                    ], spacing=2, expand=True),
                    ft.Icon(
                        ft.icons.CHECK_CIRCLE if mexc_selected else ft.icons.RADIO_BUTTON_UNCHECKED,
                        size=32, color=SUCCESS_COLOR if mexc_selected else TEXT_SECONDARY
                    ),
                ], vertical_alignment="center"),
                padding=18,
                bgcolor="#003322" if mexc_selected else "#1a1a22",
                border_radius=16,
                border=ft.border.all(2, "#00ff88" if mexc_selected else BORDER_COLOR),
                on_click=lambda e: toggle_exchange("mexc"),
                ink=True,
                width=420,
            )
            
            step_content.content = ft.Column([
                ft.Container(
                    content=ft.Icon(ft.icons.LINK, size=40, color=DARK_BG),
                    width=70, height=70,
                    border_radius=35,
                    bgcolor=WARNING_COLOR,
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=15),
                ft.Text("Подключите биржи", size=22, weight="bold", color=TEXT_PRIMARY),
                ft.Text("Выберите биржи для отслеживания портфеля", size=13, color=TEXT_SECONDARY),
                ft.Container(height=25),
                bybit_card,
                gateio_card,
                mexc_card,
                ft.Container(height=8),
                error_text,
            ], horizontal_alignment="center", spacing=12)
        
        elif current_step["value"] == 4:
            # Шаг 4: API ключи
            key_sections = []
            for ex_name in selected_exchanges["list"]:
                color = EXCHANGE_COLORS.get(ex_name, PRIMARY_COLOR)
                name = EXCHANGE_NAMES.get(ex_name, ex_name.upper())
                
                if ex_name not in exchange_keys_data["data"]:
                    exchange_keys_data["data"][ex_name] = {"api": "", "secret": "", "passphrase": ""}
                
                fields = [
                    ft.TextField(
                        label="API Key",
                        width=400,
                        height=50,
                        bgcolor=CARD_BG,
                        border_color=color,
                        focused_border_color=color,
                        border_radius=10,
                        value=exchange_keys_data["data"][ex_name]["api"],
                        on_change=lambda e, n=ex_name: exchange_keys_data["data"].__setitem__(n, {**exchange_keys_data["data"][n], "api": e.control.value}),
                    ),
                    ft.TextField(
                        label="Secret Key",
                        width=400,
                        height=50,
                        password=True,
                        can_reveal_password=True,
                        bgcolor=CARD_BG,
                        border_color=color,
                        focused_border_color=color,
                        border_radius=10,
                        value=exchange_keys_data["data"][ex_name]["secret"],
                        on_change=lambda e, n=ex_name: exchange_keys_data["data"].__setitem__(n, {**exchange_keys_data["data"][n], "secret": e.control.value}),
                    ),
                ]
                
                key_sections.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Container(
                                    content=ft.Icon(ft.icons.ACCOUNT_BALANCE, size=20, color=DARK_BG),
                                    width=36, height=36,
                                    border_radius=8,
                                    bgcolor=color,
                                    alignment=ft.alignment.center,
                                ),
                                ft.Text(name, size=16, weight="bold", color=color),
                            ], spacing=12),
                            ft.Container(height=10),
                            *fields,
                        ], spacing=10),
                        padding=20,
                        bgcolor=ft.colors.with_opacity(0.05, color),
                        border_radius=12,
                        border=ft.border.all(1, ft.colors.with_opacity(0.3, color)),
                    )
                )
            
            step_content.content = ft.Column([
                ft.Container(
                    content=ft.Icon(ft.icons.KEY, size=40, color=DARK_BG),
                    width=70, height=70,
                    border_radius=35,
                    bgcolor=SUCCESS_COLOR,
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=15),
                ft.Text("API ключи", size=22, weight="bold", color=TEXT_PRIMARY),
                ft.Text("Введите ключи для выбранных бирж", size=13, color=TEXT_SECONDARY),
                ft.Container(height=20),
                *key_sections,
                ft.Container(height=8),
                error_text,
            ], horizontal_alignment="center", scroll="adaptive", spacing=15)
        
        update_progress()
        update_buttons()
        page.update()
    
    def update_buttons():
        """Обновляет кнопки навигации"""
        back_btn = ft.TextButton(
            "← Назад",
            style=ft.ButtonStyle(color=TEXT_SECONDARY),
            on_click=prev_step,
            visible=current_step["value"] > 1,
        )
        
        if current_step["value"] < 4:
            next_btn = ft.ElevatedButton(
                text="Далее →",
                width=150,
                height=50,
                style=ft.ButtonStyle(
                    bgcolor=PRIMARY_COLOR,
                    color=DARK_BG,
                    text_style=ft.TextStyle(size=15, weight="bold"),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
                on_click=next_step,
            )
        else:
            next_btn = ft.ElevatedButton(
                text="Создать аккаунт",
                width=200,
                height=50,
                icon=ft.icons.CHECK,
                style=ft.ButtonStyle(
                    bgcolor=SUCCESS_COLOR,
                    color=DARK_BG,
                    text_style=ft.TextStyle(size=15, weight="bold"),
                    shape=ft.RoundedRectangleBorder(radius=12),
                ),
                on_click=next_step,
            )
        
        buttons_container.content = ft.Row([
            back_btn,
            ft.Container(expand=True),
            next_btn,
        ], width=420)
    
    def next_step(e):
        if current_step["value"] == 1:
            # Валидация шага 1
            if not username_field.value.strip():
                error_text.value = "Введите имя пользователя"
                error_text.visible = True
                page.update()
                return
            
            if not password_field.value or len(password_field.value) < 4:
                error_text.value = "Пароль должен быть минимум 4 символа"
                error_text.visible = True
                page.update()
                return
            
            if not email_field.value.strip() or "@" not in email_field.value:
                error_text.value = "Введите корректный email"
                error_text.visible = True
                page.update()
                return
            
            if not full_name_field.value.strip():
                error_text.value = "Введите полное имя"
                error_text.visible = True
                page.update()
                return
            
            # Проверяем уникальность имени
            existing = session.query(User).filter_by(name=username_field.value.strip()).first()
            if existing:
                error_text.value = "Пользователь с таким именем уже существует"
                error_text.visible = True
                page.update()
                return
            
            # Проверяем уникальность email
            existing_email = session.query(User).filter_by(email=email_field.value.strip()).first()
            if existing_email:
                error_text.value = "Этот email уже используется"
                error_text.visible = True
                page.update()
                return
            
            error_text.visible = False
            current_step["value"] = 2
            update_step_content()
        
        elif current_step["value"] == 2:
            # Аватар выбран - переходим дальше
            error_text.visible = False
            current_step["value"] = 3
            update_step_content()
        
        elif current_step["value"] == 3:
            if not selected_exchanges["list"]:
                error_text.value = "Выберите хотя бы одну биржу"
                error_text.visible = True
                page.update()
                return
            
            error_text.visible = False
            current_step["value"] = 4
            update_step_content()
        
        elif current_step["value"] == 4:
            # Финальная регистрация
            for ex_name in selected_exchanges["list"]:
                data = exchange_keys_data["data"].get(ex_name, {})
                if not data.get("api") or not data.get("secret"):
                    error_text.value = f"Заполните ключи для {EXCHANGE_NAMES[ex_name]}"
                    error_text.visible = True
                    page.update()
                    return
            
            # Тестируем подключения
            error_text.value = "Проверка подключения к биржам..."
            error_text.color = WARNING_COLOR
            error_text.visible = True
            page.update()
            
            for ex_name in selected_exchanges["list"]:
                data = exchange_keys_data["data"][ex_name]
                success, msg = test_exchange_connection(
                    ex_name, data["api"], data["secret"], data.get("passphrase")
                )
                if not success:
                    error_text.value = f"{EXCHANGE_NAMES[ex_name]}: {msg}"
                    error_text.color = ACCENT_COLOR
                    error_text.visible = True
                    page.update()
                    return
            
            # Создаем пользователя
            try:
                new_user = User(
                    name=username_field.value.strip(),
                    password=password_field.value,
                    email=email_field.value.strip(),
                    full_name=full_name_field.value.strip(),
                    phone=phone_field.value.strip() or None,
                    country=country_dropdown.value,
                    avatar_icon=selected_avatar["icon"],
                    avatar_color=selected_avatar["color"],
                )
                session.add(new_user)
                session.commit()
                
                # Добавляем ключи
                for ex_name in selected_exchanges["list"]:
                    data = exchange_keys_data["data"][ex_name]
                    key = ExchangeAPIKey(
                        user_id=new_user.id,
                        exchange_name=ex_name,
                        api_key=data["api"],
                        secret_key=data["secret"],
                        passphrase=data.get("passphrase"),
                    )
                    session.add(key)
                
                session.commit()
                
                current_user["user"] = new_user
                show_main_screen_callback()
                
            except Exception as ex:
                error_text.value = f"Ошибка регистрации: {ex}"
                error_text.color = ACCENT_COLOR
                error_text.visible = True
                page.update()
    
    def prev_step(e):
        if current_step["value"] > 1:
            current_step["value"] -= 1
            error_text.visible = False
            update_step_content()
    
    # Инициализация
    update_step_content()
    
    register_container = ft.Container(
        content=ft.Column([
            progress_container,
            ft.Container(height=25),
            step_content,
            ft.Container(height=20),
            buttons_container,
            ft.Container(height=15),
            ft.TextButton(
                text="Уже есть аккаунт? Войти",
                style=ft.ButtonStyle(color=TEXT_SECONDARY),
                on_click=lambda e: show_login_callback(),
            ),
        ], horizontal_alignment="center", scroll="adaptive"),
        padding=40,
        bgcolor=CARD_BG,
        border_radius=20,
        width=520,
        height=720,
        border=ft.border.all(1, BORDER_COLOR),
        shadow=ft.BoxShadow(blur_radius=40, spread_radius=5, color="#00000060"),
    )
    
    page.add(ft.Container(content=register_container, expand=True, alignment=ft.alignment.center))
    page.update()
