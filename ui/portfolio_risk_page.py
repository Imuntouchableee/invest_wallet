"""
Профессиональная страница risk analytics портфеля.
"""
import base64
import io
import logging
import statistics

import flet as ft
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator

from backend.portfolio_history_service import store_portfolio_snapshot
from backend.portfolio_risk_engine import PortfolioRiskAnalyzer
from ui.config import (
    ACCENT_COLOR,
    BORDER_COLOR,
    CARD_BG,
    DARK_BG,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    SUCCESS_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
)

logger = logging.getLogger(__name__)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _format_money(value):
    return f"${_safe_float(value):,.2f}"


def _format_pct(value, digits=2):
    return f"{_safe_float(value):.{digits}f}%"


def _format_ratio(value):
    ratio = _safe_float(value)
    if abs(ratio) >= 10:
        return f"{ratio:,.1f}"
    return f"{ratio:,.2f}"


def _format_compact_money(value):
    amount = _safe_float(value)
    abs_amount = abs(amount)
    if abs_amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    if abs_amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    return f"${amount:,.0f}"


def _percentile(values, percentile):
    cleaned = sorted(_safe_float(item) for item in values)
    if not cleaned:
        return 0.0
    if len(cleaned) == 1:
        return cleaned[0]
    position = (len(cleaned) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(cleaned) - 1)
    weight = position - lower
    return cleaned[lower] * (1 - weight) + cleaned[upper] * weight


def _format_exchange_label(exchange_name: str) -> str:
    normalized = str(exchange_name or "").strip().lower()
    if normalized == "gateio":
        return "GATE.IO"
    return normalized.upper()


def _score_color(score: float) -> str:
    if score >= 80:
        return SUCCESS_COLOR
    if score >= 65:
        return SECONDARY_COLOR
    if score >= 50:
        return WARNING_COLOR
    return ACCENT_COLOR


def _metric_color(metric_key: str, metric_value: float) -> str:
    value = _safe_float(metric_value)
    if metric_key in {"var", "drawdown", "volatility"}:
        if value <= 3:
            return SUCCESS_COLOR
        if value <= 8:
            return WARNING_COLOR
        return ACCENT_COLOR
    if metric_key in {"sharpe", "sortino", "calmar"}:
        if value >= 1.5:
            return SUCCESS_COLOR
        if value >= 0.7:
            return WARNING_COLOR
        return ACCENT_COLOR
    if metric_key == "return":
        if value >= 0:
            return SUCCESS_COLOR
        return ACCENT_COLOR
    return PRIMARY_COLOR


def _figure_to_base64(fig) -> str:
    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="png",
        dpi=120,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    plt.close(fig)
    return encoded


def _placeholder_chart(title: str, subtitle: str, accent_color: str) -> str:
    fig = plt.figure(figsize=(7.6, 4.0), dpi=120)
    fig.patch.set_facecolor("#0c1118")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#111723")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#1f2a38")
    ax.text(
        0.5,
        0.58,
        title,
        color=accent_color,
        fontsize=18,
        fontweight="bold",
        ha="center",
        va="center",
    )
    ax.text(
        0.5,
        0.42,
        subtitle,
        color="#8a8a9a",
        fontsize=10,
        ha="center",
        va="center",
    )
    return _figure_to_base64(fig)


