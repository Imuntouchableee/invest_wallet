"""
Модуль предсказания: загружает обученные модели и выводит
прогноз цены и вероятность роста/падения для последней записи.
"""

import logging
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SAVED_DIR = Path(__file__).resolve().parent.parent / "models" / "saved"

MODEL_NAMES = ["xgboost", "lightgbm", "catboost"]
DISPLAY_NAMES = {
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",
}


def _load_model(name: str, kind: str) -> Any:
    """Загружает модель из .joblib."""
    path = SAVED_DIR / f"{name}_{kind}.joblib"
    if not path.exists():
        raise FileNotFoundError(f"Модель не найдена: {path}")
    return joblib.load(path)


def predict_next_day(
    X_last: pd.DataFrame,
) -> Dict[str, Dict[str, Any]]:
    """Предсказывает цену и направление на следующий день.

    Parameters
    ----------
    X_last : pd.DataFrame
        Признаки последней доступной записи (1 строка).

    Returns
    -------
    Dict[str, Dict[str, Any]]
        Словарь {model_name: {predicted_price, prob_growth, prob_fall}}.
    """
    predictions: Dict[str, Dict[str, Any]] = {}

    for name in MODEL_NAMES:
        display = DISPLAY_NAMES[name]
        reg_model = _load_model(name, "regressor")
        clf_model = _load_model(name, "classifier")

        predicted_price = float(reg_model.predict(X_last)[0])

        if hasattr(clf_model, "predict_proba"):
            prob = clf_model.predict_proba(X_last)[0]
            prob_fall = float(prob[0]) * 100
            prob_growth = float(prob[1]) * 100
        else:
            pred_dir = int(clf_model.predict(X_last)[0])
            prob_growth = 100.0 if pred_dir == 1 else 0.0
            prob_fall = 100.0 - prob_growth

        predictions[display] = {
            "predicted_price": round(predicted_price, 2),
            "prob_growth": round(prob_growth, 1),
            "prob_fall": round(prob_fall, 1),
        }

        logger.info(
            "[%s] Predicted price: %.2f | Growth: %.1f%% | Fall: %.1f%%",
            display, predicted_price, prob_growth, prob_fall,
        )

    return predictions


def print_predictions(predictions: Dict[str, Dict[str, Any]]) -> None:
    """Красиво выводит предсказания в консоль.

    Parameters
    ----------
    predictions : Dict[str, Dict[str, Any]]
        Результат predict_next_day().
    """
    print("\n" + "=" * 55)
    print("  ПРОГНОЗ ЦЕНЫ BITCOIN НА СЛЕДУЮЩИЙ ДЕНЬ")
    print("=" * 55)
    for model_name, data in predictions.items():
        print(f"\n  [{model_name}]")
        print(f"    Predicted price: {data['predicted_price']:.2f}")
        print(f"    Probability of growth: {data['prob_growth']:.1f}%")
        print(f"    Probability of fall:   {data['prob_fall']:.1f}%")
    print("\n" + "=" * 55)
