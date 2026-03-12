import threading

import flet as ft
from logging import getLogger

from data.database import DatabaseManager
from ui.config import (
    ACCENT_COLOR,
    BORDER_COLOR,
    CARD_BG,
    DARK_BG,
    EXCHANGE_COLORS,
    EXCHANGE_NAMES,
    PRIMARY_COLOR,
    SUCCESS_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
)

logger = getLogger(__name__)

AI_GRADIENT_UP = "#00ff88"
AI_GRADIENT_DOWN = "#ff3366"
AI_PANEL_BG = "#0d1117"

EXCHANGE_TABLES = {
    'mexc': 'mexc_pairs',
    'bybit': 'bybit_pairs',
    'gateio': 'gateio_pairs',
}

STABLE_ASSETS = {'USDT', 'USDC', 'BUSD', 'DAI'}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _normalize_levels(prices, volumes):
    levels = []
    for price, volume in zip(prices or [], volumes or []):
        price_value = _safe_float(price)
        volume_value = _safe_float(volume)
        if price_value > 0 and volume_value > 0:
            levels.append((price_value, volume_value))
    return levels[:5]


def _format_money(value):
    return f"${value:,.2f}"


def _format_qty(value, asset_name):
    return f"{value:,.6f} {asset_name}"


def _load_order_books(symbol):
    db = DatabaseManager()
    if not db.connect():
        return {}, 'Не удалось подключиться к базе данных'

    books = {}
    try:
        for exchange_name, table_name in EXCHANGE_TABLES.items():
            db.cursor.execute(
                f"""
                SELECT current_price, ask_price, ask_volume, bid_price, bid_volume
                FROM {table_name}
                WHERE symbol = %s
                """,
                (symbol,),
            )
            row = db.cursor.fetchone()
            if not row:
                books[exchange_name] = None
                continue

            current_price, ask_price, ask_volume, bid_price, bid_volume = row
            books[exchange_name] = {
                'current_price': _safe_float(current_price),
                'ask_levels': _normalize_levels(ask_price, ask_volume),
                'bid_levels': _normalize_levels(bid_price, bid_volume),
            }
    except Exception as error:
        logger.error(f"[SLIPPAGE] Ошибка чтения стаканов: {error}")
        return {}, 'Не удалось получить данные стакана'
    finally:
        db.close()

    return books, None


def _simulate_buy(levels, target_usdt):
    if not levels:
        return {
            'available': False,
            'filled': False,
            'coverage': 0.0,
        }

    remaining = max(target_usdt, 0.0)
    spent_usdt = 0.0
    received_qty = 0.0
    total_depth_usdt = 0.0
    best_price = levels[0][0]

    for price, volume in levels:
        level_notional = price * volume
        total_depth_usdt += level_notional
        if remaining <= 0:
            continue

        take_notional = min(remaining, level_notional)
        take_qty = take_notional / price
        spent_usdt += take_notional
        received_qty += take_qty
        remaining -= take_notional

    avg_price = spent_usdt / received_qty if received_qty > 0 else 0.0
    slippage_pct = ((avg_price / best_price) - 1) * 100 if best_price else 0.0
    coverage = spent_usdt / target_usdt if target_usdt > 0 else 0.0

    return {
        'available': True,
        'filled': remaining <= 1e-9,
        'coverage': min(coverage, 1.0),
        'requested_usdt': target_usdt,
        'spent_usdt': spent_usdt,
        'received_qty': received_qty,
        'remaining_usdt': max(remaining, 0.0),
        'avg_price': avg_price,
        'best_price': best_price,
        'slippage_pct': max(slippage_pct, 0.0),
        'depth_usdt': total_depth_usdt,
        'levels_count': len(levels),
    }


