import ast
from datetime import datetime, timezone

from data.database import DatabaseManager

EXCHANGE_TABLES = {
    'mexc': 'mexc_pairs',
    'bybit': 'bybit_pairs',
    'gateio': 'gateio_pairs',
}

DEFAULT_BENCHMARK_AMOUNTS = (100.0, 500.0, 1000.0)


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


def _parse_quotes(quotes_raw):
    if not quotes_raw:
        return []

    try:
        values = ast.literal_eval(str(quotes_raw))
    except Exception:
        return []

    if not isinstance(values, (list, tuple)):
        return []

    parsed = []
    for value in values:
        value_float = _safe_float(value)
        if value_float > 0:
            parsed.append(value_float)
    return parsed


def _normalize_timestamp(timestamp_value):
    if not timestamp_value:
        return None
    if getattr(timestamp_value, 'tzinfo', None) is None:
        return timestamp_value.replace(tzinfo=timezone.utc)
    return timestamp_value.astimezone(timezone.utc)


def _metric_score_lower_is_better(value, good, bad):
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    ratio = (value - good) / (bad - good)
    return max(0.0, 100.0 * (1.0 - ratio))


def _metric_score_higher_is_better(value, bad, good):
    if value <= bad:
        return 0.0
    if value >= good:
        return 100.0
    ratio = (value - bad) / (good - bad)
    return max(0.0, min(100.0, 100.0 * ratio))


def load_liquidity_profiles(symbol):
    db = DatabaseManager()
    if not db.connect():
        return {}, 'Не удалось подключиться к базе данных'

    profiles = {}
    try:
        for exchange_name, table_name in EXCHANGE_TABLES.items():
            db.cursor.execute(
                f"""
                SELECT current_price, ask_price, ask_volume, bid_price, bid_volume,
                       taker_fee, maker_fee, min_order_amount, lot_size,
                       volume_24h, quotes_1h, updated_at
                FROM {table_name}
                WHERE symbol = %s
                """,
                (symbol,),
            )
            row = db.cursor.fetchone()
            if not row:
                profiles[exchange_name] = None
                continue

            (
                current_price,
                ask_price,
                ask_volume,
                bid_price,
                bid_volume,
                taker_fee,
                maker_fee,
                min_order_amount,
                lot_size,
                volume_24h,
                quotes_1h,
                updated_at,
            ) = row

            ask_levels = _normalize_levels(ask_price, ask_volume)
            bid_levels = _normalize_levels(bid_price, bid_volume)
            best_ask = ask_levels[0][0] if ask_levels else 0.0
            best_bid = bid_levels[0][0] if bid_levels else 0.0
            mid_price = (best_ask + best_bid) / 2 if best_ask and best_bid else 0.0
            spread_pct = (
                ((best_ask - best_bid) / mid_price) * 100.0
                if mid_price > 0
                else 0.0
            )

            profiles[exchange_name] = {
                'symbol': symbol,
                'current_price': _safe_float(current_price),
                'ask_levels': ask_levels,
                'bid_levels': bid_levels,
                'best_ask': best_ask,
                'best_bid': best_bid,
                'mid_price': mid_price,
                'spread_pct': spread_pct,
                'taker_fee': _safe_float(taker_fee),
                'maker_fee': _safe_float(maker_fee),
                'min_order_amount': _safe_float(min_order_amount),
                'lot_size': _safe_float(lot_size),
                'volume_24h': _safe_float(volume_24h),
                'quotes_1h': _parse_quotes(quotes_1h),
                'updated_at': updated_at,
            }
    except Exception:
        return {}, 'Не удалось получить данные ликвидности'
    finally:
        db.close()

    return profiles, None


def simulate_buy(levels, target_usdt):
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


def simulate_sell(levels, target_usdt):
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


def select_best_result(results, side):
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


