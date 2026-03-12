#!/usr/bin/env python3
"""
Одноразовое обучение XGBoost-классификатора на данных btc_prices.csv.

Запуск:
    python -m ml.train

Результат:
    Обученная модель сохраняется в ml/saved/xgb_direction.joblib
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS, build_features, get_feature_target_split
from ml.trainer import train_xgboost_classifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ml.train")

CSV_PATH = Path(__file__).parent / "btc_prices.csv"
SAVED_DIR = Path(__file__).parent / "saved"
MODEL_PATH = SAVED_DIR / "xgb_direction.joblib"

N_TRIALS = 50


def main() -> None:
    logger.info("=" * 60)
    logger.info("  ОБУЧЕНИЕ МОДЕЛИ XGBoost НА btc_prices.csv")
    logger.info("=" * 60)

    # 1. Загрузка CSV
    if not CSV_PATH.exists():
        logger.error("Файл не найден: %s", CSV_PATH)
        sys.exit(1)

    df_raw = pd.read_csv(CSV_PATH)

    # Унификация столбцов
    if "Start" in df_raw.columns:
        df_raw = df_raw.rename(columns={"Start": "Date"})
    df_raw["Date"] = pd.to_datetime(df_raw["Date"])

    required = ["Date", "Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in df_raw.columns]
    if missing:
        logger.error("Отсутствуют столбцы: %s", missing)
        sys.exit(1)

    df_raw = df_raw[required].sort_values("Date").reset_index(drop=True)
    logger.info("Загружено %d записей  |  %s — %s",
                len(df_raw),
                df_raw["Date"].min().date(),
                df_raw["Date"].max().date())

    # 2. Feature engineering
    df = build_features(df_raw)
    logger.info("После генерации признаков: %d строк, %d признаков",
                len(df), len(FEATURE_COLUMNS))

    # 3. Разделение train / val (70/30 по времени)
    X, y = get_feature_target_split(df)
    X = X.astype(float)
    y = y.astype(float)

    mask = np.isfinite(X.values).all(axis=1) & np.isfinite(y.values)
    X = X[mask].reset_index(drop=True)
    y = y[mask].reset_index(drop=True)

    split = int(len(X) * 0.7)
    X_train, X_val = X.iloc[:split], X.iloc[split:]
    y_train, y_val = y.iloc[:split], y.iloc[split:]

    logger.info("Train: %d  |  Val: %d", len(X_train), len(X_val))

    # 4. Обучение с Optuna
    clf = train_xgboost_classifier(
        X_train, y_train, X_val, y_val, n_trials=N_TRIALS,
    )

    # 5. Оценка на валидации
    acc = clf.score(X_val, y_val)
    logger.info("Accuracy на валидации: %.4f", acc)

    # 6. Сохранение
    SAVED_DIR.mkdir(parents=True, exist_ok=True)

    import joblib
    joblib.dump(clf, MODEL_PATH)
    logger.info("Модель сохранена: %s", MODEL_PATH)
    logger.info("=" * 60)
    logger.info("  ГОТОВО. Модель можно использовать в приложении.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
