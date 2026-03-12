"""
Генерация технических индикаторов (Feature Engineering).

23 признака на основе OHLCV-данных:
  - Скользящие средние (SMA): 7, 14, 30, 60, 200
  - Экспоненциальные средние (EMA): 7, 14, 30
  - Трендовые: RSI(14), MACD, MACD_signal, MACD_hist
  - Волатильность: rolling_std_7, rolling_std_30
  - Доходность: return_1d, return_3d, return_7d
  - Дополнительные: high_low_ratio, close_open_ratio, volume_change

Целевая переменная:
  target_direction — 1 если цена вырастет, 0 иначе.
"""

from typing import List, Tuple

import numpy as np
import pandas as pd

FEATURE_COLUMNS: List[str] = [
    "Open", "High", "Low", "Close", "Volume",
    "SMA_7", "SMA_14", "SMA_30", "SMA_60", "SMA_200",
    "EMA_7", "EMA_14", "EMA_30",
    "RSI_14", "MACD", "MACD_signal", "MACD_hist",
    "rolling_std_7", "rolling_std_30",
    "return_1d", "return_3d", "return_7d",
    "high_low_ratio", "close_open_ratio", "volume_change",
]

TARGET_DIRECTION = "target_direction"


def _add_sma(df: pd.DataFrame) -> pd.DataFrame:
    for window in [7, 14, 30, 60, 200]:
        df[f"SMA_{window}"] = df["Close"].rolling(window=window).mean()
    return df


def _add_ema(df: pd.DataFrame) -> pd.DataFrame:
    for span in [7, 14, 30]:
        df[f"EMA_{span}"] = df["Close"].ewm(span=span, adjust=False).mean()
    return df


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _add_trend_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["RSI_14"] = _compute_rsi(df["Close"], period=14)
    ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema_12 - ema_26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df


def _add_volatility(df: pd.DataFrame) -> pd.DataFrame:
    df["rolling_std_7"] = df["Close"].rolling(window=7).std()
    df["rolling_std_30"] = df["Close"].rolling(window=30).std()
    return df


def _add_returns(df: pd.DataFrame) -> pd.DataFrame:
    df["return_1d"] = df["Close"].pct_change(periods=1)
    df["return_3d"] = df["Close"].pct_change(periods=3)
    df["return_7d"] = df["Close"].pct_change(periods=7)
    return df


def _add_extra_features(df: pd.DataFrame) -> pd.DataFrame:
    df["high_low_ratio"] = df["High"] / df["Low"]
    df["close_open_ratio"] = df["Close"] / df["Open"]
    df["volume_change"] = df["Volume"].pct_change()
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Создаёт все признаки и целевую переменную, удаляет NaN.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV-данные с колонками Date, Open, High, Low, Close, Volume.

    Returns
    -------
    pd.DataFrame
        DataFrame с признаками и target_direction, без NaN.
    """
    df = df.copy()
    df = _add_sma(df)
    df = _add_ema(df)
    df = _add_trend_indicators(df)
    df = _add_volatility(df)
    df = _add_returns(df)
    df = _add_extra_features(df)

    df[TARGET_DIRECTION] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna().reset_index(drop=True)
    return df


def get_feature_target_split(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Разделяет DataFrame на признаки (X) и целевую переменную (y).

    Returns
    -------
    Tuple[pd.DataFrame, pd.Series]
        (X, y_direction)
    """
    drop_cols = [c for c in ["Date", TARGET_DIRECTION] if c in df.columns]
    X = df.drop(columns=drop_cols)
    y = df[TARGET_DIRECTION]
    return X, y