def _simulate_sell(levels, target_usdt):
    if not levels:
        return {
            'available': False,
            'filled': False,
            'coverage': 0.0,
        }

    remaining = max(target_usdt, 0.0)
    received_usdt = 0.0
    sold_qty = 0.0
    total_depth_usdt = 0.0
    best_price = levels[0][0]

    for price, volume in levels:
        level_notional = price * volume
        total_depth_usdt += level_notional
        if remaining <= 0:
            continue

        take_notional = min(remaining, level_notional)
        take_qty = take_notional / price
        received_usdt += take_notional
        sold_qty += take_qty
        remaining -= take_notional

    avg_price = received_usdt / sold_qty if sold_qty > 0 else 0.0
    slippage_pct = (1 - (avg_price / best_price)) * 100 if best_price else 0.0
    coverage = received_usdt / target_usdt if target_usdt > 0 else 0.0

    return {
        'available': True,
        'filled': remaining <= 1e-9,
        'coverage': min(coverage, 1.0),
        'requested_usdt': target_usdt,
        'received_usdt': received_usdt,
        'sold_qty': sold_qty,
        'remaining_usdt': max(remaining, 0.0),
        'avg_price': avg_price,
        'best_price': best_price,
        'slippage_pct': max(slippage_pct, 0.0),
        'depth_usdt': total_depth_usdt,
        'levels_count': len(levels),
    }


def _select_best_result(results, side):
    valid_results = [result for result in results if result.get('available')]
    if not valid_results:
        return None

    if side == 'buy':
        return max(
            valid_results,
            key=lambda result: (
                1 if result.get('filled') else 0,
                result.get('coverage', 0.0),
                result.get('received_qty', 0.0),
                -result.get('avg_price', 0.0),
            ),
        )

    return max(
        valid_results,
        key=lambda result: (
            1 if result.get('filled') else 0,
            result.get('coverage', 0.0),
            -result.get('sold_qty', float('inf')),
            result.get('avg_price', 0.0),
        ),
    )


def _build_depth_lines(levels, color):
    rows = []
    for index, (price, volume) in enumerate(levels[:5], start=1):
        rows.append(
            ft.Container(
                content=ft.Row([
                    ft.Text(f"{index}", size=11, color=TEXT_SECONDARY),
                    ft.Container(expand=True),
                    ft.Text(f"{price:,.4f}", size=11, color=color),
                    ft.Container(width=12),
                    ft.Text(f"{volume:,.4f}", size=11, color=TEXT_PRIMARY),
                ]),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                bgcolor=ft.colors.with_opacity(0.04, color),
                border_radius=8,
            )
        )

    if not rows:
        rows.append(ft.Text('Нет данных стакана', size=11, color=TEXT_SECONDARY))
    return rows


