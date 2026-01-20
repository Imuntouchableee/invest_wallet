"""
Диалоговые окна приложения (кроме торговли)
"""
import flet as ft
import logging

from ui.config import (
    DARK_BG, CARD_BG, PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    EXCHANGE_COLORS, EXCHANGE_NAMES, AVATAR_COLORS,
)
from backend.models import User, ExchangeAPIKey, session
from backend.api import test_exchange_connection

logger = logging.getLogger(__name__)


def show_logout_confirm_dialog(page: ft.Page, logout_callback):
    """Диалог подтверждения выхода"""
    def close_dialog():
        dialog.open = False
        page.update()
    
    def confirm_logout(e):
        close_dialog()
        logout_callback()
    
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.icons.LOGOUT, color=ACCENT_COLOR, size=28),
            ft.Text("Выход из аккаунта", size=20, weight="bold", color=TEXT_PRIMARY),
        ], spacing=10),
        content=ft.Container(
            content=ft.Column([
                ft.Text("Вы уверены, что хотите выйти?", size=16, color=TEXT_PRIMARY),
                ft.Container(height=10),
                ft.Text("Для повторного входа потребуется ввести логин и пароль.", size=13, color=TEXT_SECONDARY),
            ]),
            width=350,
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda e: close_dialog(), style=ft.ButtonStyle(color=TEXT_SECONDARY)),
            ft.ElevatedButton(
                "Выйти",
                style=ft.ButtonStyle(bgcolor=ACCENT_COLOR, color=TEXT_PRIMARY),
                on_click=confirm_logout,
            ),
        ],
        actions_alignment="end",
        bgcolor=CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def show_add_exchange_dialog(page: ft.Page, current_user: dict, 
                             show_main_screen_callback, preselected_exchange: str = None):
    """Диалог добавления новой биржи"""
    def close_dialog():
        dialog.open = False
        page.update()
    
    selected_exchange = {"value": preselected_exchange or "bybit"}
    
    # Поля ввода
    api_key_field = ft.TextField(
        label="API Key",
        width=400,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
    )
    
    secret_key_field = ft.TextField(
        label="Secret Key",
        width=400,
        password=True,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
    )
    
    status_text = ft.Text("", size=13, visible=False)
    
    def on_exchange_change(e):
        selected_exchange["value"] = e.control.value
        page.update()
    
    def test_connection(e):
        api_key = api_key_field.value.strip()
        secret_key = secret_key_field.value.strip()
        
        if not api_key or not secret_key:
            status_text.value = "Заполните все обязательные поля"
            status_text.color = ACCENT_COLOR
            status_text.visible = True
            page.update()
            return
        
        status_text.value = "Проверка подключения..."
        status_text.color = WARNING_COLOR
        status_text.visible = True
        page.update()
        
        success, message = test_exchange_connection(
            selected_exchange["value"], api_key, secret_key, None
        )
        
        status_text.value = message
        status_text.color = SUCCESS_COLOR if success else ACCENT_COLOR
        page.update()
    
    def save_exchange(e):
        user = current_user["user"]
        api_key = api_key_field.value.strip()
        secret_key = secret_key_field.value.strip()
        
        if not api_key or not secret_key:
            status_text.value = "Заполните все обязательные поля"
            status_text.color = ACCENT_COLOR
            status_text.visible = True
            page.update()
            return
        
        # Проверяем подключение
        success, message = test_exchange_connection(
            selected_exchange["value"], api_key, secret_key, None
        )
        
        if not success:
            status_text.value = f"Не удалось подключиться: {message}"
            status_text.color = ACCENT_COLOR
            status_text.visible = True
            page.update()
            return
        
        # Проверяем, нет ли уже такой биржи
        existing = session.query(ExchangeAPIKey).filter_by(
            user_id=user.id, 
            exchange_name=selected_exchange["value"]
        ).first()
        
        if existing:
            existing.api_key = api_key
            existing.secret_key = secret_key
            existing.is_active = True
        else:
            new_key = ExchangeAPIKey(
                user_id=user.id,
                exchange_name=selected_exchange["value"],
                api_key=api_key,
                secret_key=secret_key,
            )
            session.add(new_key)
        
        session.commit()
        close_dialog()
        show_main_screen_callback()
    
    exchange_dropdown = ft.Dropdown(
        label="Выберите биржу",
        width=400,
        value=selected_exchange["value"],
        options=[
            ft.dropdown.Option("bybit", "Bybit"),
            ft.dropdown.Option("gateio", "Gate.io"),
            ft.dropdown.Option("mexc", "MEXC"),
        ],
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        on_change=on_exchange_change,
    )
    
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.icons.ADD_LINK, color=PRIMARY_COLOR),
            ft.Text("Подключить биржу", size=20, weight="bold", color=TEXT_PRIMARY),
        ], spacing=10),
        content=ft.Container(
            content=ft.Column([
                exchange_dropdown,
                ft.Container(height=15),
                api_key_field,
                ft.Container(height=10),
                secret_key_field,
                ft.Container(height=10),
                status_text,
            ], spacing=0),
            width=450,
        ),
        actions=[
            ft.TextButton("Проверить", on_click=test_connection, style=ft.ButtonStyle(color=WARNING_COLOR)),
            ft.ElevatedButton(
                "Сохранить",
                style=ft.ButtonStyle(bgcolor=SUCCESS_COLOR, color=DARK_BG),
                on_click=save_exchange,
            ),
            ft.TextButton("Отмена", on_click=lambda e: close_dialog(), style=ft.ButtonStyle(color=TEXT_SECONDARY)),
        ],
        bgcolor=CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def show_exchange_settings_dialog(page: ft.Page, current_user: dict, 
                                  show_main_screen_callback, show_add_exchange_callback):
    """Диалог настроек подключенных бирж"""
    user = current_user["user"]
    user_keys = session.query(ExchangeAPIKey).filter_by(user_id=user.id).all()
    
    def close_dialog():
        dialog.open = False
        page.update()
    
    def toggle_exchange(key_id, is_active):
        key = session.get(ExchangeAPIKey, key_id)
        if key:
            key.is_active = is_active
            session.commit()
            close_dialog()
            show_exchange_settings_dialog(page, current_user, show_main_screen_callback, show_add_exchange_callback)
    
    def delete_exchange(key_id):
        key = session.get(ExchangeAPIKey, key_id)
        if key:
            session.delete(key)
            session.commit()
            close_dialog()
            show_exchange_settings_dialog(page, current_user, show_main_screen_callback, show_add_exchange_callback)
    
    exchange_rows = []
    for key in user_keys:
        color = EXCHANGE_COLORS.get(key.exchange_name, PRIMARY_COLOR)
        name = EXCHANGE_NAMES.get(key.exchange_name, key.exchange_name.upper())
        
        exchange_rows.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.ACCOUNT_BALANCE, color=color, size=24),
                    ft.Column([
                        ft.Text(name, size=16, weight="bold", color=TEXT_PRIMARY),
                        ft.Text(
                            f"API: {key.api_key[:8]}...{key.api_key[-4:]}", 
                            size=11, color=TEXT_SECONDARY
                        ),
                    ], spacing=2, expand=True),
                    ft.Switch(
                        value=key.is_active,
                        active_color=SUCCESS_COLOR,
                        on_change=lambda e, kid=key.id: toggle_exchange(kid, e.control.value),
                    ),
                    ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_color=ACCENT_COLOR,
                        tooltip="Удалить",
                        on_click=lambda e, kid=key.id: delete_exchange(kid),
                    ),
                ], vertical_alignment="center"),
                padding=15,
                bgcolor=ft.colors.with_opacity(0.1, color),
                border_radius=10,
                border=ft.border.all(1, color),
            )
        )
    
    if not exchange_rows:
        exchange_rows.append(
            ft.Text("Нет подключенных бирж", size=14, color=TEXT_SECONDARY, italic=True)
        )
    
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.icons.SETTINGS, color=PRIMARY_COLOR),
            ft.Text("Настройки бирж", size=20, weight="bold", color=TEXT_PRIMARY),
        ], spacing=10),
        content=ft.Container(
            content=ft.Column([
                *exchange_rows,
                ft.Container(height=15),
                ft.ElevatedButton(
                    "Добавить биржу",
                    icon=ft.icons.ADD,
                    style=ft.ButtonStyle(bgcolor=PRIMARY_COLOR, color=DARK_BG),
                    on_click=lambda e: (close_dialog(), show_add_exchange_callback()),
                ),
            ], spacing=10),
            width=450,
        ),
        actions=[
            ft.TextButton("Закрыть", on_click=lambda e: close_dialog()),
        ],
        bgcolor=CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    
    page.overlay.append(dialog)
    dialog.open = True
    page.update()


