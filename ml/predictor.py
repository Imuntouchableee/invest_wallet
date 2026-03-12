"""
Прогнозирование направления цены через предобученную модель XGBoost.

Модель обучается ОДИН раз через  python -m ml.train  и хранится в
ml/saved/xgb_direction.joblib.

При вызове predict_direction():
  1. Загружает OHLCV-данные выбранной монеты из PostgreSQL
  2. Если в БД данных нет — подтягивает с биржи и сохраняет
  3. Строит 23 технических индикатора
  4. Прогоняет через предобученную модель
  5. Возвращает вероятности роста / падения в процентах
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import ccxt
import joblib
import numpy as np
import pandas as pd

from data.database import DatabaseManager
from ml.features import build_features, get_feature_target_split

logger = logging.getLogger(__name__)

SAVED_DIR = Path(__file__).parent / "saved"
MODEL_PATH = SAVED_DIR / "xgb_direction.joblib"
MIN_CANDLES = 250

_model_cache = {"clf": None}


def _get_model():
    """Загружает модель из файла (с кэшем в памяти)."""
    if _model_cache["clf"] is not None:
        return _model_cache["clf"]
    if not MODEL_PATH.exists():
        return None
    clf = joblib.load(MODEL_PATH)
    _model_cache["clf"] = clf
    logger.info("Модель загружена из %s", MODEL_PATH.name)
    return clf


def _fetch_ohlcv_from_exchange(symbol: str, days: int = 500) -> pd.DataFrame:
    """Загружает дневные OHLCV-свечи с бирж через ccxt (публичный API)."""
    exchanges = [
        ccxt.bybit({"enableRateLimit": True}),
        ccxt.mexc({"enableRateLimit": True}),
        ccxt.gateio({"enableRateLimit": True}),
    ]
    since = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)

    for exchange in exchanges:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, "1d", since=since, limit=days)
            if ohlcv and len(ohlcv) >= MIN_CANDLES:
                df = pd.DataFrame(
                    ohlcv,
                    columns=["timestamp", "Open", "High", "Low", "Close", "Volume"],
                )
                df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
                df = df.sort_values("Date").reset_index(drop=True)
                logger.info(
                    "Загружено %d свечей для %s с %s",
                    len(df), symbol, exchange.id,
                )
                return df
        except Exception as exc:
            logger.warning(
                "Не удалось загрузить %s с %s: %s",
                symbol, exchange.id, exc,
            )
            continue

    return pd.DataFrame()


def _save_to_db(symbol: str, df: pd.DataFrame) -> None:
    db = DatabaseManager()
    if not db.connect():
        return
    try:
        db.save_price_history(symbol, df)
    finally:
        db.close()


def _load_from_db(symbol: str) -> pd.DataFrame:
    db = DatabaseManager()
    if not db.connect():
        return pd.DataFrame()
    try:
        return db.load_price_history(symbol)
    finally:
        db.close()


def predict_direction(symbol: str) -> dict:
    """Прогнозирует направление цены для указанного символа.

    Использует предобученную модель (без повторного обучения).

    Parameters
    ----------
    symbol : str
        Торговая пара, например 'BTC/USDT'.

    Returns
    -------
    dict
        {
            'status': 'ok' | 'error',
            'prob_up': float (0–100),
            'prob_down': float (0–100),
            'signal': 'up' | 'down',
            'confidence': float (0–100),
            'error': str  (только при status='error'),
        }
    """
    try:
        # 1. Проверка наличия модели
        clf = _get_model()
        if clf is None:
            return {
                "status": "error",
                "error": (
                    "Модель не найдена. "
                    "Запустите обучение: python -m ml.train"
                ),
            }

        # 2. Загрузка данных из БД
        df_raw = _load_from_db(symbol)

        # 3. Если данных мало — загрузка с биржи и сохранение
        if df_raw.empty or len(df_raw) < MIN_CANDLES:
            logger.info(
                "Недостаточно данных в БД для %s (%d), загрузка с биржи...",
                symbol, 0 if df_raw.empty else len(df_raw),
            )
            df_raw = _fetch_ohlcv_from_exchange(symbol)
            if not df_raw.empty:
                _save_to_db(symbol, df_raw)

        if df_raw.empty or len(df_raw) < MIN_CANDLES:
            count = 0 if df_raw.empty else len(df_raw)
            return {
                "status": "error",
                "error": (
                    f"Недостаточно исторических данных "
                    f"({count} свечей, нужно {MIN_CANDLES})"
                ),
            }

        # Приведение типов (Decimal из PostgreSQL → float)
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col in df_raw.columns:
                df_raw[col] = df_raw[col].astype(float)

        # 4. Feature engineering
        df = build_features(df_raw)
        if len(df) < 50:
            return {
                "status": "error",
                "error": "Недостаточно данных после обработки признаков",
            }

        X, _ = get_feature_target_split(df)
        X = X.astype(float)

        # 5. Прогноз на последней строке
        X_last = X.iloc[[-1]]
        prob = clf.predict_proba(X_last)[0]
        prob_down = float(prob[0]) * 100
        prob_up = float(prob[1]) * 100

        signal = "up" if prob_up > prob_down else "down"
        confidence = max(prob_up, prob_down)

        return {
            "status": "ok",
            "prob_up": round(prob_up, 1),
            "prob_down": round(prob_down, 1),
            "signal": signal,
            "confidence": round(confidence, 1),
        }

    except Exception as exc:
        logger.error("Ошибка прогнозирования %s: %s", symbol, exc, exc_info=True)
        return {"status": "error", "error": str(exc)}
