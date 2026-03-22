import flet as ft
from logging import getLogger

from backend.liquidity_analyzer import analyze_liquidity, load_liquidity_profiles
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

logger = getLogger(__name__)

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
    profiles, error_message = load_liquidity_profiles(symbol)
    if error_message:
        logger.error(f"[SLIPPAGE] Ошибка чтения стаканов: {error_message}")
        return {}, error_message

    books = {}
    for exchange_name in EXCHANGE_TABLES:
        profile = profiles.get(exchange_name)
        if not profile:
            books[exchange_name] = None
            continue

        books[exchange_name] = {
            'current_price': _safe_float(profile.get('current_price')),
            'ask_levels': profile.get('ask_levels') or [],
            'bid_levels': profile.get('bid_levels') or [],
        }
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


def _get_score_color(score):
    if score >= 75:
        return SUCCESS_COLOR
    if score >= 50:
        return WARNING_COLOR
    return ACCENT_COLOR


def _get_quality_bg(score):
    return ft.colors.with_opacity(0.14, _get_score_color(score))


def _format_compact_money(value):
    value = _safe_float(value)
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def _build_liquidity_stat(title, value, subtitle, accent_color):
    return ft.Container(
        expand=True,
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        border_radius=14,
        bgcolor=ft.colors.with_opacity(0.16, "#0d131c"),
        border=ft.border.all(1, ft.colors.with_opacity(0.34, BORDER_COLOR)),
        content=ft.Column([
            ft.Row([
                ft.Container(
                    width=8,
                    height=8,
                    border_radius=999,
                    bgcolor=accent_color,
                ),
                ft.Text(title, size=9, weight='bold', color=TEXT_SECONDARY),
            ], spacing=8),
            ft.Container(height=6),
            ft.Text(value, size=15, weight='bold', color=TEXT_PRIMARY),
            ft.Text(subtitle, size=10, color=TEXT_SECONDARY),
        ], spacing=0),
    )


def _build_liquidity_exchange_row(exchange_score, is_leader):
    exchange_name = exchange_score.get('exchange_name')
    exchange_title = EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())
    score = exchange_score.get('liquidity_score', 0.0)
    score_color = _get_score_color(score)

    if not exchange_score.get('available'):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=12),
            border_radius=14,
            bgcolor=CARD_BG,
            border=ft.border.all(1, BORDER_COLOR),
            content=ft.Row([
                ft.Text(exchange_title, size=13, weight='bold', color=TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Text('Нет данных', size=12, color=TEXT_SECONDARY),
            ]),
        )

    return ft.Container(
        padding=ft.padding.symmetric(horizontal=14, vertical=12),
        border_radius=14,
        bgcolor=ft.colors.with_opacity(0.10, score_color),
        border=ft.border.all(
            1,
            ft.colors.with_opacity(0.45, score_color if is_leader else BORDER_COLOR),
        ),
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Container(
                        width=10,
                        height=10,
                        border_radius=999,
                        bgcolor=EXCHANGE_COLORS.get(exchange_name, score_color),
                    ),
                    ft.Text(exchange_title, size=13, weight='bold', color=TEXT_PRIMARY),
                ], spacing=8),
                ft.Container(expand=True),
                ft.Container(
                    visible=is_leader,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=999,
                    bgcolor=ft.colors.with_opacity(0.14, SUCCESS_COLOR),
                    content=ft.Text(
                        'ЛИДЕР',
                        size=9,
                        weight='bold',
                        color=SUCCESS_COLOR,
                    ),
                ),
                ft.Container(width=10),
                ft.Text(f"{score:.1f}", size=18, weight='bold', color=score_color),
            ], vertical_alignment='center'),
            ft.Container(height=10),
            ft.Row([
                _build_liquidity_stat(
                    'Качество',
                    exchange_score.get('execution_quality', 'низкая').upper(),
                    'общая оценка исполнения',
                    score_color,
                ),
                _build_liquidity_stat(
                    'Спред',
                    f"{exchange_score.get('spread_pct', 0.0):.4f}%",
                    'лучший bid/ask',
                    PRIMARY_COLOR,
                ),
                _build_liquidity_stat(
                    'Глубина',
                    _format_compact_money(exchange_score.get('depth_usdt', 0.0)),
                    'средняя по bid/ask 5 уровней',
                    SECONDARY_COLOR,
                ),
            ], spacing=10),
            ft.Container(height=10),
            ft.Row([
                _build_liquidity_stat(
                    'Buy 100/500/1000',
                    f"{exchange_score.get('avg_buy_slippage_pct', 0.0):.4f}%",
                    'среднее проскальзывание покупки',
                    ACCENT_COLOR,
                ),
                _build_liquidity_stat(
                    'Sell 100/500/1000',
                    f"{exchange_score.get('avg_sell_slippage_pct', 0.0):.4f}%",
                    'среднее проскальзывание продажи',
                    SUCCESS_COLOR,
                ),
                _build_liquidity_stat(
                    'Стабильность',
                    f"{exchange_score.get('stability_score', 0.0):.0f}/100",
                    (
                        f"комиссия {exchange_score.get('fee_pct', 0.0):.3f}% · "
                        f"мин. ордер {_format_compact_money(exchange_score.get('min_order_usdt', 0.0))}"
                    ),
                    WARNING_COLOR,
                ),
            ], spacing=10),
        ], spacing=0),
    )


