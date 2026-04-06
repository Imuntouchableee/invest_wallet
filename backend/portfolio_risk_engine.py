"""
Продвинутый анализатор риск-метрик портфеля.

Считает классические показатели устойчивости и advanced risk metrics:
- Historical VaR 95%
- Sharpe Ratio
- Sortino Ratio
- Max Drawdown
- Calmar Ratio
"""
import ast
import logging
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from backend.models import PortfolioHistory, session
from data.database import DatabaseManager

logger = logging.getLogger(__name__)

STABLE_ASSETS = {"USDT", "USDC", "USD", "BUSD", "DAI", "TUSD"}
SUPPORTED_EXCHANGES = ("bybit", "gateio", "mexc")
DEFAULT_ANNUAL_RISK_FREE_RATE = 0.02


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _safe_div(numerator, denominator, default=0.0):
    denominator_value = _safe_float(denominator)
    if abs(denominator_value) < 1e-12:
        return default
    return _safe_float(numerator) / denominator_value


def _normalize_exchange_name(value) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "gate.io": "gateio",
        "gate_io": "gateio",
        "gate-io": "gateio",
    }
    return aliases.get(raw, raw)


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return _safe_float(values[0])

    ordered = sorted(_safe_float(v) for v in values)
    position = (len(ordered) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _annualized_cagr(
    starting_value: float,
    ending_value: float,
    start_ts: Optional[datetime],
    end_ts: Optional[datetime],
) -> float:
    start_value = _safe_float(starting_value)
    end_value = _safe_float(ending_value)
    if start_value <= 0 or end_value <= 0 or not start_ts or not end_ts:
        return 0.0

    elapsed_seconds = max((end_ts - start_ts).total_seconds(), 0.0)
    if elapsed_seconds <= 0:
        return 0.0

    years = elapsed_seconds / (365.0 * 24.0 * 3600.0)
    if years <= 0:
        return 0.0

    try:
        return (end_value / start_value) ** (1 / years) - 1
    except Exception:
        return 0.0


class PortfolioRiskAnalyzer:
    def __init__(
        self,
        user_id: int,
        annual_risk_free_rate: float = DEFAULT_ANNUAL_RISK_FREE_RATE,
    ):
        self.user_id = user_id
        self.annual_risk_free_rate = annual_risk_free_rate
        self.portfolio_history = self._get_portfolio_history(days=90)

    def _normalize_portfolio_data(self, raw_portfolio: Dict) -> Dict:
        if "assets" in raw_portfolio and "by_exchange" in raw_portfolio:
            return raw_portfolio

        if "all_assets" in raw_portfolio and "exchanges" in raw_portfolio:
            by_exchange = {}
            for exchange_name, exchange_data in (raw_portfolio.get("exchanges") or {}).items():
                by_exchange[_normalize_exchange_name(exchange_name)] = _safe_float(
                    (exchange_data or {}).get("total_usd")
                )

            return {
                "assets": raw_portfolio.get("all_assets", []),
                "by_exchange": by_exchange,
                "total_usd": _safe_float(raw_portfolio.get("total_usd")),
            }

        return raw_portfolio or {}

    def _get_portfolio_history(self, days: int = 90) -> List[PortfolioHistory]:
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            return (
                session.query(PortfolioHistory)
                .filter(
                    PortfolioHistory.user_id == self.user_id,
                    PortfolioHistory.timestamp >= cutoff_date,
                )
                .order_by(PortfolioHistory.timestamp)
                .all()
            )
        except Exception as exc:
            logger.error("[RISK ENGINE] Failed to load history: %s", str(exc)[:160])
            return []

    def _build_db_history_series(self) -> List[Dict]:
        points = []
        for row in self.portfolio_history:
            total_value = _safe_float(row.total_value_usd)
            if total_value <= 0:
                continue
            points.append(
                {
                    "timestamp": row.timestamp,
                    "total_value_usd": total_value,
                    "bybit_value": _safe_float(row.bybit_value),
                    "gateio_value": _safe_float(row.gateio_value),
                    "mexc_value": _safe_float(row.mexc_value),
                    "source": "portfolio_history",
                }
            )
        return points

    def _append_current_snapshot(
        self,
        points: List[Dict],
        normalized_portfolio: Dict,
        source_name: str,
    ) -> List[Dict]:
        current_total = _safe_float(normalized_portfolio.get("total_usd"))
        if current_total <= 0:
            return points

        by_exchange = normalized_portfolio.get("by_exchange") or {}
        now = datetime.now()
        latest = points[-1] if points else None
        if latest:
            latest_total = _safe_float(latest.get("total_value_usd"))
            latest_ts = latest.get("timestamp") or now
            if (
                abs(current_total - latest_total) < 1e-6
                and abs((now - latest_ts).total_seconds()) < 300
            ):
                return points

        points.append(
            {
                "timestamp": now,
                "total_value_usd": current_total,
                "bybit_value": _safe_float(by_exchange.get("bybit")),
                "gateio_value": _safe_float(by_exchange.get("gateio")),
                "mexc_value": _safe_float(by_exchange.get("mexc")),
                "source": source_name,
            }
        )
        return points

    def _parse_quotes_history(self, raw_quotes) -> List[float]:
        if not raw_quotes:
            return []
        if isinstance(raw_quotes, list):
            return [_safe_float(item) for item in raw_quotes if _safe_float(item) > 0]
        if isinstance(raw_quotes, str):
            try:
                parsed = ast.literal_eval(raw_quotes)
                if isinstance(parsed, list):
                    return [_safe_float(item) for item in parsed if _safe_float(item) > 0]
            except Exception:
                return []
        return []

    def _find_asset_quote_series(
        self,
        db: DatabaseManager,
        currency: str,
        preferred_exchange: str,
        fallback_price: float,
    ) -> List[float]:
        if currency.upper() in STABLE_ASSETS:
            return [1.0] * 12

        symbol = f"{currency.upper()}/USDT"
        search_order = []
        preferred = _normalize_exchange_name(preferred_exchange)
        if preferred:
            search_order.append(preferred)
        search_order.extend(
            exchange for exchange in SUPPORTED_EXCHANGES if exchange not in search_order
        )

        for exchange_name in search_order:
            pair_info = db.get_pair_info(exchange_name, symbol)
            quotes = self._parse_quotes_history((pair_info or {}).get("quotes_1h"))
            if len(quotes) >= 2:
                return quotes

        if fallback_price > 0:
            return [fallback_price] * 12
        return []

    def _build_quote_reconstruction_series(self, normalized_portfolio: Dict) -> List[Dict]:
        assets = normalized_portfolio.get("assets") or []
        if not assets:
            return []

        db = DatabaseManager()
        if not db.connect():
            return []

        try:
            per_asset_series = []
            for asset in assets:
                amount = _safe_float(asset.get("amount"))
                if amount <= 0:
                    continue

                currency = str(asset.get("currency", "")).upper()
                exchange_name = _normalize_exchange_name(asset.get("exchange"))
                price_fallback = _safe_float(asset.get("price_usd"))
                quotes = self._find_asset_quote_series(
                    db,
                    currency,
                    exchange_name,
                    price_fallback,
                )
                if len(quotes) < 2:
                    continue

                per_asset_series.append(
                    {
                        "exchange": exchange_name,
                        "amount": amount,
                        "quotes": quotes,
                    }
                )

            if not per_asset_series:
                return []

            min_length = min(len(item["quotes"]) for item in per_asset_series)
            if min_length < 2:
                return []

            now = datetime.now()
            points = []
            for idx in range(min_length):
                total_value = 0.0
                by_exchange = {
                    "bybit_value": 0.0,
                    "gateio_value": 0.0,
                    "mexc_value": 0.0,
                }

                for item in per_asset_series:
                    quote_value = _safe_float(item["quotes"][-min_length + idx])
                    asset_value = item["amount"] * quote_value
                    total_value += asset_value
                    exchange_name = item["exchange"]
                    if exchange_name == "bybit":
                        by_exchange["bybit_value"] += asset_value
                    elif exchange_name == "gateio":
                        by_exchange["gateio_value"] += asset_value
                    elif exchange_name == "mexc":
                        by_exchange["mexc_value"] += asset_value

                timestamp = now - timedelta(hours=(min_length - 1 - idx))
                points.append(
                    {
                        "timestamp": timestamp,
                        "total_value_usd": total_value,
                        "source": "quote_reconstruction",
                        **by_exchange,
                    }
                )
            return points
        finally:
            db.close()

    def _select_history_series(self, normalized_portfolio: Dict) -> Tuple[List[Dict], Dict]:
        db_points = self._append_current_snapshot(
            self._build_db_history_series(),
            normalized_portfolio,
            "portfolio_history",
        )
        if len(db_points) >= 8:
            return db_points, {
                "source": "portfolio_history",
                "source_label": "Live portfolio snapshots",
            }

        quote_points = self._build_quote_reconstruction_series(normalized_portfolio)
        if len(quote_points) >= 8:
            return quote_points, {
                "source": "quote_reconstruction",
                "source_label": "Hourly quote reconstruction",
            }

        if db_points:
            return db_points, {
                "source": "portfolio_history",
                "source_label": "Live portfolio snapshots",
            }

        return quote_points, {
            "source": "quote_reconstruction",
            "source_label": "Hourly quote reconstruction",
        }

    def _infer_period_metadata(self, timestamps: List[datetime]) -> Dict:
        if len(timestamps) < 2:
            return {
                "interval_hours": 24.0,
                "periods_per_year": 365.0,
                "interval_label": "1D",
            }

        deltas = []
        for idx in range(1, len(timestamps)):
            delta_seconds = max((timestamps[idx] - timestamps[idx - 1]).total_seconds(), 0.0)
            if delta_seconds > 0:
                deltas.append(delta_seconds)

        if not deltas:
            return {
                "interval_hours": 24.0,
                "periods_per_year": 365.0,
                "interval_label": "1D",
            }

        median_seconds = statistics.median(deltas)
        interval_hours = max(median_seconds / 3600.0, 1 / 60.0)
        periods_per_year = (365.0 * 24.0) / interval_hours

        if interval_hours >= 24:
            interval_label = f"{max(1, round(interval_hours / 24))}D"
        else:
            interval_label = f"{max(1, round(interval_hours))}H"

        return {
            "interval_hours": interval_hours,
            "periods_per_year": periods_per_year,
            "interval_label": interval_label,
        }

    def calculate_concentration_risk(self, portfolio_data: Dict) -> Dict:
        assets = portfolio_data.get("assets", [])
        if not assets:
            return {"risk_level": "LOW", "score": 100.0, "description": "Нет данных"}

        aggregated_assets = {}
        total_value = 0.0
        for asset in assets:
            value_usd = _safe_float(asset.get("value_usd"))
            if value_usd <= 0:
                continue
            asset_name = str(asset.get("currency", "")).upper() or "UNKNOWN"
            total_value += value_usd
            aggregated_assets.setdefault(
                asset_name,
                {"name": asset_name, "value": 0.0},
            )
            aggregated_assets[asset_name]["value"] += value_usd

        if total_value <= 0:
            return {"risk_level": "LOW", "score": 100.0, "description": "Портфель пуст"}

        asset_distribution = []
        for asset_name, payload in aggregated_assets.items():
            value_usd = _safe_float(payload.get("value"))
            asset_distribution.append(
                {
                    "name": asset_name,
                    "percentage": _safe_div(value_usd * 100.0, total_value),
                    "value": round(value_usd, 2),
                }
            )
        asset_distribution.sort(key=lambda item: item["percentage"], reverse=True)

        largest = asset_distribution[0]["percentage"] if asset_distribution else 0.0
        top3 = sum(item["percentage"] for item in asset_distribution[:3])

        if largest > 50:
            risk_level = "CRITICAL"
            score = max(0.0, 100.0 - (largest - 50.0) * 2.2)
            description = (
                f"Критическая концентрация: {largest:.1f}% в {asset_distribution[0]['name']}"
            )
        elif largest > 30:
            risk_level = "HIGH"
            score = max(25.0, 100.0 - (largest - 30.0) * 1.6)
            description = (
                f"Высокая концентрация: {largest:.1f}% в {asset_distribution[0]['name']}"
            )
        elif top3 > 70:
            risk_level = "MEDIUM"
            score = max(45.0, 100.0 - (top3 - 70.0) * 0.8)
            description = f"Топ-3 актива занимают {top3:.1f}% портфеля"
        else:
            risk_level = "LOW"
            score = 87.0
            description = "Концентрация портфеля находится в норме"

        return {
            "risk_level": risk_level,
            "score": round(score, 2),
            "description": description,
            "largest_asset": asset_distribution[0] if asset_distribution else None,
            "top3_percentage": round(top3, 2),
            "total_assets": len(asset_distribution),
            "asset_distribution": asset_distribution[:8],
        }

    def calculate_exchange_dependency(self, portfolio_data: Dict) -> Dict:
        by_exchange = portfolio_data.get("by_exchange", {})
        if not by_exchange:
            return {
                "risk_level": "MEDIUM",
                "score": 50.0,
                "description": "Нет данных по биржам",
                "exchanges": [],
            }

        exchange_distribution = []
        total_value = sum(_safe_float(value) for value in by_exchange.values())
        if total_value <= 0:
            return {"risk_level": "LOW", "score": 100.0, "description": "Портфель пуст"}

        for exchange_name, value in by_exchange.items():
            value_usd = _safe_float(value)
            exchange_distribution.append(
                {
                    "exchange": _normalize_exchange_name(exchange_name),
                    "percentage": _safe_div(value_usd * 100.0, total_value),
                    "value": value_usd,
                }
            )
        exchange_distribution.sort(key=lambda item: item["percentage"], reverse=True)

        largest_exchange = exchange_distribution[0] if exchange_distribution else None
        largest_pct = largest_exchange["percentage"] if largest_exchange else 0.0

        if largest_pct > 85:
            risk_level = "CRITICAL"
            score = max(0.0, 100.0 - (largest_pct - 85.0) * 2.2)
            description = (
                f"Критическая зависимость: {largest_pct:.1f}% на {largest_exchange['exchange']}"
            )
        elif largest_pct > 70:
            risk_level = "HIGH"
            score = max(20.0, 100.0 - (largest_pct - 70.0) * 1.7)
            description = f"Высокая зависимость от {largest_exchange['exchange']}"
        elif largest_pct > 50:
            risk_level = "MEDIUM"
            score = max(45.0, 100.0 - (largest_pct - 50.0) * 1.2)
            description = f"Умеренная зависимость: {largest_pct:.1f}% на одной бирже"
        else:
            risk_level = "LOW"
            score = 90.0
            description = "Средства распределены между биржами нормально"

        return {
            "risk_level": risk_level,
            "score": round(score, 2),
            "description": description,
            "exchanges": exchange_distribution,
            "largest_exchange": largest_exchange,
        }

    def calculate_volatility_risk(self, returns: Optional[List[float]] = None) -> Dict:
        returns = returns or []
        if len(returns) < 2:
            return {
                "risk_level": "UNKNOWN",
                "score": 50.0,
                "description": "Недостаточно данных для оценки волатильности",
                "days_tracked": len(returns),
                "volatility": 0.0,
            }

        volatility = statistics.stdev(returns)
        avg_change = statistics.mean(returns)
        volatility_pct = volatility * 100.0

        if volatility_pct > 5.0:
            risk_level = "HIGH"
            score = max(20.0, 100.0 - volatility_pct * 6.5)
        elif volatility_pct > 2.0:
            risk_level = "MEDIUM"
            score = max(45.0, 100.0 - volatility_pct * 10.0)
        else:
            risk_level = "LOW"
            score = 88.0

        return {
            "risk_level": risk_level,
            "score": round(score, 2),
            "description": f"Волатильность доходностей: {volatility_pct:.2f}%",
            "volatility": round(volatility_pct, 4),
            "avg_period_return": round(avg_change * 100.0, 4),
            "max_change": round(max(returns) * 100.0, 4),
            "min_change": round(min(returns) * 100.0, 4),
            "days_tracked": len(returns),
        }

    def calculate_stablecoin_ratio(self, portfolio_data: Dict) -> Dict:
        assets = portfolio_data.get("assets", [])
        total_value = sum(_safe_float(asset.get("value_usd")) for asset in assets)
        if total_value <= 0:
            return {
                "risk_level": "NEUTRAL",
                "score": 50.0,
                "description": "Портфель пуст",
                "stablecoin_percentage": 0.0,
            }

        stable_value = sum(
            _safe_float(asset.get("value_usd"))
            for asset in assets
            if str(asset.get("currency", "")).upper() in STABLE_ASSETS
        )
        stable_pct = _safe_div(stable_value * 100.0, total_value)

        if stable_pct > 80:
            risk_level = "SAFE_BUT_CONSERVATIVE"
            score = 70.0
            description = f"Высокая доля стейблкоинов: {stable_pct:.1f}%"
        elif stable_pct > 50:
            risk_level = "MODERATE"
            score = 76.0
            description = f"Значительная доля стейблкоинов: {stable_pct:.1f}%"
        elif stable_pct > 20:
            risk_level = "BALANCED"
            score = 82.0
            description = f"Баланс риска и резерва: {stable_pct:.1f}% в стейблкоинах"
        else:
            risk_level = "AGGRESSIVE"
            score = 60.0
            description = f"Минимальная доля стейблкоинов: {stable_pct:.1f}%"

        return {
            "risk_level": risk_level,
            "score": score,
            "description": description,
            "stablecoin_percentage": round(stable_pct, 2),
            "stablecoin_value": round(stable_value, 2),
            "risky_assets_percentage": round(100.0 - stable_pct, 2),
        }

    def calculate_liquidity_risk(self, portfolio_data: Dict) -> Dict:
        assets = portfolio_data.get("assets", [])
        total_value = sum(_safe_float(asset.get("value_usd")) for asset in assets)
        if total_value <= 0:
            return {
                "risk_level": "NEUTRAL",
                "score": 50.0,
                "description": "Портфель пуст",
                "low_liquidity_percentage": 0.0,
            }

        illiquid_value = sum(
            _safe_float(asset.get("value_usd"))
            for asset in assets
            if _safe_float(asset.get("value_usd")) < 100.0
        )
        illiquid_pct = _safe_div(illiquid_value * 100.0, total_value)
        small_positions_count = sum(
            1 for asset in assets if _safe_float(asset.get("value_usd")) < 100.0
        )

        if illiquid_pct > 40:
            risk_level = "HIGH"
            score = max(15.0, 100.0 - illiquid_pct * 1.6)
            description = f"Высокая доля малых позиций: {illiquid_pct:.1f}%"
        elif illiquid_pct > 20:
            risk_level = "MEDIUM"
            score = max(45.0, 100.0 - illiquid_pct * 1.4)
            description = f"Умеренный риск ликвидности: {illiquid_pct:.1f}%"
        else:
            risk_level = "LOW"
            score = 86.0
            description = "Основная часть портфеля остается ликвидной"

        return {
            "risk_level": risk_level,
            "score": round(score, 2),
            "description": description,
            "low_liquidity_percentage": round(illiquid_pct, 2),
            "small_positions_count": small_positions_count,
            "illiquid_value": round(illiquid_value, 2),
        }

    def calculate_advanced_risk_metrics(self, portfolio_data: Dict) -> Dict:
        normalized_portfolio = self._normalize_portfolio_data(portfolio_data)
        history_points, history_meta = self._select_history_series(normalized_portfolio)

        if len(history_points) < 3:
            return {
                "history_ready": False,
                "history_points": len(history_points),
                "source": history_meta.get("source"),
                "source_label": history_meta.get("source_label"),
                "var_95_abs": 0.0,
                "var_95_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "calmar_ratio": 0.0,
                "annualized_return_pct": 0.0,
                "annualized_volatility_pct": 0.0,
                "win_rate_pct": 0.0,
                "interval_label": "N/A",
                "risk_free_rate_annual": self.annual_risk_free_rate,
                "history_window_label": "Недостаточно истории",
                "history_points_series": history_points,
                "returns_series": [],
                "drawdown_series": [],
            }

        timestamps = [point["timestamp"] for point in history_points]
        values = [_safe_float(point["total_value_usd"]) for point in history_points]
        period_meta = self._infer_period_metadata(timestamps)
        periods_per_year = max(period_meta["periods_per_year"], 1.0)
        period_rf = (1 + self.annual_risk_free_rate) ** (1 / periods_per_year) - 1

        returns_series = []
        raw_returns = []
        for idx in range(1, len(history_points)):
            prev_value = values[idx - 1]
            curr_value = values[idx]
            if prev_value <= 0:
                continue
            period_return = curr_value / prev_value - 1
            raw_returns.append(period_return)
            returns_series.append(
                {
                    "timestamp": timestamps[idx],
                    "return": period_return,
                    "return_pct": period_return * 100.0,
                }
            )

        running_max = 0.0
        drawdown_series = []
        drawdowns = []
        for idx, value in enumerate(values):
            running_max = max(running_max, value)
            drawdown = _safe_div(value, running_max, 1.0) - 1.0 if running_max > 0 else 0.0
            drawdowns.append(drawdown)
            drawdown_series.append(
                {
                    "timestamp": timestamps[idx],
                    "drawdown": drawdown,
                    "drawdown_pct": drawdown * 100.0,
                }
            )

        if not raw_returns:
            raw_returns = [0.0]

        mean_return = statistics.mean(raw_returns)
        return_stdev = statistics.stdev(raw_returns) if len(raw_returns) > 1 else 0.0
        downside_diffs = [min(period_return - period_rf, 0.0) for period_return in raw_returns]
        downside_deviation = math.sqrt(
            sum(diff * diff for diff in downside_diffs) / max(len(downside_diffs), 1)
        )

        mean_excess_return = mean_return - period_rf
        sharpe_ratio = (
            (mean_excess_return / return_stdev) * math.sqrt(periods_per_year)
            if return_stdev > 0
            else 0.0
        )
        sortino_ratio = (
            (mean_excess_return / downside_deviation) * math.sqrt(periods_per_year)
            if downside_deviation > 0
            else 0.0
        )

        var_95_pct = max(0.0, -_percentile(raw_returns, 0.05))
        current_value = values[-1] if values else 0.0
        var_95_abs = current_value * var_95_pct
        max_drawdown_pct = abs(min(drawdowns)) if drawdowns else 0.0
        annualized_return = _annualized_cagr(values[0], values[-1], timestamps[0], timestamps[-1])
        annualized_volatility = return_stdev * math.sqrt(periods_per_year)
        calmar_ratio = (
            annualized_return / max_drawdown_pct
            if max_drawdown_pct > 1e-12
            else 0.0
        )
        win_rate_pct = _safe_div(
            sum(1 for value in raw_returns if value > 0) * 100.0,
            len(raw_returns),
        )

        history_duration = timestamps[-1] - timestamps[0]
        if history_duration.days >= 1:
            history_window_label = f"{history_duration.days + 1} дн. истории"
        else:
            history_window_label = (
                f"{max(1, round(history_duration.total_seconds() / 3600))} ч. истории"
            )

        return {
            "history_ready": True,
            "history_points": len(history_points),
            "returns_count": len(raw_returns),
            "source": history_meta.get("source"),
            "source_label": history_meta.get("source_label"),
            "interval_label": period_meta["interval_label"],
            "interval_hours": round(period_meta["interval_hours"], 2),
            "periods_per_year": round(periods_per_year, 2),
            "risk_free_rate_annual": self.annual_risk_free_rate,
            "history_window_label": history_window_label,
            "var_95_abs": round(var_95_abs, 2),
            "var_95_pct": round(var_95_pct * 100.0, 2),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "sortino_ratio": round(sortino_ratio, 3),
            "max_drawdown_pct": round(max_drawdown_pct * 100.0, 2),
            "calmar_ratio": round(calmar_ratio, 3),
            "annualized_return_pct": round(annualized_return * 100.0, 2),
            "annualized_volatility_pct": round(annualized_volatility * 100.0, 2),
            "mean_period_return_pct": round(mean_return * 100.0, 4),
            "best_period_return_pct": round(max(raw_returns) * 100.0, 2),
            "worst_period_return_pct": round(min(raw_returns) * 100.0, 2),
            "win_rate_pct": round(win_rate_pct, 2),
            "history_points_series": history_points,
            "returns_series": returns_series,
            "drawdown_series": drawdown_series,
        }

    def _score_advanced_metrics(self, advanced_metrics: Dict) -> Dict:
        if not advanced_metrics.get("history_ready"):
            return {
                "advanced_score": 50.0,
                "var_score": 50.0,
                "sharpe_score": 50.0,
                "drawdown_score": 50.0,
                "calmar_score": 50.0,
            }

        var_pct = _safe_float(advanced_metrics.get("var_95_pct"))
        sharpe = _safe_float(advanced_metrics.get("sharpe_ratio"))
        sortino = _safe_float(advanced_metrics.get("sortino_ratio"))
        max_drawdown = _safe_float(advanced_metrics.get("max_drawdown_pct"))
        calmar = _safe_float(advanced_metrics.get("calmar_ratio"))

        var_score = max(0.0, 100.0 - var_pct * 4.0)
        drawdown_score = max(0.0, 100.0 - max_drawdown * 3.2)
        sharpe_score = max(0.0, min(100.0, 55.0 + sharpe * 18.0))
        sortino_score = max(0.0, min(100.0, 55.0 + sortino * 14.0))
        calmar_score = max(0.0, min(100.0, 50.0 + calmar * 20.0))

        advanced_score = statistics.mean(
            [var_score, drawdown_score, sharpe_score, sortino_score, calmar_score]
        )
        return {
            "advanced_score": round(advanced_score, 2),
            "var_score": round(var_score, 2),
            "sharpe_score": round((sharpe_score + sortino_score) / 2.0, 2),
            "drawdown_score": round(drawdown_score, 2),
            "calmar_score": round(calmar_score, 2),
        }

    def _identify_main_risk(
        self,
        concentration: Dict,
        exchange_dep: Dict,
        volatility: Dict,
        liquidity: Dict,
        advanced_metrics: Dict,
    ) -> Dict:
        risk_candidates = [
            ("Концентрация", concentration.get("score", 0.0), concentration.get("description")),
            ("Зависимость от биржи", exchange_dep.get("score", 0.0), exchange_dep.get("description")),
            ("Волатильность", volatility.get("score", 0.0), volatility.get("description")),
            ("Ликвидность", liquidity.get("score", 0.0), liquidity.get("description")),
        ]

        if advanced_metrics.get("history_ready"):
            risk_candidates.extend(
                [
                    (
                        "VaR 95%",
                        max(0.0, 100.0 - _safe_float(advanced_metrics.get("var_95_pct")) * 4.0),
                        f"Ожидаемый убыток 95%: {advanced_metrics.get('var_95_pct', 0.0):.2f}%",
                    ),
                    (
                        "Просадка",
                        max(0.0, 100.0 - _safe_float(advanced_metrics.get("max_drawdown_pct")) * 3.2),
                        f"Максимальная просадка: {advanced_metrics.get('max_drawdown_pct', 0.0):.2f}%",
                    ),
                ]
            )

        main_risk = min(risk_candidates, key=lambda item: item[1])
        return {
            "name": main_risk[0],
            "score": round(_safe_float(main_risk[1]), 2),
            "description": str(main_risk[2] or "Нет описания"),
        }

    def _get_recommendation(
        self,
        concentration: Dict,
        exchange_dep: Dict,
        volatility: Dict,
        stablecoin: Dict,
        liquidity: Dict,
        advanced_metrics: Dict,
    ) -> str:
        issues = []

        if concentration.get("risk_level") in {"CRITICAL", "HIGH"} and concentration.get("largest_asset"):
            issues.append(
                f"снизить концентрацию в {concentration['largest_asset']['name']}"
            )
        if exchange_dep.get("risk_level") in {"CRITICAL", "HIGH"}:
            issues.append("распределить средства между биржами")
        if volatility.get("risk_level") == "HIGH":
            issues.append("снизить долю самых волатильных позиций")
        if liquidity.get("risk_level") == "HIGH":
            issues.append("уменьшить долю малых и неликвидных позиций")
        if advanced_metrics.get("history_ready"):
            if _safe_float(advanced_metrics.get("max_drawdown_pct")) > 20:
                issues.append("ограничить потенциальную просадку через диверсификацию")
            if _safe_float(advanced_metrics.get("sharpe_ratio")) < 0.5:
                issues.append("повысить доходность на единицу риска")
            if _safe_float(advanced_metrics.get("var_95_pct")) > 5:
                issues.append("снизить однопериодный риск потерь")
        if stablecoin.get("risk_level") == "AGGRESSIVE":
            issues.append("добавить резерв в стейблкоинах")

        if not issues:
            return (
                "Портфель выглядит устойчиво: концентрация под контролем, "
                "а доходность компенсирует риск."
            )
        return "Фокус оптимизации: " + "; ".join(issues[:3])

    def calculate_overall_stability_score(self, portfolio_data: Dict) -> Dict:
        normalized_portfolio = self._normalize_portfolio_data(portfolio_data)
        advanced_metrics = self.calculate_advanced_risk_metrics(normalized_portfolio)

        raw_returns = [
            _safe_float(item.get("return"))
            for item in advanced_metrics.get("returns_series", [])
        ]

        concentration = self.calculate_concentration_risk(normalized_portfolio)
        exchange_dep = self.calculate_exchange_dependency(normalized_portfolio)
        volatility = self.calculate_volatility_risk(raw_returns)
        stablecoin = self.calculate_stablecoin_ratio(normalized_portfolio)
        liquidity = self.calculate_liquidity_risk(normalized_portfolio)
        advanced_scores = self._score_advanced_metrics(advanced_metrics)

        weights = {
            "concentration": 0.18,
            "exchange_dependency": 0.15,
            "volatility": 0.15,
            "stablecoin": 0.10,
            "liquidity": 0.12,
            "advanced": 0.30,
        }

        overall_score = (
            concentration["score"] * weights["concentration"]
            + exchange_dep["score"] * weights["exchange_dependency"]
            + volatility["score"] * weights["volatility"]
            + stablecoin["score"] * weights["stablecoin"]
            + liquidity["score"] * weights["liquidity"]
            + advanced_scores["advanced_score"] * weights["advanced"]
        )

        if overall_score >= 80:
            stability_level = "EXCELLENT"
            emoji = "🟢"
            regime_label = "Устойчивый"
        elif overall_score >= 65:
            stability_level = "GOOD"
            emoji = "🟡"
            regime_label = "Контролируемый"
        elif overall_score >= 50:
            stability_level = "MODERATE"
            emoji = "🟠"
            regime_label = "Напряженный"
        else:
            stability_level = "POOR"
            emoji = "🔴"
            regime_label = "Агрессивный риск"

        return {
            "stability_score": round(overall_score, 1),
            "stability_level": stability_level,
            "emoji": emoji,
            "risk_regime": regime_label,
            "recommendation": self._get_recommendation(
                concentration,
                exchange_dep,
                volatility,
                stablecoin,
                liquidity,
                advanced_metrics,
            ),
            "main_risk": self._identify_main_risk(
                concentration,
                exchange_dep,
                volatility,
                liquidity,
                advanced_metrics,
            ),
            "advanced_scores": advanced_scores,
            "metrics": {
                "concentration": concentration,
                "exchange_dependency": exchange_dep,
                "volatility": volatility,
                "stablecoin": stablecoin,
                "liquidity": liquidity,
                "advanced": advanced_metrics,
            },
        }
