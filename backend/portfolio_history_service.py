import logging
from datetime import datetime, timedelta

from backend.models import PortfolioHistory, session

logger = logging.getLogger(__name__)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def store_portfolio_snapshot(
    user_id: int,
    portfolio_data: dict,
    min_interval_minutes: int = 30,
    min_change_ratio: float = 0.003,
) -> bool:
    """Сохраняет снимок портфеля в историю, если прошло достаточно времени
    или стоимость заметно изменилась.
    """
    if not user_id or not portfolio_data:
        return False

    total_value = _safe_float(portfolio_data.get("total_usd"))
    exchanges = portfolio_data.get("exchanges") or {}

    bybit_value = _safe_float((exchanges.get("bybit") or {}).get("total_usd"))
    gateio_value = _safe_float((exchanges.get("gateio") or {}).get("total_usd"))
    mexc_value = _safe_float((exchanges.get("mexc") or {}).get("total_usd"))

    now = datetime.now()

    try:
        latest = (
            session.query(PortfolioHistory)
            .filter(PortfolioHistory.user_id == user_id)
            .order_by(PortfolioHistory.timestamp.desc())
            .first()
        )

        if latest is not None:
            latest_total = _safe_float(latest.total_value_usd)
            latest_time = latest.timestamp or now
            age = now - latest_time
            if latest_total > 0:
                change_ratio = abs(total_value - latest_total) / latest_total
            else:
                change_ratio = 1.0 if total_value > 0 else 0.0

            if (
                age < timedelta(minutes=min_interval_minutes)
                and change_ratio < min_change_ratio
            ):
                return False

        session.add(
            PortfolioHistory(
                user_id=user_id,
                timestamp=now,
                total_value_usd=total_value,
                bybit_value=bybit_value,
                gateio_value=gateio_value,
                mexc_value=mexc_value,
            )
        )
        session.commit()
        logger.info(
            "[PORTFOLIO HISTORY] Snapshot stored user=%s total=$%.2f",
            user_id,
            total_value,
        )
        return True
    except Exception as exc:
        session.rollback()
        logger.error(
            "[PORTFOLIO HISTORY] Failed to store snapshot: %s",
            str(exc)[:160],
        )
        return False