def _build_liquidity_section(asset_name, analysis):
    overall_score = analysis.get('overall_score', 0.0)
    score_color = _get_score_color(overall_score)
    ranked_scores = analysis.get('ranked_scores') or []
    leader_name = ranked_scores[0]['exchange_name'] if ranked_scores else None
    best_entry_exchange = analysis.get('best_entry_exchange')
    best_exit_exchange = analysis.get('best_exit_exchange')
    benchmark_text = '/'.join(str(int(value)) for value in analysis.get('benchmark_amounts', []))

    return ft.Container(
        padding=20,
        border_radius=20,
        bgcolor=CARD_BG,
        border=ft.border.all(1, ft.colors.with_opacity(0.42, BORDER_COLOR)),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=20,
            color=ft.colors.with_opacity(0.18, '#000000'),
        ),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(
                        'ИНДЕКС КАЧЕСТВА ЛИКВИДНОСТИ',
                        size=12,
                        weight='bold',
                        color=TEXT_SECONDARY,
                    ),
                    ft.Text(
                        f'{asset_name}/USDT • исполнение по локальной БД',
                        size=20,
                        weight='bold',
                        color=TEXT_PRIMARY,
                    ),
                ], spacing=4),
                ft.Container(expand=True),
                ft.Text(
                    f'Эталонные объёмы: {benchmark_text} USDT',
                    size=11,
                    color=TEXT_SECONDARY,
                ),
            ], vertical_alignment='center'),
            ft.Container(height=18),
            ft.Row([
                ft.Container(
                    width=260,
                    padding=20,
                    border_radius=18,
                    gradient=ft.LinearGradient(
                        begin=ft.alignment.top_left,
                        end=ft.alignment.bottom_right,
                        colors=['#0f1722', '#0d131c', '#0b1017'],
                    ),
                    border=ft.border.all(
                        1,
                        ft.colors.with_opacity(0.45, score_color),
                    ),
                    content=ft.Column([
                        ft.Text('Liquidity Score', size=11, color=TEXT_SECONDARY),
                        ft.Container(height=6),
                        ft.Text(
                            f'{overall_score:.1f}',
                            size=42,
                            weight='bold',
                            color=score_color,
                        ),
                        ft.Text(
                            analysis.get('overall_quality', 'низкая').upper(),
                            size=13,
                            weight='bold',
                            color=TEXT_PRIMARY,
                        ),
                        ft.Container(height=10),
                        ft.ProgressBar(
                            value=min(max(overall_score / 100.0, 0.0), 1.0),
                            height=10,
                            color=score_color,
                            bgcolor=ft.colors.with_opacity(0.10, score_color),
                            border_radius=12,
                        ),
                        ft.Container(height=10),
                        ft.Text(
                            'Индекс учитывает спред, глубину 5 уровней, '\
                            'проскальзывание, комиссию, порог входа и устойчивость.',
                            size=11,
                            color=TEXT_SECONDARY,
                        ),
                    ], spacing=0),
                ),
                ft.Container(width=16),
                ft.Column([
                    ft.Row([
                        _build_liquidity_stat(
                            'Execution Quality',
                            analysis.get('overall_quality', 'низкая').upper(),
                            'общий режим ликвидности актива',
                            score_color,
                        ),
                        _build_liquidity_stat(
                            'Best Entry',
                            EXCHANGE_NAMES.get(best_entry_exchange, 'Нет данных'),
                            (
                                f"ориентир {analysis.get('reference_amount', 0.0):.0f} USDT"
                            ),
                            PRIMARY_COLOR,
                        ),
                    ], spacing=12),
                    ft.Container(height=12),
                    ft.Row([
                        _build_liquidity_stat(
                            'Best Exit',
                            EXCHANGE_NAMES.get(best_exit_exchange, 'Нет данных'),
                            (
                                f"ориентир {analysis.get('reference_amount', 0.0):.0f} USDT"
                            ),
                            SUCCESS_COLOR,
                        ),
                        _build_liquidity_stat(
                            'Market Coverage',
                            f"{len(ranked_scores)}/{len(EXCHANGE_TABLES)}",
                            'бирж с валидными данными ликвидности',
                            WARNING_COLOR,
                        ),
                    ], spacing=12),
                ], expand=True),
            ], vertical_alignment='start'),
            ft.Container(height=18),
            ft.Row([
                ft.Text('Рейтинг площадок', size=16, weight='bold', color=TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Text(
                    'Стабильность оценивается по свежести данных, полноте стакана, '\
                    'балансу bid/ask и гладкости котировок за 1 час.',
                    size=11,
                    color=TEXT_SECONDARY,
                ),
            ], vertical_alignment='center'),
            ft.Container(height=12),
            ft.Column([
                _build_liquidity_exchange_row(
                    exchange_score,
                    exchange_score.get('exchange_name') == leader_name,
                )
                for exchange_score in analysis.get('exchange_scores', [])
            ], spacing=12),
        ], spacing=0),
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
    liquidity_section_host = ft.Container()

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
            liquidity_section_host.content = None
            recommendation_title.value = 'Ожидается ввод суммы'
            recommendation_subtitle.value = (
                'Анализ появится после ввода корректного объёма сделки.'
            )
            page.update()
            return

        liquidity_analysis, liquidity_error = analyze_liquidity(
            symbol,
            reference_amount=target_usdt,
        )
        if liquidity_error:
            liquidity_section_host.content = ft.Container(
                padding=20,
                border_radius=18,
                bgcolor=CARD_BG,
                border=ft.border.all(1, ft.colors.with_opacity(0.30, ACCENT_COLOR)),
                content=ft.Text(
                    liquidity_error,
                    size=12,
                    color=TEXT_SECONDARY,
                ),
            )
        else:
            liquidity_section_host.content = _build_liquidity_section(
                asset_name,
                liquidity_analysis,
            )

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
                                ft.Text('АНАЛИЗ ПРОСКАЛЬЗЫВАНИЯ', size=24, weight='bold', color=TEXT_PRIMARY),
                                ft.Text(
                                    f'{symbol} • стакан заявок по трём биржам',
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
                        liquidity_section_host,
                        ft.Container(height=18),
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