def _build_result_card(asset_name, exchange_name, side, result, book, is_best):
    exchange_color = EXCHANGE_COLORS.get(exchange_name, PRIMARY_COLOR)
    exchange_title = EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())

    if not result.get('available'):
        return ft.Container(
            expand=True,
            padding=22,
            bgcolor=CARD_BG,
            border_radius=18,
            border=ft.border.all(1, BORDER_COLOR),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.SHOW_CHART, color=exchange_color),
                    ft.Text(exchange_title, size=18, weight='bold', color=TEXT_PRIMARY),
                ]),
                ft.Container(height=20),
                ft.Text('Пара недоступна в локальной базе', size=13, color=TEXT_SECONDARY),
            ]),
        )

    fill_color = SUCCESS_COLOR if result.get('filled') else WARNING_COLOR
    side_levels = book['ask_levels'] if side == 'buy' else book['bid_levels']
    side_color = ACCENT_COLOR if side == 'buy' else SUCCESS_COLOR

    primary_value = (
        _format_qty(result.get('received_qty', 0.0), asset_name)
        if side == 'buy'
        else _format_qty(result.get('sold_qty', 0.0), asset_name)
    )
    primary_label = 'Получите актива' if side == 'buy' else 'Нужно продать'
    quote_value = (
        _format_money(result.get('spent_usdt', 0.0))
        if side == 'buy'
        else _format_money(result.get('received_usdt', 0.0))
    )
    quote_label = 'Будет потрачено' if side == 'buy' else 'Будет получено'

    return ft.Container(
        expand=True,
        padding=22,
        bgcolor=CARD_BG,
        border_radius=18,
        border=ft.border.all(
            1,
            ft.colors.with_opacity(0.55, exchange_color if is_best else BORDER_COLOR),
        ),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=18,
            color=ft.colors.with_opacity(0.18, exchange_color),
        ),
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Container(
                        width=12,
                        height=12,
                        border_radius=6,
                        bgcolor=exchange_color,
                    ),
                    ft.Text(exchange_title, size=18, weight='bold', color=TEXT_PRIMARY),
                ], spacing=10),
                ft.Container(expand=True),
                ft.Container(
                    visible=is_best,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    bgcolor=ft.colors.with_opacity(0.15, SUCCESS_COLOR),
                    border_radius=20,
                    content=ft.Text(
                        'ЛУЧШИЙ ВАРИАНТ',
                        size=10,
                        weight='bold',
                        color=SUCCESS_COLOR,
                    ),
                ),
            ]),
            ft.Container(height=14),
            ft.Container(
                padding=ft.padding.symmetric(horizontal=14, vertical=12),
                bgcolor=ft.colors.with_opacity(0.08, exchange_color),
                border_radius=14,
                content=ft.Row([
                    ft.Column([
                        ft.Text(primary_label, size=11, color=TEXT_SECONDARY),
                        ft.Text(primary_value, size=18, weight='bold', color=TEXT_PRIMARY),
                    ], spacing=4, expand=True),
                    ft.Column([
                        ft.Text(quote_label, size=11, color=TEXT_SECONDARY),
                        ft.Text(quote_value, size=18, weight='bold', color=exchange_color),
                    ], spacing=4, horizontal_alignment='end'),
                ]),
            ),
            ft.Container(height=14),
            ft.Row([
                ft.Column([
                    ft.Text('Лучшая цена', size=11, color=TEXT_SECONDARY),
                    ft.Text(
                        f"{result.get('best_price', 0.0):,.4f}",
                        size=14,
                        weight='bold',
                        color=TEXT_PRIMARY,
                    ),
                ], spacing=4, expand=True),
                ft.Column([
                    ft.Text('Средняя цена', size=11, color=TEXT_SECONDARY),
                    ft.Text(
                        f"{result.get('avg_price', 0.0):,.4f}",
                        size=14,
                        weight='bold',
                        color=TEXT_PRIMARY,
                    ),
                ], spacing=4, expand=True),
                ft.Column([
                    ft.Text('Проскальзывание', size=11, color=TEXT_SECONDARY),
                    ft.Text(
                        f"{result.get('slippage_pct', 0.0):.4f}%",
                        size=14,
                        weight='bold',
                        color=fill_color,
                    ),
                ], spacing=4, expand=True),
            ], spacing=12),
            ft.Container(height=12),
            ft.Row([
                ft.Text('Покрытие заявки', size=11, color=TEXT_SECONDARY),
                ft.Container(expand=True),
                ft.Text(
                    f"{result.get('coverage', 0.0) * 100:.1f}%",
                    size=11,
                    color=fill_color,
                    weight='bold',
                ),
            ]),
            ft.ProgressBar(
                value=result.get('coverage', 0.0),
                height=8,
                color=fill_color,
                bgcolor=ft.colors.with_opacity(0.08, fill_color),
                border_radius=8,
            ),
            ft.Container(height=12),
            ft.Row([
                ft.Text('Ликвидность 5 уровней', size=11, color=TEXT_SECONDARY),
                ft.Container(expand=True),
                ft.Text(
                    _format_money(result.get('depth_usdt', 0.0)),
                    size=11,
                    weight='bold',
                    color=TEXT_PRIMARY,
                ),
            ]),
            ft.Container(height=14),
            ft.Text('Глубина стакана', size=12, color=TEXT_SECONDARY, weight='bold'),
            ft.Column(_build_depth_lines(side_levels, side_color), spacing=6),
        ], spacing=0),
    )


def _build_prediction_loading():
    """Панель загрузки прогноза."""
    return ft.Container(
        padding=24,
        bgcolor=AI_PANEL_BG,
        border_radius=18,
        border=ft.border.all(1, ft.colors.with_opacity(0.2, PRIMARY_COLOR)),
        content=ft.Row([
            ft.ProgressRing(
                width=28, height=28, stroke_width=3, color=PRIMARY_COLOR,
            ),
            ft.Container(width=14),
            ft.Column([
                ft.Text(
                    'ПРОГНОЗ ИИ',
                    size=14, weight='bold', color=PRIMARY_COLOR,
                ),
                ft.Text(
                    'Анализ дневных свечей и обучение модели...',
                    size=12, color=TEXT_SECONDARY,
                ),
            ], spacing=4),
        ], vertical_alignment='center'),
    )


