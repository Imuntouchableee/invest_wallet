"""
Benchmark-модуль: загружает обученные модели, выполняет предсказания
на тестовом наборе, считает метрики и измеряет время инференса.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd

from evaluation.metrics import classification_metrics, regression_metrics

logger = logging.getLogger(__name__)

SAVED_DIR = Path(__file__).resolve().parent.parent / "models" / "saved"

MODEL_NAMES: List[str] = ["xgboost", "lightgbm", "catboost"]


def _load_model(name: str, kind: str) -> Any:
    """Загружает модель из .joblib файла.

    Parameters
    ----------
    name : str
        Имя модели (xgboost | lightgbm | catboost).
    kind : str
        Тип модели (regressor | classifier).

    Returns
    -------
    Any
        Загруженный объект модели.
    """
    path = SAVED_DIR / f"{name}_{kind}.joblib"
    if not path.exists():
        raise FileNotFoundError(f"Модель не найдена: {path}")
    return joblib.load(path)


def run_benchmark(
    X_test: pd.DataFrame,
    y_test_price: pd.Series,
    y_test_dir: pd.Series,
) -> pd.DataFrame:
    """Выполняет бенчмарк всех моделей на тестовой выборке.

    Parameters
    ----------
    X_test : pd.DataFrame
        Признаки тестовой выборки.
    y_test_price : pd.Series
        Истинные цены (регрессия).
    y_test_dir : pd.Series
        Истинные направления (классификация).

    Returns
    -------
    pd.DataFrame
        Сводная таблица с метриками и временем инференса.
    """
    results: List[Dict[str, Any]] = []

    for name in MODEL_NAMES:
        logger.info("--- Benchmark: %s ---", name)
        reg_model = _load_model(name, "regressor")
        clf_model = _load_model(name, "classifier")

        # Регрессия — предсказание + время
        t0 = time.perf_counter()
        y_pred_price = reg_model.predict(X_test)
        reg_time = time.perf_counter() - t0

        # Классификация — предсказание + время
        t0 = time.perf_counter()
        y_pred_dir = clf_model.predict(X_test)
        clf_time = time.perf_counter() - t0

        # Вероятности для ROC-AUC
        if hasattr(clf_model, "predict_proba"):
            y_prob = clf_model.predict_proba(X_test)[:, 1]
        else:
            y_prob = None

        reg_m = regression_metrics(y_test_price, y_pred_price)
        clf_m = classification_metrics(y_test_dir, y_pred_dir, y_prob)

        total_time = reg_time + clf_time

        row = {
            "Model": name.upper() if name != "lightgbm" else "LightGBM",
            **reg_m,
            **clf_m,
            "prediction_time_seconds": round(total_time, 6),
        }
        # Красивые имена
        if name == "xgboost":
            row["Model"] = "XGBoost"
        elif name == "catboost":
            row["Model"] = "CatBoost"

        results.append(row)
        logger.info("Время предсказания %s: %.6f сек", row["Model"], total_time)

    df_results = pd.DataFrame(results)
    return df_results
