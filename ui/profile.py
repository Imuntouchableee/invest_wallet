"""
Страница профиля пользователя
"""
import flet as ft
from datetime import datetime

from ui.config import (
    DARK_BG, CARD_BG, PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR, SUCCESS_COLOR, WARNING_COLOR,
    EXCHANGE_COLORS, EXCHANGE_NAMES,
)
from ui.components import get_user_level
from backend.models import User, session


def show_profile_page(page: ft.Page, current_user: dict, portfolio_cache: dict,
                      show_main_screen_callback, show_exchange_settings_callback,
                      show_logout_confirm_callback, show_edit_profile_callback):
    """Полноэкранная страница профиля"""
    user = current_user["user"]
    portfolio = portfolio_cache.get("data")
    
    # Обновляем данные пользователя из БД
    user = session.query(User).filter_by(id=user.id).first()
    current_user["user"] = user
    
    # Статистика
    total_usd = portfolio['total_usd'] if portfolio else 0
    exchanges_count = len(portfolio['exchanges']) if portfolio else 0
    assets_count = len(portfolio['all_assets']) if portfolio else 0
    
    level_name, level_color, level_icon = get_user_level(total_usd)
    
    # Дата регистрации
    reg_date = user.registration_date.strftime("%d.%m.%Y") if user.registration_date else "Неизвестно"
    last_login = user.last_login.strftime("%d.%m.%Y %H:%M") if user.last_login else "Неизвестно"
    days_active = (datetime.now() - user.registration_date).days if user.registration_date else 0
    
    page.controls.clear()
    
    # ============ HEADER ПРОФИЛЯ ============
    profile_header = ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.icons.ARROW_BACK,
                icon_color=TEXT_PRIMARY,
                tooltip="Назад",
                on_click=lambda e: show_main_screen_callback(),
            ),
            ft.Text("Профиль", size=24, weight="bold", color=TEXT_PRIMARY),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.icons.EDIT,
                icon_color=PRIMARY_COLOR,
                tooltip="Редактировать профиль",
                on_click=lambda e: show_edit_profile_callback(),
            ),
        ], vertical_alignment="center"),
        padding=20,
        bgcolor=CARD_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR)),
    )
    
    # ============ АВАТАР И ОСНОВНАЯ ИНФО ============
    avatar_section = ft.Container(
        content=ft.Column([
            # Большой аватар
            ft.CircleAvatar(
                content=ft.Text(user.name[0].upper(), size=48, weight="bold", color=DARK_BG),
                radius=70,
                bgcolor=user.avatar_color or PRIMARY_COLOR,
            ),
            ft.Container(height=15),
            # Имя и уровень
            ft.Row([
                ft.Text(user.name, size=28, weight="bold", color=TEXT_PRIMARY),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(level_icon, size=16, color=DARK_BG),
                        ft.Text(level_name, size=12, weight="bold", color=DARK_BG),
                    ], spacing=5),
                    bgcolor=level_color,
                    padding=ft.padding.symmetric(horizontal=12, vertical=5),
                    border_radius=15,
                ),
            ], alignment="center", spacing=15),
            # Полное имя
            ft.Text(user.full_name or "Полное имя не указано", size=16, color=TEXT_SECONDARY),
            ft.Container(height=5),
            # Email
            ft.Row([
                ft.Icon(ft.icons.EMAIL, size=16, color=TEXT_SECONDARY),
                ft.Text(user.email or "Email не указан", size=14, color=TEXT_SECONDARY),
            ], alignment="center", spacing=8),
        ], horizontal_alignment="center"),
        padding=30,
        bgcolor=ft.colors.with_opacity(0.05, PRIMARY_COLOR),
    )
    
    # ============ КАРТОЧКА ПОРТФЕЛЯ ============
    portfolio_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, size=28, color=SUCCESS_COLOR),
                ft.Text("Общий портфель", size=18, weight="bold", color=TEXT_PRIMARY),
            ], spacing=10),
            ft.Container(height=15),
            ft.Text(f"${total_usd:,.2f}", size=42, weight="bold", color=SUCCESS_COLOR),
            ft.Container(height=20),
            # Метрики
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{exchanges_count}", size=24, weight="bold", color=PRIMARY_COLOR),
                        ft.Text("Бирж", size=12, color=TEXT_SECONDARY),
                    ], horizontal_alignment="center"),
                    expand=True,
                ),
                ft.Container(width=1, height=50, bgcolor=BORDER_COLOR),
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{assets_count}", size=24, weight="bold", color=SECONDARY_COLOR),
                        ft.Text("Активов", size=12, color=TEXT_SECONDARY),
                    ], horizontal_alignment="center"),
                    expand=True,
                ),
                ft.Container(width=1, height=50, bgcolor=BORDER_COLOR),
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"{days_active}", size=24, weight="bold", color=WARNING_COLOR),
                        ft.Text("Дней", size=12, color=TEXT_SECONDARY),
                    ], horizontal_alignment="center"),
                    expand=True,
                ),
            ]),
        ], horizontal_alignment="center"),
        padding=25,
        bgcolor=CARD_BG,
        border_radius=16,
        border=ft.border.all(1, BORDER_COLOR),
        margin=ft.margin.symmetric(horizontal=20, vertical=10),
    )
    
    # ============ РАСПРЕДЕЛЕНИЕ ПО БИРЖАМ ============
    exchange_cards = []
    if portfolio:
        for ex_name, ex_data in portfolio['exchanges'].items():
            if ex_data['status'] == 'success':
                color = EXCHANGE_COLORS.get(ex_name, PRIMARY_COLOR)
                percentage = (ex_data['total_usd'] / total_usd * 100) if total_usd > 0 else 0
                exchange_cards.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Icon(ft.icons.ACCOUNT_BALANCE, size=24, color=DARK_BG),
                                width=50, height=50,
                                bgcolor=color,
                                border_radius=12,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column([
                                ft.Text(EXCHANGE_NAMES.get(ex_name, ex_name), size=16, weight="bold", color=TEXT_PRIMARY),
                                ft.Text(f"{ex_data['asset_count']} активов", size=12, color=TEXT_SECONDARY),
                            ], spacing=2, expand=True),
                            ft.Column([
                                ft.Text(f"${ex_data['total_usd']:,.2f}", size=18, weight="bold", color=SUCCESS_COLOR),
                                ft.Container(
                                    content=ft.Text(f"{percentage:.1f}%", size=11, color=DARK_BG, weight="bold"),
                                    bgcolor=color,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                    border_radius=8,
                                ),
                            ], horizontal_alignment="end", spacing=5),
                        ], vertical_alignment="center"),
                        padding=15,
                        bgcolor=ft.colors.with_opacity(0.08, color),
                        border_radius=12,
                        border=ft.border.all(1, color),
                    )
                )
    
    exchanges_section = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.PIE_CHART, size=24, color=PRIMARY_COLOR),
                ft.Text("Распределение по биржам", size=18, weight="bold", color=TEXT_PRIMARY),
            ], spacing=10),
            ft.Container(height=15),
            ft.Column(exchange_cards, spacing=10) if exchange_cards else ft.Text("Нет данных", color=TEXT_SECONDARY),
        ]),
        padding=20,
        bgcolor=CARD_BG,
        border_radius=16,
        border=ft.border.all(1, BORDER_COLOR),
        margin=ft.margin.symmetric(horizontal=20, vertical=5),
    )
    
    # ============ ИНФОРМАЦИЯ ОБ АККАУНТЕ ============
    account_info = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.INFO_OUTLINE, size=24, color=PRIMARY_COLOR),
                ft.Text("Информация об аккаунте", size=18, weight="bold", color=TEXT_PRIMARY),
            ], spacing=10),
            ft.Container(height=15),
            # Строки информации
            ft.Row([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=18, color=TEXT_SECONDARY),
                ft.Text("Дата регистрации:", size=14, color=TEXT_SECONDARY, expand=True),
                ft.Text(reg_date, size=14, weight="bold", color=TEXT_PRIMARY),
            ], vertical_alignment="center"),
            ft.Divider(height=1, color=BORDER_COLOR),
            ft.Row([
                ft.Icon(ft.icons.ACCESS_TIME, size=18, color=TEXT_SECONDARY),
                ft.Text("Последний вход:", size=14, color=TEXT_SECONDARY, expand=True),
                ft.Text(last_login, size=14, weight="bold", color=TEXT_PRIMARY),
            ], vertical_alignment="center"),
            ft.Divider(height=1, color=BORDER_COLOR),
            ft.Row([
                ft.Icon(ft.icons.PHONE, size=18, color=TEXT_SECONDARY),
                ft.Text("Телефон:", size=14, color=TEXT_SECONDARY, expand=True),
                ft.Text(user.phone or "Не указан", size=14, weight="bold", color=TEXT_PRIMARY),
            ], vertical_alignment="center"),
            ft.Divider(height=1, color=BORDER_COLOR),
            ft.Row([
                ft.Icon(ft.icons.LOCATION_ON, size=18, color=TEXT_SECONDARY),
                ft.Text("Страна:", size=14, color=TEXT_SECONDARY, expand=True),
                ft.Text(user.country or "Не указана", size=14, weight="bold", color=TEXT_PRIMARY),
            ], vertical_alignment="center"),
        ], spacing=10),
        padding=20,
        bgcolor=CARD_BG,
        border_radius=16,
        border=ft.border.all(1, BORDER_COLOR),
        margin=ft.margin.symmetric(horizontal=20, vertical=5),
    )
    
    # ============ КНОПКИ ДЕЙСТВИЙ ============
    action_buttons = ft.Container(
        content=ft.Row([
            ft.ElevatedButton(
                text="Настройки бирж",
                icon=ft.icons.SETTINGS,
                style=ft.ButtonStyle(
                    bgcolor=ft.colors.with_opacity(0.1, PRIMARY_COLOR),
                    color=PRIMARY_COLOR,
                    padding=ft.padding.symmetric(horizontal=25, vertical=15),
                ),
                on_click=lambda e: (show_main_screen_callback(), show_exchange_settings_callback()),
            ),
            ft.ElevatedButton(
                text="Выйти из аккаунта",
                icon=ft.icons.LOGOUT,
                style=ft.ButtonStyle(
                    bgcolor=ft.colors.with_opacity(0.1, ACCENT_COLOR),
                    color=ACCENT_COLOR,
                    padding=ft.padding.symmetric(horizontal=25, vertical=15),
                ),
                on_click=lambda e: show_logout_confirm_callback(),
            ),
        ], alignment="center", spacing=20),
        padding=20,
        margin=ft.margin.only(bottom=20),
    )
    
    # Собираем страницу
    page.add(
        ft.Column([
            profile_header,
            ft.Container(
                content=ft.Column([
                    avatar_section,
                    portfolio_card,
                    exchanges_section,
                    account_info,
                    action_buttons,
                ], scroll="adaptive", spacing=0),
                expand=True,
            ),
        ], expand=True, spacing=0)
    )
    page.update()