def _calculate_stability_score(profile, max_benchmark_amount):
    ask_levels = profile.get('ask_levels') or []
    bid_levels = profile.get('bid_levels') or []
    ask_depth = sum(price * volume for price, volume in ask_levels)
    bid_depth = sum(price * volume for price, volume in bid_levels)
    total_depth = ask_depth + bid_depth

    level_completeness = min(len(ask_levels), len(bid_levels)) / 5.0
    completeness_score = max(0.0, min(100.0, level_completeness * 100.0))

    depth_balance = 0.0
    if total_depth > 0:
        depth_balance = 1.0 - abs(ask_depth - bid_depth) / total_depth
    balance_score = max(0.0, min(100.0, depth_balance * 100.0))

    freshness_score = 35.0
    normalized_updated_at = _normalize_timestamp(profile.get('updated_at'))
    if normalized_updated_at:
        age_seconds = max(
            0.0,
            (datetime.now(timezone.utc) - normalized_updated_at).total_seconds(),
        )
        freshness_score = _metric_score_lower_is_better(
            age_seconds,
            good=20.0,
            bad=600.0,
        )

    quotes = profile.get('quotes_1h') or []
    quote_volatility_pct = 2.0
    if len(quotes) >= 3:
        average_price = sum(quotes) / len(quotes)
        if average_price > 0:
            quote_range_pct = ((max(quotes) - min(quotes)) / average_price) * 100.0
            quote_volatility_pct = quote_range_pct
    quote_score = _metric_score_lower_is_better(
        quote_volatility_pct,
        good=0.4,
        bad=5.0,
    )

    depth_support_score = _metric_score_higher_is_better(
        total_depth,
        bad=max_benchmark_amount,
        good=max_benchmark_amount * 8.0,
    )

    return (
        freshness_score * 0.30
        + completeness_score * 0.20
        + balance_score * 0.20
        + quote_score * 0.15
        + depth_support_score * 0.15
    )


def _get_quality_label(score):
    if score >= 75:
        return 'высокая'
    if score >= 50:
        return 'средняя'
    return 'низкая'


