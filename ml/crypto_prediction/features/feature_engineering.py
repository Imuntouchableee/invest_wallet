"""
Модуль генерации признаков (Feature Engineering).

Создаёт технические индикаторы и целевые переменные
для прогнозирования цены Bitcoin.
"""

import logging
from typing import List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Список всех создаваемых признаков (для удобства)
FEATURE_COLUMNS: List[str] = [
    "Open", "High", "Low", "Close", "Volume",
    # Скользящие средние
    "SMA_7", "SMA_14", "SMA_30", "SMA_60", "SMA_200",
    # Экспоненциальные средние
    "EMA_7", "EMA_14", "EMA_30",
    # Трендовые индикаторы
    "RSI_14", "MACD", "MACD_signal", "MACD_hist",
    # Волатильность
    "rolling_std_7", "rolling_std_30",
    # Доходность
    "return_1d", "return_3d", "return_7d",
    # Дополнительные
    "high_low_ratio", "close_open_ratio", "volume_change",
]

TARGET_PRICE = "target_price"
TARGET_DIRECTION = "target_direction"


def _add_sma(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет простые скользящие средние (SMA)."""
    for window in [7, 14, 30, 60, 200]:
        df[f"SMA_{window}"] = df["Close"].rolling(window=window).mean()
    return df


def _add_ema(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет экспоненциальные скользящие средние (EMA)."""
    for span in [7, 14, 30]:
        df[f"EMA_{span}"] = df["Close"].ewm(span=span, adjust=False).mean()
    return df


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Вычисляет RSI (Relative Strength Index).

    Parameters
    ----------
    series : pd.Series
        Временной ряд цен закрытия.
    period : int
        Период RSI (по умолчанию 14).

    Returns
    -------
    pd.Series
        Значения RSI.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _add_trend_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет RSI, MACD, MACD_signal, MACD_hist."""
    # RSI(14)
    df["RSI_14"] = _compute_rsi(df["Close"], period=14)

    # MACD
    ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_12 - ema_26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df


def _add_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет показатели волатильности."""
    df["rolling_std_7"] = df["Close"].rolling(window=7).std()
    df["rolling_std_30"] = df["Close"].rolling(window=30).std()
    return df


def _add_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет доходности за 1, 3 и 7 дней."""
    df["return_1d"] = df["Close"].pct_change(periods=1)
    df["return_3d"] = df["Close"].pct_change(periods=3)
    df["return_7d"] = df["Close"].pct_change(periods=7)
    return df


def _add_extra_features(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет дополнительные признаки."""
    df["high_low_ratio"] = df["High"] / df["Low"]
    df["close_open_ratio"] = df["Close"] / df["Open"]
    df["volume_change"] = df["Volume"].pct_change()
    return df


def _add_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Создаёт целевые переменные.

    target_price     — цена закрытия следующего дня (регрессия).
    target_direction — 1 если цена вырастет, 0 иначе (классификация).
    """
    df[TARGET_PRICE] = df["Close"].shift(-1)
    df[TARGET_DIRECTION] = (df["Close"].shift(-1) > df["Close"]).astype(int)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Создаёт все признаки и целевые переменные, удаляет NaN.

    Parameters
    ----------
    df : pd.DataFrame
        Сырые данные с колонками Date, Open, High, Low, Close, Volume.

    Returns
    -------
    pd.DataFrame
        DataFrame с признаками и целями, без NaN.
    """
    logger.info("Генерация признаков...")
    df = df.copy()

    df = _add_sma(df)
    df = _add_ema(df)
    df = _add_trend_indicators(df)
    df = _add_volatility(df)
    df = _add_returns(df)
    df = _add_extra_features(df)
    df = _add_targets(df)

    rows_before = len(df)
    df = df.dropna().reset_index(drop=True)
    rows_after = len(df)
    logger.info(
        "Удалено %d строк с NaN. Осталось %d строк.",
        rows_before - rows_after, rows_after,
    )
    return df


def get_feature_target_split(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Разделяет DataFrame на признаки (X) и целевые переменные (y).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame после build_features().

    Returns
    -------
    Tuple[pd.DataFrame, pd.Series, pd.Series]
        (X, y_price, y_direction)
    """
    drop_cols = ["Date", TARGET_PRICE, TARGET_DIRECTION]
    existing_drop = [c for c in drop_cols if c in df.columns]
    X = df.drop(columns=existing_drop)
    y_price = df[TARGET_PRICE]
    y_direction = df[TARGET_DIRECTION]
    return X, y_price, y_direction
