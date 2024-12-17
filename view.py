import sqlite3
import flet as ft
from models import User, Asset
from models import session
from api import mainn

data = {}

top_25_expensive_coins = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'TON/USDT', 'MKR/USDT',
    'LTC/USDT', 'BCH/USDT', 'DOT/USDT', 'LINK/USDT', 'AAVE/USDT',
    'ATOM/USDT', 'FIL/USDT', 'NEAR/USDT', 'SOL/USDT', 'AVAX/USDT',
    'ALGO/USDT', 'FTM/USDT', 'MANA/USDT', 'SAND/USDT',
    'XTZ/USDT', 'ICP/USDT', 'GRT/USDT', 'EGLD/USDT'
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

    # Поля для входа
    login_username_field = ft.TextField(label="Имя пользователя", width=300)
    login_password_field = ft.TextField(label="Пароль", width=300, password=True)
    login_button = ft.ElevatedButton(text="Войти", on_click=lambda e: login_user())
    go_to_register_button = ft.TextButton(text="Зарегистрироваться", on_click=lambda e: show_register_screen())

    # Поля для регистрации
    register_username_field = ft.TextField(label="Имя пользователя", width=300)
    register_password_field = ft.TextField(label="Пароль", width=300, password=True)
    register_button = ft.ElevatedButton(text="Зарегистрироваться", on_click=lambda e: register_user())
    back_to_login_button = ft.TextButton(text="Назад к входу", on_click=lambda e: show_login_screen())

    # Профиль
    def show_profile(page: ft.Page, name):
        user = session.query(User).filter(User.name == name).first()
        assets = session.query(Asset).filter(Asset.user_id == user.id).all()
        if user.balance is None:
            user.balance = 0

        def delete_asset(asset_id):
            asset_to_delete = session.query(Asset).filter(Asset.id == asset_id).first()
            if asset_to_delete:
                session.delete(asset_to_delete)
                session.commit()
                show_profile(page, name)  # Перезагрузить профиль после удаления

        def add_asset():
            # Переменная для сообщения об ошибке
            error_message = ft.Text("", color=ft.colors.RED, visible=False)

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
                        error_message.value = "Сумма должна быть больше 0 рублей."
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
                on_change=update_quantity,
            )

            # Выпадающий список для выбора биржи
            exchange_dropdown = ft.Dropdown(
                options=[ft.dropdown.Option(exchange) for exchange in list(data.values())[0].keys()],
                hint_text="Выберите биржу",
                on_change=update_quantity,
            )

            # Поле для ввода суммы
            asset_value_field = ft.TextField(
                label="Сумма (в рублях)",
                on_change=update_quantity,
            )

            # Поле для автоматического расчета количества
            asset_quantity_field = ft.TextField(
                label="Количество",
                read_only=True,
            )

            # Кнопка подтверждения
            confirm_button = ft.ElevatedButton(
                text="Добавить актив",
                on_click=validate_and_confirm,
            )

            # Отображение интерфейса в диалоговом окне
            dialog = ft.AlertDialog(
                title=ft.Text("Добавить актив"),
                content=ft.Column(
                    [
                        asset_name_dropdown,
                        exchange_dropdown,
                        asset_value_field,
                        asset_quantity_field,
                        error_message,
                    ],
                    tight=True,
                ),
                actions=[confirm_button],
            )

            page.overlay.append(dialog)
            dialog.open = True
            page.update()

        def sell_asset(asset_id):
            asset = session.query(Asset).filter(Asset.id == asset_id).first()

            if not asset:
                snack_bar = ft.SnackBar(ft.Text("Актива не существует!"))
                page.overlay.append(snack_bar)
                snack_bar.open = True
                return

            def confirm_sell_asset(e):
                sell_quantity = float(sell_quantity_slider.value)
                if sell_quantity >= asset.quantity:
                    session.delete(asset)
                else:
                    asset.quantity -= sell_quantity
                session.commit()
                show_profile(page, name)  # Перезагрузить профиль после продажи

            def close_dialog():
                if page.dialog:
                    page.dialog.open = False
                    page.update()

            # Ползунок для выбора количества
            sell_quantity_slider = ft.Slider(
                min=0,
                max=asset.quantity,
                value=asset.quantity,
                label="{value} единиц",
                divisions=10
            )

            # Отобразить модальное окно
            dialog = ft.AlertDialog(
                title=ft.Text("Продажа актива"),
                content=ft.Column([
                    ft.Text(f"Продается: {asset.coin_name}"),
                    sell_quantity_slider,
                ]),
                actions=[
                    ft.TextButton("Продать", on_click=confirm_sell_asset),
                    ft.TextButton("Отмена", on_click=lambda e: close_dialog()),
                ],
            )
            page.dialog = dialog
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
                if page.dialog:
                    page.dialog.open = False
                    page.update()

            dialog = ft.AlertDialog(
                title=ft.Text("Выход из профиля"),
                content=ft.Text("Вы действительно хотите выйти из аккаунта?"),
                actions=[
                    ft.TextButton(
                        "Выйти",
                        on_click=confirm_logout,
                        style=ft.ButtonStyle(
                            bgcolor=ft.colors.RED_500,
                            color=ft.colors.WHITE
                        ),
                    ),
                    ft.TextButton("Отмена", on_click=lambda e: close_dialog()),
                ],
            )
            page.dialog = dialog
            dialog.open = True
            page.update()

        def top_up_balance():
            def confirm_top_up(e):
                try:
                    top_up_amount = float(balance_field.value)
                    if top_up_amount <= 0:
                        raise ValueError("Сумма должна быть положительной")
                    user.balance += top_up_amount
                    session.commit()
                    show_profile(page, name)
                except ValueError as ex:
                    snack_bar = ft.SnackBar(ft.Text(f"Ошибка: {ex}"))
                    page.overlay.append(snack_bar)
                    snack_bar.open = True

            def close_dialog():
                if page.dialog:
                    page.dialog.open = False
                    page.update()

            # Поле для ввода суммы
            balance_field = ft.TextField(
                label="Сумма пополнения",
                hint_text="Введите сумму (рубли)",
                keyboard_type="number",
            )

            # Модальное окно
            dialog = ft.AlertDialog(
                title=ft.Text("Пополнение баланса"),
                content=ft.Column(
                    [balance_field],
                    spacing=20,
                ),
                actions=[
                    ft.TextButton("Пополнить", on_click=confirm_top_up),
                    ft.TextButton("Отмена", on_click=lambda e: close_dialog()),
                ],
            )
            page.dialog = dialog
            dialog.open = True
            page.update()

        def refresh_data():
            # Обработчик обновления данных
            def start_loading():
                # Показать модальное окно загрузки
                loading_dialog = ft.AlertDialog(
                    title=ft.Text("Обновление данных"),
                    content=ft.Row(
                        [
                            ft.ProgressRing(),
                            ft.Text("Загрузка новых данных, пожалуйста, подождите...", expand=1),
                        ],
                        alignment="center",
                    ),
                )
                page.dialog = loading_dialog
                loading_dialog.open = True
                page.update()

                # Запуск обновления данных
                update_data()

            def update_data():
                try:
                    # Имитация задержки для обновления данных
                    from time import sleep
                    sleep(2)  # Имитация времени обновления данных

                    # Обновляем данные (вызываем вашу функцию)
                    nonlocal data
                    data = mainn()

                    # Обновляем цены в таблице assets
                    update_asset_prices(data)

                    # Обновляем графический интерфейс
                    refresh_asset_list()

                    # Закрыть диалог загрузки и показать уведомление
                    if page.dialog:
                        page.dialog.open = False

                    success_snackbar = ft.SnackBar(ft.Text("Данные успешно обновлены!"))
                    page.overlay.append(success_snackbar)
                    success_snackbar.open = True
                    page.update()

                except Exception as e:
                    # Если произошла ошибка, показать уведомление об ошибке
                    if page.dialog:
                        page.dialog.open = False

                    error_snackbar = ft.SnackBar(ft.Text(f"Ошибка обновления: {e}", color=ft.colors.RED))
                    page.overlay.append(error_snackbar)
                    error_snackbar.open = True
                    page.update()

            def update_asset_prices(data):
                """Обновляет цены в таблице assets на основе новых данных."""
                assets = session.query(Asset).all()
                for asset in assets:
                    coin_name = asset.coin_name
                    if coin_name in data:
                        # Берем среднюю цену по всем биржам
                        prices = data[coin_name]
                        average_price = sum(prices.values()) / len(prices)

                        # Рассчитываем стоимость актива
                        asset.value_rub = asset.quantity * average_price
                    else:
                        print(f"Монета {coin_name} не найдена в обновленных данных!")

                # Сохраняем изменения в базе данных
                session.commit()

            def refresh_asset_list():
                """Обновляет список активов на экране."""
                # Получаем актуальные данные из базы
                updated_assets = session.query(Asset).all()

                # Очищаем предыдущий список активов
                asset_list.controls.clear()
                asset_list.controls.append(
                    ft.Row(
                        [
                            ft.Text("Монета", size=18, weight="bold", expand=1, text_align="left"),
                            ft.Text("Количество", size=18, weight="bold", expand=1, text_align="left"),
                            ft.Text("Стоимость (₽)", size=18, weight="bold", expand=1, text_align="left"),
                            ft.Text("Действие", size=18, weight="bold", expand=1, text_align="center"),
                        ],
                        alignment="spaceBetween",
                        height=50,  # Высота заголовка
                    )
                )
                asset_list.controls.append(ft.Divider(thickness=1, opacity=0.2))
                # Добавляем обновленные данные
                for asset in updated_assets:
                    asset_row = ft.Row(
                        [
                            ft.Text(asset.coin_name, size=16, expand=1, text_align="start"),  # Первая колонка
                            ft.Text(str(asset.quantity), size=16, expand=1, text_align="start"),  # Вторая колонка
                            ft.Text(f"{asset.value_rub} ₽", size=16, expand=1, text_align="start"),  # Третья колонка
                            ft.Row(
                                [
                                    ft.ElevatedButton(
                                        text="Продать",
                                        on_click=lambda e, a_id=asset.id: sell_asset(a_id),
                                        bgcolor=ft.colors.ORANGE_500,
                                        color=ft.colors.BLACK,
                                    ),
                                    ft.ElevatedButton(
                                        text="Удалить",
                                        on_click=lambda e, a_id=asset.id: delete_asset(a_id),
                                        bgcolor=ft.colors.RED_500,
                                        color=ft.colors.BLACK,
                                    ),
                                ],
                                alignment="center",
                                expand=1,
                            ),
                        ],
                        alignment="spaceBetween",
                        height=50,  # Высота строки
                    )
                    # Добавляем строку данных и разделитель
                    asset_list.controls.extend([asset_row, ft.Divider(thickness=1, opacity=0.1)])

                # Если активов нет
                if not updated_assets:
                    asset_list.controls.append(
                        ft.Text("У вас нет отслеживаемых активов.", size=16, italic=True, text_align="center")
                    )

                # Обновляем страницу
                page.update()

            # Запуск загрузки
            start_loading()

        def create_summary_page():
            """Создает страницу со сводом по монетам на разных биржах."""
            def refresh_summary():
                """Обновляет данные на странице свода."""
                try:
                    # Получаем новые данные (здесь может быть вызов вашей функции обновления)
                    nonlocal data
                    data = mainn()

                    # Очищаем старое содержимое
                    summary_table.controls.clear()

                    # Добавляем обновленные данные
                    for coin_name, prices in data.items():
                        for exchange, price in prices.items():
                            summary_table.controls.append(
                                ft.Row(
                                    [
                                        ft.Text(coin_name, expand=1, text_align="start"),
                                        ft.Text(exchange, expand=1, text_align="start"),
                                        ft.Text(f"{price} ₽", expand=1, text_align="start"),
                                    ],
                                    alignment="spaceBetween",
                                    height=50,
                                )
                            )

                    # Обновляем интерфейс
                    page.update()
                except Exception as e:
                    # Обработчик ошибок
                    error_snackbar = ft.SnackBar(ft.Text(f"Ошибка обновления: {e}", color=ft.colors.RED))
                    page.overlay.append(error_snackbar)
                    error_snackbar.open = True
                    page.update()

            # Создаем таблицу для отображения данных
            summary_table = ft.Column(
                [
                    # Заголовки столбцов
                    ft.Row(
                        [
                            ft.Text("Монета", size=18, weight="bold", expand=1, text_align="start"),
                            ft.Text("Биржа", size=18, weight="bold", expand=1, text_align="start"),
                            ft.Text("Цена (₽)", size=18, weight="bold", expand=1, text_align="start"),
                        ],
                        alignment="spaceBetween",
                        height=50,
                    ),
                    ft.Divider(thickness=1, opacity=0.2),  # Линия под заголовком
                ],
                scroll="adaptive",
                expand=True,
            )

            # Инициализация таблицы с текущими данными
            for coin_name, prices in data.items():
                for exchange, price in prices.items():
                    summary_table.controls.append(
                        ft.Row(
                            [
                                ft.Text(coin_name, expand=1, text_align="start"),
                                ft.Text(exchange, expand=1, text_align="start"),
                                ft.Text(f"{price} ₽", expand=1, text_align="start"),
                            ],
                            alignment="spaceBetween",
                            height=50,
                        )
                    )

            # Кнопка для обновления данных
            refresh_button = ft.ElevatedButton(
                text="Обновить данные",
                on_click=lambda e: refresh_summary(),
                bgcolor=ft.colors.GREEN_500,
                color=ft.colors.WHITE,
            )

            # Верстка новой страницы
            return ft.View(
                controls=[
                    ft.Text("Свод по монетам", size=24, weight="bold", text_align="center"),
                    ft.Divider(thickness=2, opacity=0.3),
                    summary_table,
                    refresh_button,
                ]
            )

        def open_summary_page(e):
            """Открывает страницу со сводом."""
            summary_page = create_summary_page()
            page.views.append(summary_page)
            page.go("/summary")


        page.controls.clear()

        # Заголовок профиля
        header = ft.Row(
            [
                # Аватарка
                ft.Container(
                    content=ft.CircleAvatar(
                        content=ft.Text(user.name[0].upper(), size=24, color=ft.colors.WHITE),
                        radius=30,
                    ),
                    on_click=lambda e: open_logout_dialog(),  # Обработчик клика
                ),
                ft.ElevatedButton(
                    text="Открыть свод",
                    on_click=open_summary_page,
                    bgcolor=ft.colors.BLUE_500,
                    color=ft.colors.WHITE,
                ),
                # Информация о пользователе
                ft.Column(
                    [
                        ft.Text(f"{user.name}", size=24, weight="bold", color=ft.colors.WHITE),
                        ft.Text(f"Баланс: {user.balance} ₽", size=20, color=ft.colors.GREEN_500),
                    ],
                    alignment="start",
                ),
            ],
            alignment="spaceBetween",
        )

        # Кнопки действий
        action_buttons = ft.Row(
            [
                ft.ElevatedButton(
                    "Добавить актив",
                    on_click=lambda e: add_asset(),
                    bgcolor=ft.colors.GREEN_500,
                    color=ft.colors.BLACK,
                ),
                ft.ElevatedButton(
                    "Пополнить баланс",
                    icon=ft.icons.ADD,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.BLUE_500,
                        color=ft.colors.WHITE,
                    ),
                    on_click=lambda e: top_up_balance(),
                ),
                ft.ElevatedButton(
                    text="Обновить данные",
                    icon=ft.icons.REFRESH,
                    style=ft.ButtonStyle(
                        bgcolor=ft.colors.BLUE_500,
                        color=ft.colors.WHITE,
                    ),
                    on_click=lambda e: refresh_data(),
                )
            ],
            alignment="spaceAround",
        )

        # Список активов
        asset_list = ft.Column(
            [
                # Заголовок колонок
                ft.Row(
                    [
                        ft.Text("Монета", size=18, weight="bold", expand=1, text_align="left"),
                        ft.Text("Количество", size=18, weight="bold", expand=1, text_align="left"),
                        ft.Text("Стоимость (₽)", size=18, weight="bold", expand=1, text_align="left"),
                        ft.Text("Действие", size=18, weight="bold", expand=1, text_align="center"),
                    ],
                    alignment="spaceBetween",
                    height=50,  # Высота заголовка
                ),
                ft.Divider(thickness=1, opacity=0.2),  # Линия под заголовком
            ],
            scroll="adaptive",  # Включаем прокрутку, если содержимое выходит за пределы
            height=400,  # Можно настроить высоту контейнера
        )

        # Данные для каждой строки
        for asset in assets:
            asset_row = ft.Row(
                [
                    ft.Text(asset.coin_name, size=16, expand=1, text_align="start"),  # Первая колонка
                    ft.Text(str(asset.quantity), size=16, expand=1, text_align="start"),  # Вторая колонка
                    ft.Text(f"{asset.value_rub} ₽", size=16, expand=1, text_align="start"),  # Третья колонка
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                text="Продать",
                                on_click=lambda e, a_id=asset.id: sell_asset(a_id),
                                bgcolor=ft.colors.ORANGE_500,
                                color=ft.colors.BLACK,
                            ),
                            ft.ElevatedButton(
                                text="Удалить",
                                on_click=lambda e, a_id=asset.id: delete_asset(a_id),
                                bgcolor=ft.colors.RED_500,
                                color=ft.colors.BLACK,
                            ),
                        ],
                        alignment="center",
                        expand=1,
                    ),
                ],
                alignment="spaceBetween",
                height=50,  # Высота строки
            )
            # Добавляем строку данных и разделитель
            asset_list.controls.extend([asset_row, ft.Divider(thickness=1, opacity=0.1)])

        # Если активов нет
        if not assets:
            asset_list.controls.append(
                ft.Text("У вас нет отслеживаемых активов.", size=16, italic=True, text_align="center")
            )

        # Объединение всех элементов
        page.controls.clear()
        page.controls.extend(
            [
                ft.Container(header, padding=10),
                ft.Divider(),
                action_buttons,
                ft.Divider(),
                ft.Text("Ваши активы:", size=24, weight="bold"),
                asset_list,
            ]
        )
        page.update()

    # Экран входа
    def show_login_screen():
        page.controls.clear()
        page.controls.extend([
            ft.Text("Авторизация", size=24),
            login_username_field,
            login_password_field,
            login_button,
            go_to_register_button,
        ])
        page.update()

    # Экран регистрации
    def show_register_screen():
        page.controls.clear()
        page.controls.extend([
            ft.Text("Регистрация", size=24),
            register_username_field,
            register_password_field,
            register_button,
            back_to_login_button,
        ])
        page.update()

    # Логика входа
    def login_user():
        try:
            username = login_username_field.value
            password = login_password_field.value

            if not username or not password:
                page.snack_bar = ft.SnackBar(ft.Text("Введите имя пользователя и пароль!"))
                page.snack_bar.open = True
                return

            user = check_user(username, password)
            if not user:
                page.snack_bar = ft.SnackBar(ft.Text("Пользователь не найден!"))
                page.snack_bar.open = True
                return

            # Если пользователь найден, показываем профиль
            show_profile(page, username)
        except ValueError as e:
            snack_bar = ft.SnackBar(ft.Text(str(e)))
            page.overlay.append(snack_bar)
            snack_bar.open = True
        except LookupError as e:
            snack_bar = ft.SnackBar(ft.Text(str(e)))
            page.overlay.append(snack_bar)
            snack_bar.open = True

    # Логика регистрации
    def register_user():
        username = register_username_field.value
        password = register_password_field.value

        if not username or not password:
            page.snack_bar = ft.SnackBar(ft.Text("Введите имя пользователя и пароль!"))
            page.snack_bar.open = True
            return

        try:
            add_user(username, password)
            page.snack_bar = ft.SnackBar(ft.Text("Пользователь успешно зарегистрирован!"))
            page.snack_bar.open = True
            show_login_screen()
        except sqlite3.IntegrityError:
            page.snack_bar = ft.SnackBar(ft.Text("Пользователь с таким именем уже существует!"))
            page.snack_bar.open = True

    # Изначально показываем экран входа
    show_login_screen()


if __name__ == "__main__":
    ft.app(target=main)