def analyze_liquidity(
    symbol,
    reference_amount=500.0,
    benchmark_amounts=DEFAULT_BENCHMARK_AMOUNTS,
):
    profiles, error_message = load_liquidity_profiles(symbol)
    if error_message:
        return None, error_message

    normalized_amounts = [
        float(amount)
        for amount in benchmark_amounts
        if _safe_float(amount) > 0
    ]
    if not normalized_amounts:
        normalized_amounts = list(DEFAULT_BENCHMARK_AMOUNTS)

    reference_amount = _safe_float(reference_amount, 500.0)
    if reference_amount <= 0:
        reference_amount = 500.0

    exchange_scores = []
    entry_results = []
    exit_results = []
    max_benchmark_amount = max(normalized_amounts)

    for exchange_name, profile in profiles.items():
        if not profile:
            exchange_scores.append({
                'exchange_name': exchange_name,
                'available': False,
                'liquidity_score': 0.0,
                'execution_quality': 'низкая',
                'spread_pct': 0.0,
                'depth_usdt': 0.0,
                'avg_buy_slippage_pct': 0.0,
                'avg_sell_slippage_pct': 0.0,
                'fee_pct': 0.0,
                'min_order_usdt': 0.0,
                'stability_score': 0.0,
                'level_completeness': 0,
            })
            continue

        buy_benchmarks = [
            simulate_buy(profile['ask_levels'], amount)
            for amount in normalized_amounts
        ]
        sell_benchmarks = [
            simulate_sell(profile['bid_levels'], amount)
            for amount in normalized_amounts
        ]
        buy_reference = simulate_buy(profile['ask_levels'], reference_amount)
        sell_reference = simulate_sell(profile['bid_levels'], reference_amount)
        buy_reference['exchange_name'] = exchange_name
        sell_reference['exchange_name'] = exchange_name
        entry_results.append(buy_reference)
        exit_results.append(sell_reference)

        average_buy_slippage = (
            sum(item.get('slippage_pct', 0.0) for item in buy_benchmarks)
            / len(buy_benchmarks)
        )
        average_sell_slippage = (
            sum(item.get('slippage_pct', 0.0) for item in sell_benchmarks)
            / len(sell_benchmarks)
        )
        fill_ratio = (
            sum(item.get('coverage', 0.0) for item in buy_benchmarks + sell_benchmarks)
            / max(len(buy_benchmarks + sell_benchmarks), 1)
        )

        ask_depth = sum(price * volume for price, volume in profile['ask_levels'])
        bid_depth = sum(price * volume for price, volume in profile['bid_levels'])
        average_depth = (ask_depth + bid_depth) / 2.0
        fee_pct = profile.get('taker_fee', 0.0) * 100.0
        min_order_usdt = profile.get('min_order_amount', 0.0) * (
            profile.get('current_price') or profile.get('mid_price') or 0.0
        )
        level_completeness = min(
            len(profile.get('ask_levels') or []),
            len(profile.get('bid_levels') or []),
        )

        spread_score = _metric_score_lower_is_better(
            profile.get('spread_pct', 0.0),
            good=0.04,
            bad=1.00,
        )
        slippage_score = _metric_score_lower_is_better(
            (average_buy_slippage + average_sell_slippage) / 2.0,
            good=0.02,
            bad=1.20,
        ) * fill_ratio
        depth_score = _metric_score_higher_is_better(
            average_depth,
            bad=max_benchmark_amount,
            good=max_benchmark_amount * 6.0,
        )
        fee_score = _metric_score_lower_is_better(
            fee_pct,
            good=0.05,
            bad=0.45,
        )
        min_order_score = _metric_score_lower_is_better(
            min_order_usdt,
            good=1.0,
            bad=50.0,
        )
        stability_score = _calculate_stability_score(profile, max_benchmark_amount)

        liquidity_score = (
            spread_score * 0.18
            + slippage_score * 0.28
            + depth_score * 0.22
            + fee_score * 0.10
            + min_order_score * 0.08
            + stability_score * 0.14
        )

        exchange_scores.append({
            'exchange_name': exchange_name,
            'available': True,
            'liquidity_score': round(liquidity_score, 2),
            'execution_quality': _get_quality_label(liquidity_score),
            'spread_pct': round(profile.get('spread_pct', 0.0), 4),
            'depth_usdt': round(average_depth, 2),
            'avg_buy_slippage_pct': round(average_buy_slippage, 4),
            'avg_sell_slippage_pct': round(average_sell_slippage, 4),
            'fee_pct': round(fee_pct, 4),
            'min_order_usdt': round(min_order_usdt, 4),
            'stability_score': round(stability_score, 2),
            'level_completeness': level_completeness,
            'reference_buy': buy_reference,
            'reference_sell': sell_reference,
            'profile': profile,
        })

    available_scores = [item for item in exchange_scores if item.get('available')]
    best_entry = select_best_result(entry_results, 'buy')
    best_exit = select_best_result(exit_results, 'sell')

    if available_scores:
        ranked_scores = sorted(
            available_scores,
            key=lambda item: item['liquidity_score'],
            reverse=True,
        )
        best_score = ranked_scores[0]['liquidity_score']
        average_score = sum(
            item['liquidity_score'] for item in available_scores
        ) / len(available_scores)
        overall_score = round(best_score * 0.55 + average_score * 0.45, 2)
    else:
        ranked_scores = []
        overall_score = 0.0

    result = {
        'symbol': symbol,
        'benchmark_amounts': normalized_amounts,
        'reference_amount': reference_amount,
        'overall_score': overall_score,
        'overall_quality': _get_quality_label(overall_score),
        'best_entry_exchange': (
            best_entry.get('exchange_name') if best_entry else None
        ),
        'best_exit_exchange': (
            best_exit.get('exchange_name') if best_exit else None
        ),
        'best_entry_result': best_entry,
        'best_exit_result': best_exit,
        'exchange_scores': exchange_scores,
        'ranked_scores': ranked_scores,
    }
    return result, None
