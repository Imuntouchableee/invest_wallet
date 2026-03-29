import ast
from datetime import datetime, timedelta

from backend.liquidity_analyzer import analyze_liquidity, load_liquidity_profiles
from backend.models import TradeDecisionHistory, session

EXCHANGE_NAMES = {
    'bybit': 'Bybit',
    'gateio': 'Gate.io',
    'mexc': 'MEXC',
}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _simulate_buy_quantity(levels, target_qty):
    if not levels or target_qty <= 0:
        return {'available': False, 'filled': False, 'coverage': 0.0}

    remaining_qty = target_qty
    spent_usdt = 0.0
    acquired_qty = 0.0
    best_price = _safe_float(levels[0][0]) if levels else 0.0

    for price, volume in levels:
        price_value = _safe_float(price)
        volume_value = _safe_float(volume)
        if price_value <= 0 or volume_value <= 0 or remaining_qty <= 0:
            continue
        take_qty = min(remaining_qty, volume_value)
        spent_usdt += take_qty * price_value
        acquired_qty += take_qty
        remaining_qty -= take_qty

    avg_price = spent_usdt / acquired_qty if acquired_qty > 0 else 0.0
    coverage = acquired_qty / target_qty if target_qty > 0 else 0.0
    slippage_pct = ((avg_price / best_price) - 1) * 100 if best_price else 0.0
    return {
        'available': True,
        'filled': remaining_qty <= 1e-9,
        'coverage': min(max(coverage, 0.0), 1.0),
        'avg_price': avg_price,
        'best_price': best_price,
        'spent_usdt': spent_usdt,
        'executed_qty': acquired_qty,
        'slippage_pct': max(slippage_pct, 0.0),
    }


def _simulate_sell_quantity(levels, target_qty):
    if not levels or target_qty <= 0:
        return {'available': False, 'filled': False, 'coverage': 0.0}

    remaining_qty = target_qty
    received_usdt = 0.0
    sold_qty = 0.0
    best_price = _safe_float(levels[0][0]) if levels else 0.0

    for price, volume in levels:
        price_value = _safe_float(price)
        volume_value = _safe_float(volume)
        if price_value <= 0 or volume_value <= 0 or remaining_qty <= 0:
            continue
        take_qty = min(remaining_qty, volume_value)
        received_usdt += take_qty * price_value
        sold_qty += take_qty
        remaining_qty -= take_qty

    avg_price = received_usdt / sold_qty if sold_qty > 0 else 0.0
    coverage = sold_qty / target_qty if target_qty > 0 else 0.0
    slippage_pct = (1 - (avg_price / best_price)) * 100 if best_price else 0.0
    return {
        'available': True,
        'filled': remaining_qty <= 1e-9,
        'coverage': min(max(coverage, 0.0), 1.0),
        'avg_price': avg_price,
        'best_price': best_price,
        'received_usdt': received_usdt,
        'executed_qty': sold_qty,
        'slippage_pct': max(slippage_pct, 0.0),
    }


def _serialize_alternative_prices(exchange_results):
    snapshot = {}
    for exchange_name, result in exchange_results.items():
        snapshot[exchange_name] = {
            'avg_price': round(_safe_float(result.get('avg_price')), 8),
            'coverage': round(_safe_float(result.get('coverage')), 6),
            'filled': bool(result.get('filled')),
        }
    return str(snapshot)