def _build_prediction_error(error_message):
    """Панель ошибки прогноза."""
    return ft.Container(
        padding=24,
        bgcolor=AI_PANEL_BG,
        border_radius=18,
        border=ft.border.all(1, ft.colors.with_opacity(0.2, ACCENT_COLOR)),
        content=ft.Row([
            ft.Container(
                width=44, height=44, border_radius=22,
                bgcolor=ft.colors.with_opacity(0.12, ACCENT_COLOR),
                alignment=ft.alignment.center,
                content=ft.Icon(
                    ft.icons.ERROR_OUTLINE_ROUNDED, color=ACCENT_COLOR, size=24,
                ),
            ),
            ft.Container(width=14),
            ft.Column([
                ft.Text(
                    'ПРОГНОЗ ИИ', size=14, weight='bold', color=ACCENT_COLOR,
                ),
                ft.Text(error_message, size=12, color=TEXT_SECONDARY),
            ], spacing=4, expand=True),
        ], vertical_alignment='center'),
    )


def _build_prediction_result(prediction):
    """Панель с результатом прогноза — красивый дизайн."""
    prob_up = prediction.get('prob_up', 50.0)
    prob_down = prediction.get('prob_down', 50.0)
    signal = prediction.get('signal', 'up')
    confidence = prediction.get('confidence', 50.0)

    is_up = signal == 'up'
    signal_color = AI_GRADIENT_UP if is_up else AI_GRADIENT_DOWN
    signal_icon = ft.icons.TRENDING_UP_ROUNDED if is_up else ft.icons.TRENDING_DOWN_ROUNDED
    signal_text = 'РОСТ' if is_up else 'ПАДЕНИЕ'
    signal_desc = (
        'Модель прогнозирует рост цены' if is_up
        else 'Модель прогнозирует снижение цены'
    )

    return ft.Container(
        padding=24,
        bgcolor=AI_PANEL_BG,
        border_radius=18,
        border=ft.border.all(1, ft.colors.with_opacity(0.25, signal_color)),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=24,
            color=ft.colors.with_opacity(0.10, signal_color),
        ),
        content=ft.Row([
            # Левая часть: крупный индикатор сигнала
            ft.Container(
                width=82, height=82, border_radius=41,
                bgcolor=ft.colors.with_opacity(0.12, signal_color),
                border=ft.border.all(3, ft.colors.with_opacity(0.45, signal_color)),
                alignment=ft.alignment.center,
                content=ft.Icon(signal_icon, size=42, color=signal_color),
            ),
            ft.Container(width=22),
            # Центральная часть: бары вероятностей
            ft.Column([
                ft.Row([
                    ft.Text(
                        'ПРОГНОЗ ИИ',
                        size=11, weight='bold', color=PRIMARY_COLOR,
                    ),
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                        bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                        border_radius=6,
                        content=ft.Text(
                            'XGBoost', size=10, weight='bold', color=PRIMARY_COLOR,
                        ),
                    ),
                ], spacing=10),
                ft.Container(height=10),
                # Бар роста
                ft.Row([
                    ft.Icon(
                        ft.icons.ARROW_UPWARD_ROUNDED, size=18, color=AI_GRADIENT_UP,
                    ),
                    ft.Text(
                        'Рост', size=13, color=TEXT_SECONDARY, width=55,
                    ),
                    ft.Container(
                        expand=True, height=12, border_radius=6,
                        bgcolor=ft.colors.with_opacity(0.06, AI_GRADIENT_UP),
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Container(
                            width=max(prob_up * 3.5, 2),
                            height=12,
                            border_radius=6,
                            bgcolor=AI_GRADIENT_UP,
                        ),
                        alignment=ft.alignment.center_left,
                    ),
                    ft.Text(
                        f'{prob_up:.1f}%', size=16, weight='bold',
                        color=AI_GRADIENT_UP, width=68, text_align='right',
                    ),
                ], spacing=8, vertical_alignment='center'),
                ft.Container(height=6),
                # Бар падения
                ft.Row([
                    ft.Icon(
                        ft.icons.ARROW_DOWNWARD_ROUNDED, size=18, color=AI_GRADIENT_DOWN,
                    ),
                    ft.Text(
                        'Падение', size=13, color=TEXT_SECONDARY, width=55,
                    ),
                    ft.Container(
                        expand=True, height=12, border_radius=6,
                        bgcolor=ft.colors.with_opacity(0.06, AI_GRADIENT_DOWN),
                        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                        content=ft.Container(
                            width=max(prob_down * 3.5, 2),
                            height=12,
                            border_radius=6,
                            bgcolor=AI_GRADIENT_DOWN,
                        ),
                        alignment=ft.alignment.center_left,
                    ),
                    ft.Text(
                        f'{prob_down:.1f}%', size=16, weight='bold',
                        color=AI_GRADIENT_DOWN, width=68, text_align='right',
                    ),
                ], spacing=8, vertical_alignment='center'),
            ], expand=True, spacing=0),
            ft.Container(width=22),
            # Правая часть: сводка сигнала
            ft.Container(
                width=190,
                padding=ft.padding.symmetric(horizontal=18, vertical=14),
                bgcolor=ft.colors.with_opacity(0.08, signal_color),
                border_radius=16,
                border=ft.border.all(1, ft.colors.with_opacity(0.15, signal_color)),
                content=ft.Column([
                    ft.Text(
                        'Сигнал', size=11, color=TEXT_SECONDARY,
                    ),
                    ft.Text(
                        signal_text, size=22, weight='bold', color=signal_color,
                    ),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Text(
                            'Уверенность', size=11, color=TEXT_SECONDARY,
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            f'{confidence:.1f}%', size=13, weight='bold',
                            color=TEXT_PRIMARY,
                        ),
                    ]),
                    ft.ProgressBar(
                        value=confidence / 100,
                        height=6,
                        color=signal_color,
                        bgcolor=ft.colors.with_opacity(0.08, signal_color),
                        border_radius=6,
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        signal_desc, size=10, color=TEXT_SECONDARY, italic=True,
                    ),
                    ft.Text(
                        '23 техн. индикатора • дневные свечи',
                        size=9, color=ft.colors.with_opacity(0.5, TEXT_SECONDARY),
                    ),
                ], spacing=2, horizontal_alignment='center'),
            ),
        ], vertical_alignment='center'),
    )


