"""
Переиспользуемые UI компоненты
"""
import flet as ft
from ui.config import (
    DARK_BG, CARD_BG, PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR,
    TEXT_PRIMARY, TEXT_SECONDARY, BORDER_COLOR, SUCCESS_COLOR, WARNING_COLOR,
)


def show_snack_bar(page: ft.Page, message: str, color=PRIMARY_COLOR, icon=ft.icons.INFO):
    """Показывает snackbar уведомление"""
    snack = ft.SnackBar(
        content=ft.Row([
            ft.Icon(icon, color=color, size=20),
            ft.Text(message, color=TEXT_PRIMARY),
        ], spacing=10),
        bgcolor=CARD_BG,
    )
    page.overlay.append(snack)
    snack.open = True
    page.update()


def get_user_level(total_usd: float):
    """Определяет уровень пользователя по объему портфеля"""
    if total_usd >= 1000000:
        return "DIAMOND", "#b9f2ff", ft.icons.DIAMOND
    elif total_usd >= 100000:
        return "PRO", "#ffd700", ft.icons.WORKSPACE_PREMIUM
    else:
        return "ОБЫЧНЫЙ", PRIMARY_COLOR, ft.icons.PERSON


def create_exchange_card(exchange_name: str, data: dict, color: str, on_asset_click=None):
    """Создает карточку биржи с активами"""
    from ui.config import EXCHANGE_NAMES
    name = EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())

    if data['status'] == 'loading':
        return ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=color, width=48, height=48),
                ft.Container(height=10),
                ft.Text(f"Синхронизация данных {name}", size=18, color=color),
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
    
    # Список активов
    asset_list = ft.Column(spacing=8, scroll="adaptive", expand=True)
    
    if data['assets']:
        for asset in data['assets']:
            asset_row = ft.Container(
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
                ], vertical_alignment="center", spacing=12),
                padding=15,
                bgcolor=CARD_BG,
                border_radius=12,
                border=ft.border.all(1, BORDER_COLOR),
            )
            asset_list.controls.append(asset_row)
    else:
        asset_list.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Icon(ft.icons.SAVINGS, size=48, color=TEXT_SECONDARY),
                    ft.Text("Нет активов", size=16, color=TEXT_SECONDARY),
                ], alignment="center", horizontal_alignment="center"),
                padding=40,
                alignment=ft.alignment.center,
            )
        )
    
    return ft.Container(
        content=ft.Column([
            # Заголовок биржи
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.ACCOUNT_BALANCE, size=24, color=color),
                    ft.Text(name, size=20, weight="bold", color=color),
                    ft.Container(expand=True),
                    ft.Column([
                        ft.Text("Баланс", size=11, color=TEXT_SECONDARY),
                        ft.Text(f"${data['total_usd']:,.2f}", size=18, weight="bold", color=SUCCESS_COLOR),
                    ], horizontal_alignment="end", spacing=2),
                ], vertical_alignment="center"),
                padding=15,
                bgcolor=ft.colors.with_opacity(0.1, color),
                border_radius=12,
                margin=ft.margin.only(bottom=15),
            ),
            # Количество активов
            ft.Text(f"Активов: {data['asset_count']}", size=14, color=TEXT_SECONDARY),
            ft.Container(height=10),
            # Список активов
            asset_list,
        ], expand=True),
        padding=15,
        expand=True,
    )