def _parse_alternative_prices(raw_value):
    if not raw_value:
        return {}
    if isinstance(raw_value, dict):
        return raw_value
    try:
        parsed = ast.literal_eval(raw_value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def record_trade_decision(
    user_id,
    symbol,
    side,
    actual_exchange,
    amount,
    actual_price=0.0,
):
    if not user_id or not symbol or amount <= 0:
        return None

    profiles, error_message = load_liquidity_profiles(symbol)
    if error_message:
        return None

    exchange_results = {}
    for exchange_name, profile in (profiles or {}).items():
        if not profile:
            continue
        levels = profile.get('ask_levels') if side == 'buy' else profile.get('bid_levels')
        result = (
            _simulate_buy_quantity(levels or [], amount)
            if side == 'buy'
            else _simulate_sell_quantity(levels or [], amount)
        )
        if result.get('available'):
            exchange_results[exchange_name] = result

    if not exchange_results:
        return None

    if side == 'buy':
        best_exchange, best_result = min(
            exchange_results.items(),
            key=lambda item: (
                0 if item[1].get('filled') else 1,
                -item[1].get('coverage', 0.0),
                item[1].get('avg_price', float('inf')),
            ),
        )
    else:
        best_exchange, best_result = max(
            exchange_results.items(),
            key=lambda item: (
                1 if item[1].get('filled') else 0,
                item[1].get('coverage', 0.0),
                item[1].get('avg_price', 0.0),
            ),
        )

    chosen_result = exchange_results.get(actual_exchange)
    if chosen_result:
        actual_reference_price = _safe_float(actual_price) or _safe_float(
            chosen_result.get('avg_price')
        )
    else:
        actual_reference_price = _safe_float(actual_price)

    if chosen_result and best_result:
        if side == 'buy':
            actual_notional = chosen_result.get('spent_usdt', 0.0)
            best_notional = best_result.get('spent_usdt', 0.0)
            avoidable_loss = max(actual_notional - best_notional, 0.0)
        else:
            actual_notional = chosen_result.get('received_usdt', 0.0)
            best_notional = best_result.get('received_usdt', 0.0)
            avoidable_loss = max(best_notional - actual_notional, 0.0)
    else:
        actual_notional = amount * actual_reference_price
        best_notional = amount * _safe_float(best_result.get('avg_price'))
        avoidable_loss = max(abs(actual_notional - best_notional), 0.0)

    avoidable_loss_pct = (
        avoidable_loss / actual_notional * 100.0
        if actual_notional > 0
        else 0.0
    )

    liquidity_analysis, _ = analyze_liquidity(
        symbol,
        reference_amount=max(actual_notional, best_notional, 100.0),
    )
    ranked_scores = (liquidity_analysis or {}).get('ranked_scores') or []
    best_liquidity_exchange = (
        ranked_scores[0]['exchange_name'] if ranked_scores else None
    )
    chosen_liquidity_score = 0.0
    for score in (liquidity_analysis or {}).get('exchange_scores', []):
        if score.get('exchange_name') == actual_exchange:
            chosen_liquidity_score = _safe_float(score.get('liquidity_score'))
            break

    execution_quality_score = max(0.0, min(100.0, 100.0 - avoidable_loss_pct * 2.5))
    if chosen_result:
        execution_quality_score *= chosen_result.get('coverage', 0.0)
    if actual_exchange == best_exchange:
        execution_quality_score = max(execution_quality_score, 85.0)
    execution_quality_score = max(0.0, min(100.0, execution_quality_score))

    record = TradeDecisionHistory(
        user_id=user_id,
        symbol=symbol,
        side=side,
        actual_exchange=actual_exchange,
        actual_price=actual_reference_price,
        amount=_safe_float(amount),
        notional_usdt=_safe_float(actual_notional),
        best_exchange=best_exchange,
        best_possible_price=_safe_float(best_result.get('avg_price')),
        best_liquidity_exchange=best_liquidity_exchange,
        alternative_prices=_serialize_alternative_prices(exchange_results),
        avoidable_loss=_safe_float(avoidable_loss),
        avoidable_loss_pct=_safe_float(avoidable_loss_pct),
        execution_quality_score=_safe_float(execution_quality_score),
        liquidity_alignment_score=_safe_float(chosen_liquidity_score),
    )
    session.add(record)
    session.commit()
    return record


def get_user_decision_quality_summary(user_id, limit=100):
    if not user_id:
        return {
            'quality_score': 0.0,
            'avoidable_loss_total': 0.0,
            'avoidable_loss_month': 0.0,
            'worst_exchange': None,
            'worst_buy_exchange': None,
            'best_exchange': None,
            'best_price_pick_rate': 0.0,
            'liquidity_alignment_rate': 0.0,
            'suboptimal_rate': 0.0,
            'worst_side_label': 'Нет данных',
            'records_count': 0,
        }

    records = (
        session.query(TradeDecisionHistory)
        .filter_by(user_id=user_id)
        .order_by(TradeDecisionHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    if not records:
        return {
            'quality_score': 0.0,
            'avoidable_loss_total': 0.0,
            'avoidable_loss_month': 0.0,
            'worst_exchange': None,
            'worst_buy_exchange': None,
            'best_exchange': None,
            'best_price_pick_rate': 0.0,
            'liquidity_alignment_rate': 0.0,
            'suboptimal_rate': 0.0,
            'worst_side_label': 'История еще не накоплена',
            'records_count': 0,
        }

    total_score = sum(_safe_float(item.execution_quality_score) for item in records)
    total_loss = sum(_safe_float(item.avoidable_loss) for item in records)
    month_cutoff = datetime.now() - timedelta(days=30)
    monthly_loss = 0.0

    loss_by_exchange = {}
    buy_loss_by_exchange = {}
    score_by_exchange = {}
    count_by_exchange = {}
    side_counters = {'buy': 0, 'sell': 0}
    best_price_hits = 0
    liquidity_alignment_hits = 0
    suboptimal_count = 0

    for item in records:
        exchange_name = item.actual_exchange
        loss_value = _safe_float(item.avoidable_loss)
        loss_by_exchange[exchange_name] = (
            loss_by_exchange.get(exchange_name, 0.0) + loss_value
        )
        score_by_exchange[exchange_name] = (
            score_by_exchange.get(exchange_name, 0.0)
            + _safe_float(item.execution_quality_score)
        )
        count_by_exchange[exchange_name] = count_by_exchange.get(exchange_name, 0) + 1
        side_counters[item.side] = side_counters.get(item.side, 0) + 1
        if item.side == 'buy':
            buy_loss_by_exchange[exchange_name] = (
                buy_loss_by_exchange.get(exchange_name, 0.0) + loss_value
            )
        if item.created_at and item.created_at >= month_cutoff:
            monthly_loss += loss_value
        if item.actual_exchange == item.best_exchange:
            best_price_hits += 1
        if item.actual_exchange == item.best_liquidity_exchange:
            liquidity_alignment_hits += 1
        if loss_value > 0.01:
            suboptimal_count += 1

    worst_exchange = None
    if loss_by_exchange:
        worst_exchange = max(loss_by_exchange.items(), key=lambda item: item[1])[0]

    worst_buy_exchange = None
    if buy_loss_by_exchange:
        worst_buy_exchange = max(
            buy_loss_by_exchange.items(),
            key=lambda item: item[1],
        )[0]

    best_exchange = None
    if score_by_exchange:
        averages = {
            exchange_name: score_by_exchange[exchange_name] / count_by_exchange[exchange_name]
            for exchange_name in score_by_exchange
        }
        best_exchange = max(averages.items(), key=lambda item: item[1])[0]

    if side_counters.get('buy', 0) >= side_counters.get('sell', 0):
        worst_side_label = 'Чаще ошибается на покупках'
    else:
        worst_side_label = 'Чаще ошибается на продажах'

    return {
        'quality_score': round(total_score / len(records), 2),
        'avoidable_loss_total': round(total_loss, 2),
        'avoidable_loss_month': round(monthly_loss, 2),
        'worst_exchange': worst_exchange,
        'worst_buy_exchange': worst_buy_exchange,
        'best_exchange': best_exchange,
        'best_price_pick_rate': round(best_price_hits / len(records) * 100.0, 2),
        'liquidity_alignment_rate': round(
            liquidity_alignment_hits / len(records) * 100.0,
            2,
        ),
        'suboptimal_rate': round(suboptimal_count / len(records) * 100.0, 2),
        'worst_side_label': worst_side_label,
        'records_count': len(records),
    }


def get_user_trade_decision_history(user_id, limit=6):
    if not user_id:
        return []

    records = (
        session.query(TradeDecisionHistory)
        .filter_by(user_id=user_id)
        .order_by(TradeDecisionHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    history = []
    for item in records:
        alternatives = _parse_alternative_prices(item.alternative_prices)
        alternatives_count = len(alternatives)
        side_label = 'Покупка' if item.side == 'buy' else 'Продажа'
        history.append({
            'created_at': item.created_at,
            'symbol': item.symbol,
            'side': item.side,
            'side_label': side_label,
            'actual_exchange': format_exchange_name(item.actual_exchange),
            'best_exchange': format_exchange_name(item.best_exchange),
            'best_liquidity_exchange': format_exchange_name(
                item.best_liquidity_exchange
            ),
            'actual_price': round(_safe_float(item.actual_price), 8),
            'best_possible_price': round(_safe_float(item.best_possible_price), 8),
            'amount': round(_safe_float(item.amount), 8),
            'avoidable_loss': round(_safe_float(item.avoidable_loss), 4),
            'execution_quality_score': round(
                _safe_float(item.execution_quality_score),
                2,
            ),
            'liquidity_alignment_score': round(
                _safe_float(item.liquidity_alignment_score),
                2,
            ),
            'alternatives_count': alternatives_count,
            'status': (
                'Оптимально'
                if _safe_float(item.avoidable_loss) <= 0.01
                else 'Есть резерв'
            ),
        })
    return history


def format_exchange_name(exchange_name):
    if not exchange_name:
        return 'Нет данных'
    return EXCHANGE_NAMES.get(exchange_name, exchange_name.upper())