def show_slippage_analysis_dialog(page: ft.Page, asset: dict):
    asset_name = (asset or {}).get('currency', '').upper()
    if not asset_name or asset_name in STABLE_ASSETS:
        snack = ft.SnackBar(
            content=ft.Text('Для анализа выберите торгуемый актив', color=TEXT_PRIMARY),
            bgcolor=CARD_BG,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()
        return

    symbol = f'{asset_name}/USDT'
    order_books, error_message = _load_order_books(symbol)
    if error_message:
        snack = ft.SnackBar(
            content=ft.Text(error_message, color=TEXT_PRIMARY),
            bgcolor=CARD_BG,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()
        return

    selected_side = {'value': 'buy'}
    amount_field = ft.TextField(
        value='100',
        width=220,
        height=58,
        text_size=20,
        text_align='right',
        suffix_text='USDT',
        bgcolor=CARD_BG,
        border_color=BORDER_COLOR,
        focused_border_color=PRIMARY_COLOR,
        content_padding=ft.padding.symmetric(horizontal=18, vertical=14),
    )
    results_row = ft.Row(spacing=18, vertical_alignment='start')
    recommendation_title = ft.Text('', size=22, weight='bold', color=TEXT_PRIMARY)
    recommendation_subtitle = ft.Text('', size=13, color=TEXT_SECONDARY)
    status_text = ft.Text('', size=12, color=WARNING_COLOR, visible=False)

    # Контейнер для прогноза ИИ (заполняется асинхронно)
    prediction_container = ft.Container(content=_build_prediction_loading())

    def _run_prediction():
        """Запуск ML-прогноза в фоновом потоке."""
        try:
            from ml.predictor import predict_direction
            result = predict_direction(symbol)
            if result.get('status') == 'ok':
                prediction_container.content = _build_prediction_result(result)
            else:
                prediction_container.content = _build_prediction_error(
                    result.get('error', 'Неизвестная ошибка'),
                )
        except Exception as exc:
            logger.error('[PREDICTION] %s', exc)
            prediction_container.content = _build_prediction_error(str(exc))
        try:
            page.update()
        except Exception:
            pass

    threading.Thread(target=_run_prediction, daemon=True).start()

    def close_dialog():
        dialog.open = False
        page.update()

    def set_side(new_side):
        selected_side['value'] = new_side
        buy_btn.bgcolor = (
            SUCCESS_COLOR
            if new_side == 'buy'
            else ft.colors.with_opacity(0.08, SUCCESS_COLOR)
        )
        buy_btn.content.controls[0].color = DARK_BG if new_side == 'buy' else SUCCESS_COLOR
        buy_btn.content.controls[2].color = DARK_BG if new_side == 'buy' else SUCCESS_COLOR
        sell_btn.bgcolor = (
            ACCENT_COLOR
            if new_side == 'sell'
            else ft.colors.with_opacity(0.08, ACCENT_COLOR)
        )
        sell_btn.content.controls[0].color = DARK_BG if new_side == 'sell' else ACCENT_COLOR
        sell_btn.content.controls[2].color = DARK_BG if new_side == 'sell' else ACCENT_COLOR
        refresh_analysis()

    def refresh_analysis(e=None):
        target_usdt = _safe_float(amount_field.value)
        if target_usdt <= 0:
            status_text.value = 'Введите сумму сделки в USDT больше нуля'
            status_text.visible = True
            results_row.controls = []
            recommendation_title.value = 'Ожидается ввод суммы'
            recommendation_subtitle.value = (
                'Анализ появится после ввода корректного объёма сделки.'
            )
            page.update()
            return

        side = selected_side['value']
        results = []
        for exchange_name in EXCHANGE_TABLES:
            book = order_books.get(exchange_name)
            if not book:
                results.append({'exchange_name': exchange_name, 'available': False})
                continue

            levels = book['ask_levels'] if side == 'buy' else book['bid_levels']
            result = (
                _simulate_buy(levels, target_usdt)
                if side == 'buy'
                else _simulate_sell(levels, target_usdt)
            )
            result['exchange_name'] = exchange_name
            results.append(result)

        best_result = _select_best_result(results, side)
        best_exchange_name = best_result.get('exchange_name') if best_result else None
        results_row.controls = [
            _build_result_card(
                asset_name,
                result['exchange_name'],
                side,
                result,
                order_books.get(result['exchange_name']) or {
                    'ask_levels': [],
                    'bid_levels': [],
                },
                result['exchange_name'] == best_exchange_name,
            )
            for result in results
        ]

        if not best_result:
            recommendation_title.value = 'Нет данных для анализа'
            recommendation_subtitle.value = (
                'В локальной базе пока нет достаточной глубины стакана по этой паре.'
            )
            status_text.visible = False
            page.update()
            return

        if side == 'buy':
            recommendation_title.value = (
                f"Лучше покупать через {EXCHANGE_NAMES.get(best_exchange_name, best_exchange_name)}"
            )
            recommendation_subtitle.value = (
                f"За {_format_money(target_usdt)} вы получите "
                f"{best_result.get('received_qty', 0.0):,.6f} {asset_name} "
                f"со средним исполнением {best_result.get('avg_price', 0.0):,.4f} "
                f"и проскальзыванием {best_result.get('slippage_pct', 0.0):.4f}%."
            )
        else:
            recommendation_title.value = (
                f"Лучше продавать через {EXCHANGE_NAMES.get(best_exchange_name, best_exchange_name)}"
            )
            recommendation_subtitle.value = (
                f"Чтобы получить {_format_money(target_usdt)}, потребуется продать "
                f"{best_result.get('sold_qty', 0.0):,.6f} {asset_name} "
                f"со средней ценой {best_result.get('avg_price', 0.0):,.4f}."
            )

        if not best_result.get('filled'):
            status_text.value = (
                'В первых 5 уровнях стакана недостаточно ликвидности '
                'для полного исполнения на лучшей площадке.'
            )
            status_text.visible = True
        else:
            status_text.visible = False
        page.update()

    buy_btn = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.ARROW_DOWNWARD_ROUNDED, size=22, color=DARK_BG),
            ft.Container(width=8),
            ft.Text('КУПИТЬ', size=15, weight='bold', color=DARK_BG),
        ], alignment='center'),
        expand=True,
        height=62,
        padding=ft.padding.symmetric(horizontal=16),
        bgcolor=SUCCESS_COLOR,
        border_radius=ft.border_radius.only(top_left=12, bottom_left=12),
        alignment=ft.alignment.center,
        ink=True,
        on_click=lambda e: set_side('buy'),
    )
    sell_btn = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.ARROW_UPWARD_ROUNDED, size=22, color=ACCENT_COLOR),
            ft.Container(width=8),
            ft.Text('ПРОДАТЬ', size=15, weight='bold', color=ACCENT_COLOR),
        ], alignment='center'),
        expand=True,
        height=62,
        padding=ft.padding.symmetric(horizontal=16),
        bgcolor=ft.colors.with_opacity(0.08, ACCENT_COLOR),
        border_radius=ft.border_radius.only(top_right=12, bottom_right=12),
        alignment=ft.alignment.center,
        ink=True,
        on_click=lambda e: set_side('sell'),
    )

    dialog = ft.AlertDialog(
        modal=True,
        title=None,
        content=ft.Container(
            width=1160,
            height=980,
            bgcolor=DARK_BG,
            border_radius=20,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column([
                ft.Container(
                    padding=24,
                    bgcolor=CARD_BG,
                    border=ft.border.only(bottom=ft.BorderSide(1, BORDER_COLOR)),
                    content=ft.Row([
                        ft.Row([
                            ft.Container(
                                width=54,
                                height=54,
                                border_radius=14,
                                bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                                alignment=ft.alignment.center,
                                content=ft.Icon(ft.icons.SHOW_CHART, color=PRIMARY_COLOR, size=30),
                            ),
                            ft.Container(width=14),
                            ft.Column([
                                ft.Text('АНАЛИЗ ПРОСКАЛЬЗЫВАНИЯ И ПРОГНОЗ', size=24, weight='bold', color=TEXT_PRIMARY),
                                ft.Text(
                                    f'{symbol} • XGBoost + стакан заявок по трём биржам',
                                    size=13,
                                    color=TEXT_SECONDARY,
                                ),
                            ], spacing=4),
                        ]),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.icons.CLOSE_ROUNDED,
                            icon_color=TEXT_SECONDARY,
                            tooltip='Закрыть',
                            on_click=lambda e: close_dialog(),
                        ),
                    ], vertical_alignment='center'),
                ),
                ft.Container(
                    expand=True,
                    padding=24,
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                expand=True,
                                padding=20,
                                bgcolor=CARD_BG,
                                border_radius=18,
                                border=ft.border.all(1, BORDER_COLOR),
                                content=ft.Column([
                                    ft.Text('Параметры сделки', size=12, color=TEXT_SECONDARY, weight='bold'),
                                    ft.Container(height=14),
                                    ft.Row([
                                        ft.Column([
                                            ft.Text('Сторона сделки', size=11, color=TEXT_SECONDARY),
                                            ft.Container(height=8),
                                            ft.Container(
                                                content=ft.Row([buy_btn, sell_btn], spacing=0),
                                                height=62,
                                                border_radius=12,
                                                border=ft.border.all(1, BORDER_COLOR),
                                            ),
                                        ], expand=True),
                                        ft.Container(width=18),
                                        ft.Column([
                                            ft.Text('Объём в USDT', size=11, color=TEXT_SECONDARY),
                                            ft.Container(height=8),
                                            amount_field,
                                        ]),
                                    ], vertical_alignment='end'),
                                ], spacing=0),
                            ),
                            ft.Container(width=18),
                            ft.Container(
                                width=360,
                                padding=20,
                                bgcolor=ft.colors.with_opacity(0.08, PRIMARY_COLOR),
                                border_radius=18,
                                border=ft.border.all(1, ft.colors.with_opacity(0.25, PRIMARY_COLOR)),
                                content=ft.Column([
                                    ft.Text('Рекомендация', size=12, color=TEXT_SECONDARY, weight='bold'),
                                    ft.Container(height=12),
                                    recommendation_title,
                                    ft.Container(height=8),
                                    recommendation_subtitle,
                                    ft.Container(height=12),
                                    status_text,
                                ], spacing=0),
                            ),
                        ]),
                        ft.Container(height=16),
                        prediction_container,
                        ft.Container(height=16),
                        ft.Row([
                            ft.Text('Сравнение исполнения', size=18, weight='bold', color=TEXT_PRIMARY),
                            ft.Container(expand=True),
                            ft.Text(
                                'Учитываются первые 5 уровней bid/ask из локальной БД',
                                size=12,
                                color=TEXT_SECONDARY,
                            ),
                        ]),
                        ft.Container(height=10),
                        ft.Container(expand=True, content=results_row),
                    ], spacing=0, scroll='auto'),
                ),
            ], spacing=0),
        ),
        bgcolor=ft.colors.TRANSPARENT,
        content_padding=0,
        inset_padding=24,
        shape=ft.RoundedRectangleBorder(radius=20),
    )

    page.overlay.append(dialog)
    dialog.open = True
    amount_field.on_change = refresh_analysis
    refresh_analysis()
