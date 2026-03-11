"""
Модуль расчёта метрик качества моделей.

Регрессия: MAE, RMSE, MAPE, R².
Классификация: Accuracy, Precision, Recall, F1, ROC-AUC.
"""

import logging
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


def regression_metrics(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Вычисляет метрики регрессии.

    Parameters
    ----------
    y_true : array-like
        Истинные значения.
    y_pred : array-like
        Предсказанные значения.

    Returns
    -------
    Dict[str, float]
        MAE, RMSE, MAPE, R2.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    # MAPE — защита от деления на ноль
    mask = y_true != 0
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
    r2 = r2_score(y_true, y_pred)

    metrics = {"MAE": round(mae, 4), "RMSE": round(rmse, 4),
               "MAPE": round(mape, 4), "R2": round(r2, 4)}
    logger.info("Регрессионные метрики: %s", metrics)
    return metrics


def classification_metrics(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    y_prob: np.ndarray | None = None,
) -> Dict[str, float]:
    """Вычисляет метрики классификации.

    Parameters
    ----------
    y_true : array-like
        Истинные метки (0/1).
    y_pred : array-like
        Предсказанные метки (0/1).
    y_prob : array-like, optional
        Вероятности положительного класса (для ROC-AUC).

    Returns
    -------
    Dict[str, float]
        Accuracy, Precision, Recall, F1, ROC-AUC.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)

    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    roc_auc = None
    if y_prob is not None:
        try:
            roc_auc = roc_auc_score(y_true, y_prob)
        except ValueError:
            roc_auc = float("nan")

    metrics: Dict[str, Any] = {
        "Accuracy": round(acc, 4),
        "Precision": round(prec, 4),
        "Recall": round(rec, 4),
        "F1": round(f1, 4),
    }
    if roc_auc is not None:
        metrics["ROC-AUC"] = round(roc_auc, 4)

    logger.info("Классификационные метрики: %s", metrics)
    return metrics
