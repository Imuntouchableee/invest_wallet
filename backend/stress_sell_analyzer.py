from collections import defaultdict

from backend.liquidity_analyzer import load_liquidity_profiles, select_best_result, simulate_sell

STABLE_ASSETS = {'USDT', 'USDC', 'BUSD', 'DAI', 'USD'}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def analyze_portfolio_stress_sell(portfolio_data):
    portfolio_data = portfolio_data or {}
    all_assets = portfolio_data.get('all_assets') or []

    nominal_value = 0.0
    executable_value = 0.0
    asset_reports = []
    exchange_totals = defaultdict(float)

    for asset in all_assets:
        asset_name = str(asset.get('currency') or '').upper()
        if not asset_name:
            continue

        amount = _safe_float(asset.get('amount'))
        asset_value = _safe_float(asset.get('value_usd'))
        if amount <= 0 or asset_value <= 0:
            continue

        nominal_value += asset_value

        if asset_name in STABLE_ASSETS:
            current_exchange = asset.get('exchange')
            executable_value += asset_value
            if current_exchange:
                exchange_totals[current_exchange] += asset_value
            asset_reports.append({
                'asset': asset_name,
                'nominal_value': asset_value,
                'executable_value': asset_value,
                'loss_usdt': 0.0,
                'loss_pct': 0.0,
                'best_exchange': current_exchange,
                'coverage': 1.0,
                'available': True,
            })
            continue

        symbol = f'{asset_name}/USDT'
        profiles, error_message = load_liquidity_profiles(symbol)
        best_result = None
        best_exchange = None

        if not error_message:
            results = []
            for exchange_name, profile in (profiles or {}).items():
                if not profile:
                    continue
                sell_result = simulate_sell(profile.get('bid_levels') or [], asset_value)
                sell_result['exchange_name'] = exchange_name
                results.append(sell_result)
            best_result = select_best_result(results, 'sell')
            if best_result:
                best_exchange = best_result.get('exchange_name')

        realized_value = 0.0
        coverage = 0.0
        if best_result and best_result.get('available'):
            realized_value = _safe_float(best_result.get('received_usdt'))
            coverage = _safe_float(best_result.get('coverage'))

        executable_value += realized_value
        if best_exchange:
            exchange_totals[best_exchange] += realized_value

        loss_usdt = max(asset_value - realized_value, 0.0)
        loss_pct = (loss_usdt / asset_value * 100.0) if asset_value > 0 else 0.0
        asset_reports.append({
            'asset': asset_name,
            'nominal_value': asset_value,
            'executable_value': realized_value,
            'loss_usdt': loss_usdt,
            'loss_pct': loss_pct,
            'best_exchange': best_exchange,
            'coverage': coverage,
            'available': bool(best_result and best_result.get('available')),
        })

    total_loss = max(nominal_value - executable_value, 0.0)
    loss_pct = (total_loss / nominal_value * 100.0) if nominal_value > 0 else 0.0
    sorted_losses = sorted(
        asset_reports,
        key=lambda item: item.get('loss_usdt', 0.0),
        reverse=True,
    )
    top_loss_assets = [
        item['asset']
        for item in sorted_losses
        if item.get('loss_usdt', 0.0) > 0.01
    ][:3]

    best_exit_exchange = None
    if exchange_totals:
        best_exit_exchange = max(exchange_totals.items(), key=lambda item: item[1])[0]

    illiquid_assets = [
        item['asset']
        for item in asset_reports
        if not item.get('available') or item.get('coverage', 0.0) < 0.99
    ]

    return {
        'nominal_value': nominal_value,
        'executable_value': executable_value,
        'liquidation_loss': total_loss,
        'liquidation_loss_pct': loss_pct,
        'top_loss_assets': top_loss_assets,
        'best_exit_exchange': best_exit_exchange,
        'asset_reports': asset_reports,
        'illiquid_assets': illiquid_assets,
        'exchange_totals': dict(exchange_totals),
    }