def show_edit_profile_dialog(page: ft.Page, current_user: dict, show_profile_callback):
    """Диалог редактирования профиля"""
    user = current_user["user"]
    
    def close_dialog():
        dialog.open = False
        page.update()
    
    # Поля
    full_name_field = ft.TextField(
        label="Полное имя",
        value=user.full_name or "",
        width=400,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.BADGE,
    )
    
    email_field = ft.TextField(
        label="Email",
        value=user.email or "",
        width=400,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.EMAIL,
    )
    
    phone_field = ft.TextField(
        label="Телефон",
        value=user.phone or "",
        width=400,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.PHONE,
    )
    
    country_field = ft.TextField(
        label="Страна",
        value=user.country or "",
        width=400,
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        prefix_icon=ft.icons.LOCATION_ON,
    )
    
    # Выбор цвета аватара
    selected_color = {"value": user.avatar_color or "#00d4ff"}
    
    def select_color(color):
        selected_color["value"] = color
        update_color_preview()
    
    def update_color_preview():
        color_row.controls = [
            ft.Container(
                width=35, height=35,
                border_radius=20,
                bgcolor=c,
                border=ft.border.all(3, TEXT_PRIMARY if selected_color["value"] == c else "transparent"),
                on_click=lambda e, col=c: select_color(col),
                ink=True,
            ) for c in AVATAR_COLORS
        ]
        page.update()
    
    color_row = ft.Row([
        ft.Container(
            width=35, height=35,
            border_radius=20,
            bgcolor=c,
            border=ft.border.all(3, TEXT_PRIMARY if selected_color["value"] == c else "transparent"),
            on_click=lambda e, col=c: select_color(col),
            ink=True,
        ) for c in AVATAR_COLORS
    ], spacing=8)
    
    def save_profile(e):
        user.full_name = full_name_field.value.strip() or None
        user.email = email_field.value.strip() or None
        user.phone = phone_field.value.strip() or None
        user.country = country_field.value.strip() or None
        user.avatar_color = selected_color["value"]
        session.commit()
        close_dialog()
        show_profile_callback()
    
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.icons.EDIT, color=PRIMARY_COLOR, size=28),
            ft.Text("Редактировать профиль", size=20, weight="bold", color=TEXT_PRIMARY),
        ], spacing=10),
        content=ft.Container(
            content=ft.Column([
                full_name_field,
                ft.Container(height=10),
                email_field,
                ft.Container(height=10),
                phone_field,
                ft.Container(height=10),
                country_field,
                ft.Container(height=15),
                ft.Text("Цвет аватара", size=14, color=TEXT_SECONDARY),
                ft.Container(height=5),
                color_row,
            ], scroll="adaptive"),
            width=450,
            height=380,
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda e: close_dialog(), style=ft.ButtonStyle(color=TEXT_SECONDARY)),
            ft.ElevatedButton(
                "Сохранить",
                style=ft.ButtonStyle(bgcolor=SUCCESS_COLOR, color=DARK_BG),
                on_click=save_profile,
            ),
        ],
        actions_alignment="end",
        bgcolor=CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    
    page.overlay.append(dialog)
    dialog.open = True
    page.update()