def _build_nav_chart(advanced_metrics: dict) -> str:
    points = advanced_metrics.get("history_points_series") or []
    if len(points) < 2:
        return _placeholder_chart(
            "NAV History",
            "Нужно больше истории портфеля",
            PRIMARY_COLOR,
        )

    timestamps = [point["timestamp"] for point in points]
    values = [_safe_float(point["total_value_usd"]) for point in points]
    fig = plt.figure(figsize=(8.2, 4.2), dpi=120)
    fig.patch.set_facecolor("#0c1118")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#111723")
    ax.plot(timestamps, values, color=PRIMARY_COLOR, linewidth=2.8)
    ax.fill_between(timestamps, values, color=PRIMARY_COLOR, alpha=0.18)
    ax.scatter(
        timestamps[-1],
        values[-1],
        color=SUCCESS_COLOR if values[-1] >= values[0] else ACCENT_COLOR,
        s=44,
        zorder=5,
    )
    ax.grid(True, color="#1f2a38", alpha=0.4, linestyle="--", linewidth=0.6)
    ax.tick_params(colors="#8a8a9a", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#1f2a38")
    ax.set_title("Portfolio NAV", color=TEXT_PRIMARY, fontsize=14, loc="left", pad=12)
    ax.set_ylabel("USD", color="#8a8a9a", fontsize=10)
    return _figure_to_base64(fig)


def _build_drawdown_chart(advanced_metrics: dict) -> str:
    points = advanced_metrics.get("drawdown_series") or []
    if len(points) < 2:
        return _placeholder_chart(
            "Drawdown Curve",
            "Нет данных для расчета просадки",
            ACCENT_COLOR,
        )

    timestamps = [point["timestamp"] for point in points]
    drawdowns = [_safe_float(point["drawdown_pct"]) for point in points]
    fig = plt.figure(figsize=(8.2, 4.2), dpi=120)
    fig.patch.set_facecolor("#0c1118")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#111723")
    ax.fill_between(timestamps, drawdowns, 0, color=ACCENT_COLOR, alpha=0.28)
    ax.plot(timestamps, drawdowns, color=ACCENT_COLOR, linewidth=2.3)
    ax.axhline(0, color="#1f2a38", linewidth=1.0)
    ax.grid(True, color="#1f2a38", alpha=0.35, linestyle="--", linewidth=0.6)
    ax.tick_params(colors="#8a8a9a", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#1f2a38")
    ax.set_title("Max Drawdown Trace", color=TEXT_PRIMARY, fontsize=14, loc="left", pad=12)
    ax.set_ylabel("%", color="#8a8a9a", fontsize=10)
    return _figure_to_base64(fig)


def _build_returns_histogram(advanced_metrics: dict) -> str:
    returns = [
        _safe_float(item.get("return_pct"))
        for item in (advanced_metrics.get("returns_series") or [])
    ]
    if len(returns) < 2:
        return _placeholder_chart(
            "Return Distribution",
            "Нужно больше наблюдений доходности",
            WARNING_COLOR,
        )

    var_threshold = _percentile(returns, 0.05)
    mean_return = statistics.mean(returns)
    interval_label = advanced_metrics.get("interval_label", "N/A")

    fig = plt.figure(figsize=(9.0, 4.8), dpi=120)
    fig.patch.set_facecolor("#0c1118")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#111723")
    ax.tick_params(colors="#8a8a9a", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#1f2a38")

    _, bins, patches = ax.hist(
        returns,
        bins=min(12, max(7, len(returns) // 3)),
        color=PRIMARY_COLOR,
        alpha=0.85,
        edgecolor="#0c1118",
    )

    for left_edge, right_edge, patch in zip(bins[:-1], bins[1:], patches):
        center = (left_edge + right_edge) / 2.0
        if center <= var_threshold:
            patch.set_facecolor(ACCENT_COLOR)
            patch.set_alpha(0.92)
        elif center < 0:
            patch.set_facecolor(WARNING_COLOR)
            patch.set_alpha(0.82)
        else:
            patch.set_facecolor(SUCCESS_COLOR)
            patch.set_alpha(0.76)

    ax.axvspan(min(returns), var_threshold, color=ACCENT_COLOR, alpha=0.08)
    ax.axvline(0.0, color="#d8dce3", linewidth=1.05, linestyle=":")
    ax.axvline(var_threshold, color=ACCENT_COLOR, linewidth=2.2, linestyle=(0, (5, 3)))
    ax.axvline(mean_return, color=PRIMARY_COLOR, linewidth=2.0)
    ax.grid(True, color="#1f2a38", alpha=0.3, linestyle="--", linewidth=0.6)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.1f}%"))
    ax.set_title("Return Distribution", color=TEXT_PRIMARY, fontsize=14, loc="left", pad=12)
    ax.set_ylabel("Observations", color="#8a8a9a", fontsize=10)
    ax.set_xlabel(f"Periodic return, %  •  interval {interval_label}", color="#8a8a9a", fontsize=10)
    ax.text(
        0.02,
        0.96,
        f"VaR 95%: {var_threshold:.2f}%",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.7,
        color=ACCENT_COLOR,
        bbox={"boxstyle": "round,pad=0.24", "facecolor": "#0d131d", "edgecolor": "#1f2a38", "alpha": 0.94},
    )
    ax.text(
        0.26,
        0.96,
        f"Mean: {mean_return:.2f}%",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.7,
        color=PRIMARY_COLOR,
        bbox={"boxstyle": "round,pad=0.24", "facecolor": "#0d131d", "edgecolor": "#1f2a38", "alpha": 0.94},
    )
    return _figure_to_base64(fig)


def _build_allocation_chart(metrics: dict) -> str:
    asset_distribution = (metrics.get("concentration") or {}).get("asset_distribution") or []
    exchange_distribution = (metrics.get("exchange_dependency") or {}).get("exchanges") or []
    if not asset_distribution and not exchange_distribution:
        return _placeholder_chart(
            "Allocation Snapshot",
            "Нет распределения по активам и биржам",
            SECONDARY_COLOR,
        )

    fig = plt.figure(figsize=(9.0, 4.9), dpi=120)
    fig.patch.set_facecolor("#0c1118")
    grid = fig.add_gridspec(
        2,
        1,
        height_ratios=[1.0, 1.0],
        hspace=0.34,
    )
    ax_assets = fig.add_subplot(grid[0, 0])
    ax_exchanges = fig.add_subplot(grid[1, 0])

    for axis in (ax_assets, ax_exchanges):
        axis.set_facecolor("#111723")
        for spine in axis.spines.values():
            spine.set_color("#1f2a38")

    if asset_distribution:
        total_asset_value = sum(_safe_float(item.get("value")) for item in asset_distribution)
        top_assets = asset_distribution[:5]
        other_pct = max(0.0, 100.0 - sum(item["percentage"] for item in top_assets))
        other_value = max(0.0, total_asset_value - sum(_safe_float(item.get("value")) for item in top_assets))
        asset_rows = list(top_assets)
        if other_pct > 0.05:
            asset_rows.append(
                {"name": "OTHER", "percentage": other_pct, "value": other_value}
            )

        asset_rows = sorted(asset_rows, key=lambda item: item["percentage"])
        labels = [item["name"] for item in asset_rows]
        values = [_safe_float(item["percentage"]) for item in asset_rows]
        raw_values = [_safe_float(item["value"]) for item in asset_rows]
        palette = [PRIMARY_COLOR, SECONDARY_COLOR, "#53d3ff", WARNING_COLOR, ACCENT_COLOR, SUCCESS_COLOR]
        colors = palette[: len(labels)]
        bars = ax_assets.barh(labels, values, color=colors, alpha=0.90, height=0.56)
        ax_assets.set_xlim(0, max(100.0, max(values) * 1.24))
        ax_assets.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.0f}%"))
        ax_assets.tick_params(colors="#d8dce3", labelsize=9)
        ax_assets.grid(True, axis="x", color="#1f2a38", alpha=0.34, linestyle="--", linewidth=0.6)
        ax_assets.set_title("Asset Exposure", color=TEXT_PRIMARY, fontsize=13, loc="left", pad=10)
        ax_assets.set_xlabel("% of portfolio NAV", color="#8a8a9a", fontsize=9)
        for bar, pct in zip(bars, values):
            ax_assets.text(
                bar.get_width() + 1.0,
                bar.get_y() + bar.get_height() / 2.0,
                f"{pct:.1f}%",
                va="center",
                ha="left",
                fontsize=8.9,
                color="#d8dce3",
            )
    else:
        ax_assets.text(0.5, 0.5, "Нет данных", color="#8a8a9a", ha="center", va="center")
        ax_assets.set_title("Asset Exposure", color=TEXT_PRIMARY, fontsize=13, loc="left", pad=10)
        ax_assets.set_xticks([])
        ax_assets.set_yticks([])

    if exchange_distribution:
        rows = sorted(exchange_distribution, key=lambda item: item["percentage"])
        names = [_format_exchange_label(item["exchange"]) for item in rows]
        values = [_safe_float(item["percentage"]) for item in rows]
        exchange_palette = {
            "BYBIT": PRIMARY_COLOR,
            "GATE.IO": WARNING_COLOR,
            "MEXC": SECONDARY_COLOR,
        }
        colors = [exchange_palette.get(name, SUCCESS_COLOR) for name in names]
        bars = ax_exchanges.barh(names, values, color=colors, alpha=0.92, height=0.50)
        ax_exchanges.set_xlim(0, max(100.0, max(values) * 1.24))
        ax_exchanges.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.0f}%"))
        ax_exchanges.tick_params(colors="#d8dce3", labelsize=9)
        ax_exchanges.grid(True, axis="x", color="#1f2a38", alpha=0.35, linestyle="--", linewidth=0.6)
        ax_exchanges.set_title("Exchange Exposure", color=TEXT_PRIMARY, fontsize=13, loc="left", pad=10)
        ax_exchanges.set_xlabel("% of portfolio NAV", color="#8a8a9a", fontsize=9)
        for bar, pct in zip(bars, values):
            ax_exchanges.text(
                bar.get_width() + 1.0,
                bar.get_y() + bar.get_height() / 2.0,
                f"{pct:.1f}%",
                va="center",
                ha="left",
                fontsize=8.8,
                color="#d8dce3",
            )
    else:
        ax_exchanges.text(0.5, 0.5, "Нет данных", color="#8a8a9a", ha="center", va="center")
        ax_exchanges.set_title("Exchange Exposure", color=TEXT_PRIMARY, fontsize=13, loc="left", pad=10)
        ax_exchanges.set_xticks([])
        ax_exchanges.set_yticks([])

    return _figure_to_base64(fig)


def _build_score_orb(score: float, regime_label: str) -> ft.Container:
    accent = _score_color(score)
    return ft.Container(
        width=220,
        height=220,
        alignment=ft.alignment.center,
        content=ft.Stack([
            ft.Container(
                width=220,
                height=220,
                border_radius=110,
                bgcolor=ft.colors.with_opacity(0.10, accent),
                border=ft.border.all(2.5, ft.colors.with_opacity(0.30, accent)),
                shadow=ft.BoxShadow(
                    blur_radius=24,
                    spread_radius=2,
                    color=ft.colors.with_opacity(0.18, accent),
                    offset=ft.Offset(0, 8),
                ),
            ),
            ft.Column([
                ft.Text(
                    f"{score:.0f}",
                    size=66,
                    weight="bold",
                    color=accent,
                ),
                ft.Text(
                    "Risk Score",
                    size=12,
                    color=TEXT_SECONDARY,
                ),
                ft.Container(height=8),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=999,
                    bgcolor=ft.colors.with_opacity(0.14, accent),
                    border=ft.border.all(1, ft.colors.with_opacity(0.24, accent)),
                    content=ft.Text(
                        regime_label.upper(),
                        size=10,
                        weight="bold",
                        color=accent,
                    ),
                ),
            ], alignment="center", horizontal_alignment="center", spacing=0),
        ], alignment=ft.alignment.center),
    )


def _build_kpi_card(title: str, value: str, subtitle: str, accent_color: str) -> ft.Container:
    return ft.Container(
        width=198,
        height=148,
        padding=16,
        border_radius=18,
        bgcolor="#0d131d",
        border=ft.border.all(1, ft.colors.with_opacity(0.26, BORDER_COLOR)),
        content=ft.Column([
            ft.Row([
                ft.Container(
                    width=8,
                    height=8,
                    border_radius=999,
                    bgcolor=accent_color,
                ),
                ft.Text(title, size=10, weight="bold", color=TEXT_SECONDARY),
            ], spacing=8),
            ft.Column([
                ft.Text(value, size=26, weight="bold", color=accent_color),
                ft.Container(height=6),
                ft.Text(subtitle, size=10, color=TEXT_SECONDARY),
            ], spacing=0),
        ], spacing=0, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True),
    )


def _build_chart_panel(
    title: str,
    subtitle: str,
    image_base64: str,
    accent_color: str,
    expand: int = 1,
    height: int = 356,
) -> ft.Container:
    return ft.Container(
        expand=expand,
        height=height,
        padding=18,
        border_radius=20,
        bgcolor="#0d131d",
        border=ft.border.all(1, ft.colors.with_opacity(0.26, BORDER_COLOR)),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(title, size=14, weight="bold", color=TEXT_PRIMARY),
                    ft.Text(subtitle, size=10, color=TEXT_SECONDARY),
                ], spacing=4),
                ft.Container(expand=True),
                ft.Container(
                    width=10,
                    height=10,
                    border_radius=999,
                    bgcolor=accent_color,
                ),
            ], vertical_alignment="center"),
            ft.Container(height=12),
            ft.Container(
                bgcolor="#09111a",
                border_radius=16,
                border=ft.border.all(1, ft.colors.with_opacity(0.16, BORDER_COLOR)),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                padding=10,
                content=ft.Image(
                    src_base64=image_base64,
                    fit=ft.ImageFit.CONTAIN,
                    expand=True,
                ),
                expand=True,
            ),
        ], spacing=0, expand=True),
    )


def _build_factor_tile(title: str, score: float, subtitle: str) -> ft.Container:
    accent = _score_color(score)
    progress_width = max(10, min(100, round(score)))
    progress_pixels = 186 * (progress_width / 100.0)
    return ft.Container(
        width=232,
        height=126,
        padding=16,
        border_radius=18,
        bgcolor="#0d131d",
        border=ft.border.all(1, ft.colors.with_opacity(0.24, BORDER_COLOR)),
        content=ft.Column([
            ft.Row([
                ft.Text(title, size=11, weight="bold", color=TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Text(f"{score:.0f}", size=18, weight="bold", color=accent),
            ], vertical_alignment="center"),
            ft.Container(height=10),
            ft.Container(
                height=10,
                width=186,
                border_radius=999,
                bgcolor=ft.colors.with_opacity(0.18, BORDER_COLOR),
                content=ft.Row([
                    ft.Container(
                        width=progress_pixels,
                        height=10,
                        border_radius=999,
                        bgcolor=accent,
                    ),
                    ft.Container(expand=True),
                ], spacing=0),
            ),
            ft.Container(height=10),
            ft.Text(subtitle, size=10, color=TEXT_SECONDARY),
        ], spacing=0, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True),
    )


def show_portfolio_risk_page(
    page: ft.Page,
    current_user: dict,
    portfolio_data: dict,
    show_main_callback,
):
    user = current_user.get("user")
    if not user or not portfolio_data:
        logger.warning("[PORTFOLIO RISK] Missing user or portfolio data")
        show_main_callback()
        return

    logger.info("[PORTFOLIO RISK] Open page for user=%s", user.name)
    store_portfolio_snapshot(user.id, portfolio_data)

    page.controls.clear()

    analyzer = PortfolioRiskAnalyzer(user.id)
    analysis = analyzer.calculate_overall_stability_score(portfolio_data)
    metrics = analysis.get("metrics") or {}
    advanced = metrics.get("advanced") or {}
    concentration = metrics.get("concentration") or {}
    exchange_dependency = metrics.get("exchange_dependency") or {}
    volatility = metrics.get("volatility") or {}
    stablecoin = metrics.get("stablecoin") or {}
    liquidity = metrics.get("liquidity") or {}
    advanced_scores = analysis.get("advanced_scores") or {}

    nav_chart = _build_nav_chart(advanced)
    drawdown_chart = _build_drawdown_chart(advanced)
    returns_chart = _build_returns_histogram(advanced)
    allocation_chart = _build_allocation_chart(metrics)

    history_chip_color = PRIMARY_COLOR if advanced.get("source") == "portfolio_history" else WARNING_COLOR
    score_color = _score_color(analysis.get("stability_score", 0.0))

    header = ft.Container(
        padding=ft.padding.symmetric(horizontal=24, vertical=18),
        bgcolor=DARK_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, ft.colors.with_opacity(0.22, BORDER_COLOR))),
        content=ft.Row([
            ft.IconButton(
                ft.icons.ARROW_BACK_ROUNDED,
                icon_size=26,
                on_click=lambda e: show_main_callback(),
                tooltip="Вернуться к портфелю",
            ),
            ft.Column([
                ft.Text(
                    "ADVANCED PORTFOLIO RISK METRICS",
                    size=22,
                    weight="bold",
                    color=PRIMARY_COLOR,
                ),
                ft.Text(
                    "VaR, Sharpe, Sortino, Drawdown и Calmar в одном аналитическом экране",
                    size=12,
                    color=TEXT_SECONDARY,
                ),
            ], spacing=4, expand=True),
            ft.Row([
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=999,
                    bgcolor=ft.colors.with_opacity(0.12, history_chip_color),
                    border=ft.border.all(1, ft.colors.with_opacity(0.22, history_chip_color)),
                    content=ft.Text(
                        advanced.get("source_label", "History source"),
                        size=10,
                        weight="bold",
                        color=history_chip_color,
                    ),
                ),
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=999,
                    bgcolor=ft.colors.with_opacity(0.12, PRIMARY_COLOR),
                    border=ft.border.all(1, ft.colors.with_opacity(0.22, PRIMARY_COLOR)),
                    content=ft.Text(
                        f"{advanced.get('history_window_label', 'История недоступна')} · {advanced.get('interval_label', 'N/A')}",
                        size=10,
                        weight="bold",
                        color=PRIMARY_COLOR,
                    ),
                ),
            ], spacing=10),
        ], vertical_alignment="center"),
    )

    overview_panel = ft.Container(
        padding=20,
        border_radius=24,
        bgcolor="#0d131d",
        border=ft.border.all(1, ft.colors.with_opacity(0.26, BORDER_COLOR)),
        content=ft.Row([
            _build_score_orb(analysis.get("stability_score", 0.0), analysis.get("risk_regime", "risk")),
            ft.Container(width=20),
            ft.Column([
                ft.Row([
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border_radius=999,
                        bgcolor=ft.colors.with_opacity(0.12, score_color),
                        border=ft.border.all(1, ft.colors.with_opacity(0.22, score_color)),
                        content=ft.Text(
                            analysis.get("stability_level", "MODERATE"),
                            size=10,
                            weight="bold",
                            color=score_color,
                        ),
                    ),
                    ft.Container(width=10),
                    ft.Text(
                        analysis.get("main_risk", {}).get("name", "Риск"),
                        size=12,
                        weight="bold",
                        color=TEXT_PRIMARY,
                    ),
                ], spacing=0),
                ft.Container(height=16),
                ft.Text(
                    analysis.get("main_risk", {}).get("description", "Нет описания риска"),
                    size=18,
                    weight="bold",
                    color=TEXT_PRIMARY,
                    max_lines=2,
                ),
                ft.Container(height=10),
                ft.Text(
                    analysis.get("recommendation", ""),
                    size=12,
                    color=TEXT_SECONDARY,
                    max_lines=3,
                ),
                ft.Container(height=18),
                ft.Row([
                    _build_factor_tile(
                        "Advanced Risk Composite",
                        advanced_scores.get("advanced_score", 50.0),
                        f"RF {advanced.get('risk_free_rate_annual', 0.02) * 100:.1f}% · "
                        f"Win rate {advanced.get('win_rate_pct', 0.0):.0f}%",
                    ),
                    ft.Container(width=12),
                    _build_factor_tile(
                        "Return / Volatility Profile",
                        advanced_scores.get("sharpe_score", 50.0),
                        f"Return {_format_pct(advanced.get('annualized_return_pct', 0.0))} · "
                        f"Vol {_format_pct(advanced.get('annualized_volatility_pct', 0.0))}",
                    ),
                ], spacing=0, wrap=True),
            ], expand=True, spacing=0),
        ], spacing=0),
    )

    kpi_row = ft.Row([
        _build_kpi_card(
            "VaR 95%",
            _format_money(advanced.get("var_95_abs", 0.0)),
            f"{_format_pct(advanced.get('var_95_pct', 0.0))} ожидаемого убытка",
            _metric_color("var", advanced.get("var_95_pct", 0.0)),
        ),
        _build_kpi_card(
            "Sharpe Ratio",
            _format_ratio(advanced.get("sharpe_ratio", 0.0)),
            "доходность на единицу total risk",
            _metric_color("sharpe", advanced.get("sharpe_ratio", 0.0)),
        ),
        _build_kpi_card(
            "Sortino Ratio",
            _format_ratio(advanced.get("sortino_ratio", 0.0)),
            "доходность на downside-risk",
            _metric_color("sortino", advanced.get("sortino_ratio", 0.0)),
        ),
        _build_kpi_card(
            "Max Drawdown",
            _format_pct(advanced.get("max_drawdown_pct", 0.0)),
            "максимальная историческая просадка",
            _metric_color("drawdown", advanced.get("max_drawdown_pct", 0.0)),
        ),
        _build_kpi_card(
            "Calmar Ratio",
            _format_ratio(advanced.get("calmar_ratio", 0.0)),
            "доходность / max drawdown",
            _metric_color("calmar", advanced.get("calmar_ratio", 0.0)),
        ),
    ], spacing=12, wrap=True)

    chart_row_top = ft.Row([
        _build_chart_panel(
            "Portfolio NAV",
            "динамика стоимости портфеля",
            nav_chart,
            PRIMARY_COLOR,
            expand=1,
        ),
        _build_chart_panel(
            "Drawdown Surface",
            "глубина и длительность просадок",
            drawdown_chart,
            ACCENT_COLOR,
            expand=1,
        ),
    ], spacing=12)

    chart_row_bottom = ft.Column([
        _build_chart_panel(
            "Return Distribution",
            "простое распределение доходностей с линиями VaR и среднего значения",
            returns_chart,
            WARNING_COLOR,
            expand=1,
            height=430,
        ),
        ft.Container(height=12),
        _build_chart_panel(
            "Allocation Snapshot",
            "крупные веса активов и бирж в текущем NAV портфеля",
            allocation_chart,
            SECONDARY_COLOR,
            expand=1,
            height=430,
        ),
    ], spacing=0)

    factor_row = ft.Row([
        _build_factor_tile(
            "Концентрация",
            concentration.get("score", 50.0),
            concentration.get("description", "Нет данных"),
        ),
        _build_factor_tile(
            "Зависимость от бирж",
            exchange_dependency.get("score", 50.0),
            exchange_dependency.get("description", "Нет данных"),
        ),
        _build_factor_tile(
            "Волатильность",
            volatility.get("score", 50.0),
            volatility.get("description", "Нет данных"),
        ),
        _build_factor_tile(
            "Ликвидность",
            liquidity.get("score", 50.0),
            liquidity.get("description", "Нет данных"),
        ),
        _build_factor_tile(
            "Резерв / Stablecoins",
            stablecoin.get("score", 50.0),
            stablecoin.get("description", "Нет данных"),
        ),
        _build_factor_tile(
            "Advanced Layer",
            advanced_scores.get("advanced_score", 50.0),
            f"Points {advanced.get('history_points', 0)} · {advanced.get('source_label', 'N/A')}",
        ),
    ], spacing=12, wrap=True)

    footer = ft.Container(
        padding=ft.padding.symmetric(horizontal=24, vertical=14),
        bgcolor=CARD_BG,
        border=ft.border.only(top=ft.BorderSide(1, ft.colors.with_opacity(0.22, BORDER_COLOR))),
        content=ft.Text(
            "Invest Wallet • Advanced Portfolio Risk Workspace",
            size=11,
            color=TEXT_SECONDARY,
            italic=True,
            text_align="center",
        ),
    )

    body = ft.Column([
        overview_panel,
        ft.Container(height=16),
        kpi_row,
        ft.Container(height=16),
        chart_row_top,
        ft.Container(height=16),
        chart_row_bottom,
        ft.Container(height=16),
        factor_row,
        ft.Container(height=18),
    ], spacing=0, scroll="adaptive")

    page.add(
        ft.Column([
            header,
            ft.Container(
                expand=True,
                padding=ft.padding.symmetric(horizontal=24, vertical=18),
                content=body,
            ),
            footer,
        ], expand=True, spacing=0)
    )
    page.update()
